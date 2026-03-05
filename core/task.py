"""
Task execution module for workflow steps.
"""

import json
import os
import re
import shlex
import signal
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel, Field

from core.path_utils import resolve_file_path

# Exit codes
SUCCESS = 0
FAILURE = 1
STOPPED = 2  # Graceful stop requested
SKIPPED = 3  # Step was skipped via user request
STALE = 200  # AI process went stale (no log activity)


class ModelType:
    """Model type constants."""
    INHERIT = "INHERIT"
    PROGRAM = "PROGRAM"
    CLAUDE_CODE = "CLAUDE_CODE"
    OPENCODE = "OPENCODE"
    DISPATCH_FUZZING_JOB = "DISPATCH_FUZZING_JOB"


class Model(BaseModel):
    """Model configuration."""
    type: str
    model: str


class OutputConfig(BaseModel):
    """Output configuration for task steps."""
    capture: bool = False
    save_to: str | None = None


class DispatchConfig(BaseModel):
    """Configuration for DISPATCH_FUZZING_JOB steps. Defaults are applied by the backend."""
    fuzzerType: str | None = None
    duration: int | None = None
    directory: str | None = None
    fuzzerArgs: dict | None = None
    label: str | None = None


class TaskStep(BaseModel):
    """Task step type."""
    type: Literal["task"]
    name: str
    description: str | None = None
    prompt: str = ""  # Optional for DISPATCH_FUZZING_JOB
    model: Model
    shouldCreateSummary: bool = Field(alias="shouldCreateSummary")
    shouldCommitChanges: bool = Field(alias="shouldCommitChanges")
    output: OutputConfig | None = None
    allowFailure: bool = Field(default=False, alias="allowFailure")
    dispatchConfig: DispatchConfig | None = Field(default=None, alias="dispatchConfig")
    preconditions: list[str] | None = Field(default=None, alias="preconditions")
    # Skip/interrupt support
    canSkip: bool = Field(default=False, alias="canSkip")
    # Live log monitoring (for long-running steps like echidna)
    logFile: str | None = Field(default=None, alias="logFile")
    logInterval: int = Field(default=10, alias="logInterval")  # seconds
    logRegex: str | None = Field(default=None, alias="logRegex")


# Global reference to currently running subprocess (for skip/interrupt)
_current_process: subprocess.Popen | None = None
_current_process_lock = threading.Lock()


def get_current_process() -> subprocess.Popen | None:
    """Get the currently running subprocess (if any)."""
    with _current_process_lock:
        return _current_process


def set_current_process(proc: subprocess.Popen | None):
    """Set the currently running subprocess reference."""
    global _current_process
    with _current_process_lock:
        _current_process = proc


def interrupt_current_process() -> bool:
    """
    Send SIGINT (Ctrl+C) to interrupt the current subprocess and its children.

    Since we use start_new_session=True, the process runs in its own process group.
    We send SIGINT to the entire process group so that child processes (like echidna
    spawned by bash -c) also receive the signal.

    Returns True if signal was sent, False if no process running.
    """
    proc = get_current_process()
    if not proc or proc.poll() is not None:
        print(f"  ⚠ No current process to interrupt (proc={proc}, poll={proc.poll() if proc else 'N/A'})")
        return False

    try:
        # Send SIGINT to the entire process group (proc.pid is the group leader)
        os.killpg(proc.pid, signal.SIGINT)
        print(f"  ⏭️  Sent SIGINT (Ctrl+C) to process group {proc.pid}")
        return True
    except Exception as e:
        print(f"  ⚠ Failed to send SIGINT: {e}")
        return False


class LogMonitor:
    """
    Background thread that monitors a log file and extracts data via regex.
    Sends extracted data to the backend at regular intervals.
    """

    def __init__(
        self,
        log_file: str,
        interval: int,
        regex_pattern: str | None,
        progress_callback: callable
    ):
        self.log_file = log_file
        self.interval = interval
        self.regex_pattern = re.compile(regex_pattern) if regex_pattern else None
        self.progress_callback = progress_callback
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_position = 0

    def start(self):
        """Start the monitoring thread."""
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the monitoring thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _monitor_loop(self):
        """Main monitoring loop."""
        while not self._stop_event.is_set():
            try:
                self._check_log_file()
            except Exception as e:
                print(f"  ⚠ Log monitor error: {e}")

            # Wait for interval or until stopped
            self._stop_event.wait(timeout=self.interval)

    def _check_log_file(self):
        """Read new content from log file and extract matches."""
        if not os.path.exists(self.log_file):
            return

        try:
            with open(self.log_file, 'r') as f:
                f.seek(self._last_position)
                new_content = f.read()
                self._last_position = f.tell()

            if not new_content:
                return

            # Extract matches using regex
            extracted = None
            if self.regex_pattern:
                matches = self.regex_pattern.findall(new_content)
                if matches:
                    # Keep the last match
                    extracted = matches[-1] if isinstance(matches[-1], str) else str(matches[-1])
            else:
                # No regex - send last few lines
                lines = new_content.strip().split('\n')
                extracted = '\n'.join(lines[-5:]) if lines else None

            if extracted:
                self.progress_callback(extracted)
        except Exception as e:
            print(f"  ⚠ Error reading log file: {e}")


class OpenCodeLogMonitor:
    """
    Background thread that monitors OPENCODE JSON log output and extracts progress.
    OPENCODE outputs JSON lines, and we parse:
    - todowrite tool events to extract todo progress
    - write tool events to extract file write activity

    Also tracks staleness - if no log updates for stale_timeout seconds,
    the process is considered stale.
    """

    def __init__(
        self,
        log_file: str,
        interval: int = 5,
        progress_callback: Callable[[dict], None] | None = None,
        stale_timeout: int = 300  # 5 minutes default
    ):
        self.log_file = log_file
        self.interval = interval
        self.progress_callback = progress_callback
        self.stale_timeout = stale_timeout
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_position = 0
        self._last_progress: str | None = None
        self._last_update_time: float = time.time()  # Track when we last saw log activity
        self._is_stale = False

    @property
    def is_stale(self) -> bool:
        """Check if the log has been stale (no updates) for stale_timeout seconds."""
        return self._is_stale

    def _check_staleness(self):
        """Check if logs are stale and update the stale flag."""
        elapsed = time.time() - self._last_update_time
        if elapsed >= self.stale_timeout:
            if not self._is_stale:
                print(f"  ⚠️ AI process appears stale - no log updates for {int(elapsed)}s")
                self._is_stale = True

    def start(self):
        """Start the monitor thread."""
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the monitor thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _extract_progress(self, json_line: str) -> str | None:
        """
        Extract progress from a JSON line.
        Returns format:
        - "✅ todos X/Y: {in_progress todo content}" for todowrite
        - "✏️ Write: {filename}" for write
        """
        try:
            import json
            data = json.loads(json_line)

            # Check if this is a tool_use event
            if data.get("type") != "tool_use":
                return None

            part = data.get("part", {})
            tool = part.get("tool")

            if tool == "todowrite":
                return self._extract_todo_progress(part)
            elif tool == "write":
                return self._extract_write_progress(part)

            return None

        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def _extract_todo_progress(self, part: dict) -> str | None:
        """Extract todo progress from a todowrite tool event."""
        try:
            state = part.get("state", {})
            input_data = state.get("input", {})
            todos = input_data.get("todos", [])

            if not todos:
                return None

            # Calculate progress
            total = len(todos)
            pending_count = sum(1 for t in todos if t.get("status") == "pending")
            completed_count = total - pending_count

            # Find in_progress todo content
            in_progress_todo = next(
                (t for t in todos if t.get("status") == "in_progress"),
                None
            )

            if in_progress_todo:
                content = in_progress_todo.get("content", "")
                # Truncate long content
                if len(content) > 60:
                    content = content[:57] + "..."
                return f"✅ todos {completed_count}/{total}: {content}"
            else:
                return f"✅ todos {completed_count}/{total}"
        except (KeyError, TypeError):
            return None

    def _extract_write_progress(self, part: dict) -> str | None:
        """Extract file write progress from a write tool event."""
        try:
            state = part.get("state", {})
            input_data = state.get("input", {})
            file_path = input_data.get("filePath", "")

            if not file_path:
                return None

            # Extract just the filename from the path
            filename = os.path.basename(file_path)
            return f"✏️ Write: {filename}"
        except (KeyError, TypeError):
            return None

    def _monitor_loop(self):
        """Main monitoring loop that reads new JSON lines and extracts progress."""
        while not self._stop_event.is_set():
            self._read_and_report()
            self._stop_event.wait(timeout=self.interval)

    def _read_and_report(self):
        """Read new content from log file and report progress."""
        try:
            if not os.path.exists(self.log_file):
                return

            with open(self.log_file, 'r') as f:
                f.seek(self._last_position)
                new_content = f.read()
                self._last_position = f.tell()

            if not new_content:
                # No new content - check staleness
                self._check_staleness()
                return

            # Got new content - reset staleness tracking
            self._last_update_time = time.time()
            self._is_stale = False

            # Process each JSON line
            for line in new_content.strip().split('\n'):
                if not line.strip():
                    continue
                progress = self._extract_progress(line)
                if progress and progress != self._last_progress:
                    self._last_progress = progress
                    if self.progress_callback:
                        self.progress_callback(progress)
        except Exception as e:
            pass  # Silent fail for monitoring


class SkipChecker:
    """
    Background thread that polls for skip requests and interrupts the subprocess.
    """

    def __init__(self, step_id: str, check_interval: int = 5):
        self.step_id = step_id
        self.check_interval = check_interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._skipped = False

    @property
    def was_skipped(self) -> bool:
        return self._skipped

    def start(self):
        """Start the skip checker thread."""
        self._thread = threading.Thread(target=self._check_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the skip checker thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _check_loop(self):
        """Main checking loop."""
        # Import here to avoid circular dependency
        from worker import check_skip_requested

        api_url = os.environ.get('WORKER_API_URL')
        bearer_token = os.environ.get('WORKER_BEARER_TOKEN')
        job_id = os.environ.get('WORKER_JOB_ID')

        if not all([api_url, bearer_token, job_id]):
            return

        while not self._stop_event.is_set():
            try:
                if check_skip_requested(api_url, bearer_token, job_id, self.step_id):
                    print(f"  ⏭️  Skip requested for step {self.step_id}")
                    self._skipped = True
                    interrupt_current_process()  # Sends SIGINT to the process
                    # Clear the skipStepId so it doesn't trigger again
                    from worker import clear_skip_request
                    clear_skip_request()
                    return
            except Exception as e:
                print(f"  ⚠ Skip check error: {e}")

            self._stop_event.wait(timeout=self.check_interval)


class StopChecker:
    """
    Background thread that polls the backend for stop requests and interrupts the subprocess.
    Unlike SkipChecker (which is per-step), this checks the job-level stopRequested flag.
    This ensures long-running steps (like Echidna) get killed when the user clicks Stop.
    """

    def __init__(self, check_interval: int = 10):
        self.check_interval = check_interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._was_stopped = False

    @property
    def was_stopped(self) -> bool:
        return self._was_stopped

    def start(self):
        """Start the stop checker thread."""
        self._thread = threading.Thread(target=self._check_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the checker thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _check_loop(self):
        """Poll the backend for stopRequested."""
        from server.jobs import check_stop_requested

        api_url = os.environ.get('WORKER_API_URL')
        bearer_token = os.environ.get('WORKER_BEARER_TOKEN')
        job_id = os.environ.get('WORKER_JOB_ID')

        if not all([api_url, bearer_token, job_id]):
            return

        while not self._stop_event.is_set():
            try:
                if check_stop_requested(api_url, bearer_token, job_id):
                    print(f"  ⏹️  Stop requested — killing running process")
                    self._was_stopped = True
                    interrupt_current_process()
                    return
            except Exception as e:
                print(f"  ⚠ Stop check error: {e}")

            self._stop_event.wait(timeout=self.check_interval)


def run_ai_command_with_progress(
    cmd: str,
    log_file: Path,
    model_type: str,
    env: dict,
    step: TaskStep | None = None,
    step_id: str | None = None,
    stale_timeout: int = 600,  # 10 minutes default
) -> int:
    """
    Run an AI command (OPENCODE/CLAUDE_CODE) with automatic progress monitoring.

    Args:
        cmd: Command to execute
        log_file: Path to the log file being written by tee
        model_type: "OPENCODE" or "CLAUDE_CODE"
        env: Environment variables
        step: Optional TaskStep for skip checking
        step_id: Optional step ID for skip checking
        stale_timeout: Seconds without log updates before considering process stale

    Returns:
        int: Return code from the command (STALE=200 if process went stale)
    """
    skip_checker = None
    stop_checker = None
    log_monitor = None

    try:
        # Always start stop checker so long-running AI steps can be killed
        stop_checker = StopChecker(check_interval=10)
        stop_checker.start()

        # Start skip checker if step is skippable
        if step and step.canSkip and step_id:
            skip_checker = SkipChecker(step_id, check_interval=5)
            skip_checker.start()
            print(f"  ⏭️  Skip checking enabled for step {step_id}")

        # Start log monitor for AI progress (always enabled for AI steps)
        # OPENCODE uses JSON output, needs special parser for todowrite events
        # CLAUDE_CODE uses stream-json, can use regex on parsed output
        if model_type == "OPENCODE":
            from worker import send_live_progress
            log_monitor = OpenCodeLogMonitor(
                log_file=str(log_file),
                interval=5,
                progress_callback=send_live_progress,
                stale_timeout=stale_timeout
            )
            log_monitor.start()
            print(f"  📊 AI progress monitoring enabled (every 5s, stale timeout: {stale_timeout}s)")
        # CLAUDE_CODE - TODO: add progress monitoring if needed

        # Resolve CWD: prefer RECON_FOUNDRY_ROOT so Python tools inherit the correct working directory
        _cwd = (env.get('RECON_FOUNDRY_ROOT') or env.get('RECON_REPO_PATH')) if env else None

        # Run the command with Popen for interruptibility
        process = subprocess.Popen(
            cmd,
            shell=True,
            env=env,
            text=True,
            cwd=_cwd,
            start_new_session=True
        )
        set_current_process(process)

        # Poll for completion while checking for staleness
        while True:
            return_code = process.poll()
            if return_code is not None:
                break

            # Check if process went stale (no log output for stale_timeout)
            if log_monitor and log_monitor.is_stale:
                print(f"  🔄 Killing stale AI process (no activity for {stale_timeout}s)")
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                except ProcessLookupError:
                    pass
                process.wait(timeout=10)  # Give it time to die
                return STALE

            time.sleep(1)  # Check every second

        # Check if we were stopped (takes priority)
        if stop_checker and stop_checker.was_stopped:
            print(f"  ⏹️  Step was stopped by user request")
            return STOPPED

        # Check if we were skipped
        if skip_checker and skip_checker.was_skipped:
            print(f"  ⏭️  Step was skipped by user request")
            return SKIPPED

        return return_code

    finally:
        set_current_process(None)
        if stop_checker:
            stop_checker.stop()
        if skip_checker:
            skip_checker.stop()
        if log_monitor:
            log_monitor.stop()


def run_with_monitoring(
    cmd: str,
    step: TaskStep,
    step_id: str | None,
    env: dict,
    shell: bool = True,
    text: bool = True,
    capture_output: bool = False
) -> tuple[int, bool, bool, str | None, str | None]:
    """
    Run a command with optional skip checking, stop checking, and log monitoring.
    Works identically to subprocess.run but with monitoring/skip/stop support.

    Args:
        cmd: Command to execute
        step: TaskStep with canSkip, logFile, logInterval, logRegex settings
        step_id: Internal step ID (for skip checking)
        env: Environment variables
        shell: Run as shell command
        text: Text mode for output
        capture_output: Whether to capture stdout/stderr

    Returns:
        tuple[int, bool, bool, str | None, str | None]: (return_code, was_skipped, was_stopped, stdout, stderr)
    """
    skip_checker = None
    stop_checker = None
    log_monitor = None
    was_skipped = False
    was_stopped = False
    stdout_data = None
    stderr_data = None

    try:
        # Always start stop checker so long-running steps (like Echidna) can be killed
        stop_checker = StopChecker(check_interval=10)
        stop_checker.start()

        # Start skip checker if step is skippable
        if step.canSkip and step_id:
            skip_checker = SkipChecker(step_id, check_interval=5)
            skip_checker.start()
            print(f"  ⏭️  Skip checking enabled for step {step_id}")

        # Start log monitor if configured
        if step.logFile:
            # Resolve log file path relative to foundry root
            foundry_root = os.environ.get('RECON_FOUNDRY_ROOT') or os.environ.get('RECON_REPO_PATH', '.')
            log_path = os.path.join(foundry_root, step.logFile)

            from worker import send_live_progress

            log_monitor = LogMonitor(
                log_file=log_path,
                interval=step.logInterval,
                regex_pattern=step.logRegex,
                progress_callback=send_live_progress
            )
            log_monitor.start()
            print(f"  📊 Log monitoring enabled: {step.logFile} (every {step.logInterval}s)")

        # Resolve CWD: prefer RECON_FOUNDRY_ROOT so Python tools inherit the correct working directory
        _cwd = (env.get('RECON_FOUNDRY_ROOT') or env.get('RECON_REPO_PATH')) if env else None

        # Run the command with Popen for interruptibility
        process = subprocess.Popen(
            cmd,
            shell=shell,
            env=env,
            text=text,
            cwd=_cwd,
            stdout=subprocess.PIPE if capture_output else None,
            stderr=subprocess.PIPE if capture_output else None,
            start_new_session=True  # Create new process group for clean signal handling
        )
        set_current_process(process)

        # Wait for completion and capture output if requested
        if capture_output:
            stdout_data, stderr_data = process.communicate()
            return_code = process.returncode
        else:
            return_code = process.wait()

        # Check if we were stopped (takes priority over skip)
        if stop_checker and stop_checker.was_stopped:
            was_stopped = True
            return_code = STOPPED

        # Check if we were skipped
        elif skip_checker and skip_checker.was_skipped:
            was_skipped = True
            # Return code might be non-zero due to SIGINT, but we treat it as success
            return_code = SKIPPED

        return (return_code, was_skipped, was_stopped, stdout_data, stderr_data)

    finally:
        set_current_process(None)
        if stop_checker:
            stop_checker.stop()
        if skip_checker:
            skip_checker.stop()
        if log_monitor:
            log_monitor.stop()


def resolve_model_string(model_type: str, model_string: str) -> str:
    """
    Resolve the model string, handling 'inherit' and shorthand names like 'opus', 'sonnet', 'haiku'.

    Args:
        model_type: The model type (CLAUDE_CODE, OPENCODE, etc.)
        model_string: The model string from the workflow (may be "inherit", "opus", "sonnet", "haiku", or full model name)

    Returns:
        str: The resolved model string to use in commands
    """
    model_lower = model_string.lower()

    # Model shorthand mappings per model type
    CLAUDE_CODE_MODELS = {
        "inherit": "sonnet",
        "opus": "opus",
        "sonnet": "sonnet",
        "haiku": "haiku",
    }

    OPENCODE_MODELS = {
        "inherit": "openrouter/anthropic/claude-opus-4.6",
        "opus": "openrouter/anthropic/claude-opus-4.6",
        "sonnet": "openrouter/anthropic/claude-sonnet-4.6",
        "haiku": "openrouter/anthropic/claude-haiku-4.5",
    }

    # Resolve based on model type, fall back to default if not found
    if model_type == ModelType.CLAUDE_CODE:
        return CLAUDE_CODE_MODELS.get(model_lower, CLAUDE_CODE_MODELS["inherit"])
    elif model_type == ModelType.OPENCODE:
        return OPENCODE_MODELS.get(model_lower, OPENCODE_MODELS["inherit"])
    else:
        ## TODO: This feels odd. Prob throw on misconfig?
        return OPENCODE_MODELS.get(model_lower, OPENCODE_MODELS["inherit"])  # Default to OPENCODE for unknown types


def resolve_path_template(path_template: str, step_num: int, tool_data: dict | None = None) -> Path:
    """
    Resolve path template with placeholders.

    Args:
        path_template: Path string with optional placeholders like {timestamp}, {step_num}, or {field.path}
        step_num: Current step number
        tool_data: Optional tool output data for extracting values

    Returns:
        Resolved Path object
    """
    path = path_template

    # Replace {timestamp} from tool_data
    if "{timestamp}" in path:
        timestamp = None
        if tool_data and isinstance(tool_data, dict):
            # Extract timestamp from tool data
            timestamp = tool_data.get("timestamp")

        if timestamp:
            path = path.replace("{timestamp}", str(timestamp))

    # Replace {step_num} with step number
    path = path.replace("{step_num}", str(step_num))

    # Replace field paths like {field.name} with values from tool_data
    if tool_data and isinstance(tool_data, dict):
        # Match patterns like {field.name} or {summary.count}
        field_pattern = re.compile(r'\{([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\}')

        def replace_field(match):
            field_path = match.group(1)
            parts = field_path.split('.')

            # Navigate through nested dict
            value = tool_data
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    # Field not found, keep placeholder
                    return match.group(0)

            return str(value)

        path = field_pattern.sub(replace_field, path)

    return Path(path)


def execute_task_step(step: TaskStep, step_num: int, step_id: str | None = None) -> tuple[int, str, str | None, str | None]:
    """
    Execute a task step based on its model type.

    Args:
        step: The task step to execute
        step_num: Step number for logging
        step_id: Optional internal step ID (e.g., "audit:3") for skip checking

    Returns:
        tuple[int, str, str | None, str | None]: (return_code, action, destination_step_name, failure_tail)
            - For task steps, destination_step_name is always None
            - failure_tail contains last 10 lines of output for failed PROGRAM steps, None otherwise
    """

    ## NOTE: Use ${RECON_FRAMEWORK_ROOT} to reference framework programs
    ## Example: ${RECON_FRAMEWORK_ROOT}/programs/my_script.py
    if step.model.type == ModelType.PROGRAM:
        command = step.prompt
        framework_root = os.environ.get('RECON_FRAMEWORK_ROOT')

        # Expand ${RECON_FRAMEWORK_ROOT} placeholder
        if framework_root and '${RECON_FRAMEWORK_ROOT}' in command:
            command = command.replace('${RECON_FRAMEWORK_ROOT}', framework_root)

        # For PROGRAM commands (forge, echidna, etc.), use RECON_FOUNDRY_ROOT
        # This handles monorepos where foundry.toml is in a subdirectory
        # Falls back to RECON_REPO_PATH for backwards compatibility
        foundry_root = os.environ.get('RECON_FOUNDRY_ROOT') or os.environ.get('RECON_REPO_PATH')
        if foundry_root:
            command = f"cd {foundry_root} && {command}"

        # Always capture output for PROGRAM steps to get failure tail
        # Also respect explicit capture config for saving output
        capture_output = True

        # Always use run_with_monitoring so stop checker can kill long-running processes (e.g. Echidna)
        return_code, was_skipped, was_stopped, stdout, stderr = run_with_monitoring(
            command, step, step_id, env=os.environ.copy(),
            shell=True, text=True, capture_output=capture_output
        )
        if was_stopped:
            print(f"  ⏹️  Step was stopped by user request")
            return (STOPPED, "STOPPED", None, None)
        if was_skipped:
            print(f"  ⏭️  Step was skipped by user request")
            return (SUCCESS, "SKIPPED", None, None)

        # Unified error handling
        if return_code != 0:
            print(f"  ❌ Command failed with exit code {return_code}")
            if stdout:
                print(f"  📤 stdout:\n{stdout}")
            if stderr:
                print(f"  📤 stderr:\n{stderr}")

            # Build failure tail from last 10 lines of combined output
            failure_tail = None
            combined_output = ""
            if stdout:
                combined_output += stdout
            if stderr:
                combined_output += "\n" + stderr if combined_output else stderr
            if combined_output:
                lines = combined_output.strip().split('\n')
                failure_tail = '\n'.join(lines[-10:])

            if hasattr(step, 'allowFailure') and step.allowFailure:
                print(f"  ⚠️  Continuing despite failure (allowFailure is enabled)")
                return (SUCCESS, "CONTINUE", None, None)
            return (FAILURE, "CONTINUE", None, failure_tail)

        # Unified output handling
        if step.output and step.output.capture and step.output.save_to:
            try:
                output_data = json.loads(stdout)
                save_path = resolve_path_template(step.output.save_to, step_num, output_data)
                save_path = resolve_file_path(save_path)
                save_path.parent.mkdir(parents=True, exist_ok=True)

                with open(save_path, 'w') as f:
                    if isinstance(output_data, dict) and 'data' in output_data:
                        json.dump(output_data['data'], f, indent=2)
                    else:
                        json.dump(output_data, f, indent=2)

                print(f"  💾 Output saved to: {save_path}")

            except json.JSONDecodeError as e:
                print(f"  ❌ Error: Failed to parse JSON output: {e}")
                if stdout:
                    print(f"  📤 stdout received:\n{stdout}")
                return (FAILURE, "CONTINUE", None, None)
            except Exception as e:
                print(f"  ❌ Error: Failed to save output: {e}")
                return (FAILURE, "CONTINUE", None, None)

        return (SUCCESS, "CONTINUE", None, None)

    ## AI Models
    # Get framework root for later use
    framework_root = os.environ.get('RECON_FRAMEWORK_ROOT', '.')

    # Create logs directory - use custom logs dir if provided, otherwise framework logs/
    logs_dir_override = os.environ.get('RECON_LOGS_DIR')
    if logs_dir_override:
        logs_dir = Path(logs_dir_override).resolve()
    else:
        logs_dir = (Path(framework_root) / "logs").resolve()
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Build the command with extended timeouts and streaming output
    env = os.environ.copy()
    env['BASH_DEFAULT_TIMEOUT_MS'] = '214748364'
    env['BASH_MAX_TIMEOUT_MS'] = '214748364'
    # Remove CLAUDECODE so nested claude invocations are allowed
    env.pop('CLAUDECODE', None)

    # Generate log filename with timestamp and step name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Sanitize step name: remove/replace all special characters
    safe_step_name = re.sub(r'[^a-z0-9_-]', '_', step.name.lower().replace(" ", "_"))
    log_file = logs_dir / f"{timestamp}_step{step_num}_{safe_step_name}.log"

    if step.model.type == ModelType.CLAUDE_CODE:
        # Resolve the model string (handle "inherit")
        resolved_model = resolve_model_string(step.model.type, step.model.model)

        # Check if we should skip permissions (only in production)
        runner_env = os.environ.get('RUNNER_ENV', '').lower()
        skip_permissions = '--dangerously-skip-permissions' if runner_env == 'production' else ''

        # Create the full pipeline command using shlex for proper escaping
        # We'll write the parser script to a temp file to avoid quoting issues
        parser_script_file = Path(framework_root) / 'log_formatters' / 'claude_code.py'

        # Process prompt - if it references an agent file, read and inject its content
        prompt = step.prompt

        agent_file_match = re.search(r'\./(?:\.opencode|prompts)/(agents?)/([^.\s]+)\.md', prompt)
        if agent_file_match:
            # Resolve agent file from PROMPTS_DIR
            prompts_dir = os.environ.get('PROMPTS_DIR', str(Path(framework_root) / 'prompts'))
            agent_file_path = Path(prompts_dir) / agent_file_match.group(1) / f"{agent_file_match.group(2)}.md"
            if agent_file_path.exists():
                print(f"  Loading agent definition from: {agent_file_path}")
                agent_content = agent_file_path.read_text()
                # Extract content after frontmatter (between --- markers)
                parts = agent_content.split('---', 2)
                if len(parts) >= 3:
                    # Use everything after the second ---
                    prompt = parts[2].strip()
                else:
                    # No frontmatter, use full content
                    prompt = agent_content
            else:
                print(f"  ⚠ Agent file not found: {agent_file_path}")

        # If repo_path is set, prefix command to cd there first
        # Use RECON_FOUNDRY_ROOT (where foundry.toml lives) with fallback to RECON_REPO_PATH
        repo_path = os.environ.get('RECON_FOUNDRY_ROOT') or os.environ.get('RECON_REPO_PATH')
        cd_prefix = f"cd {repo_path} && " if repo_path else ""

        cmd = f"""{cd_prefix}claude {skip_permissions} \
-p {shlex.quote(prompt)} \
--model {resolved_model} \
--max-turns 9999999999 \
--output-format stream-json \
--verbose 2>&1 | tee {log_file} | python3 -u {parser_script_file}"""

        print(f"📝 Logging to: {log_file}\n")

        # Retry loop for stale AI processes
        max_retries = 3
        for attempt in range(max_retries):
            if attempt > 0:
                print(f"\n  🔄 Retrying stale AI step (attempt {attempt + 1}/{max_retries})")

            # Always use AI progress monitoring for Claude Code steps
            return_code = run_ai_command_with_progress(
                cmd=cmd,
                log_file=log_file,
                model_type="CLAUDE_CODE",
                env=env,
                step=step,
                step_id=step_id
            )

            if return_code == STALE and attempt < max_retries - 1:
                print(f"  ⚠️  AI process went stale, will retry...")
                continue

            break  # Exit retry loop on success, skip, failure, or final attempt

        if return_code == STOPPED:
            return (STOPPED, "STOPPED", None, None)
        if return_code == SKIPPED:
            return (SUCCESS, "SKIPPED", None, None)
        if return_code == STALE:
            print(f"  ❌ Claude Code execution went stale after {max_retries} retries")
            return (FAILURE, "STALE_FAILED", None, None)
        if return_code != 0:
            print(f"  ❌ Claude Code execution failed with exit code {return_code}")
            return (FAILURE, "CONTINUE", None, None)

        return (SUCCESS, "CONTINUE", None, None)

    if step.model.type == ModelType.OPENCODE:
        # Resolve the model string (handle "inherit")
        resolved_model = resolve_model_string(step.model.type, step.model.model)

        parser_script_file = Path(framework_root) / 'log_formatters' / 'opencode.py'

        # Process prompt - if it references an agent file, read and inject its content
        prompt = step.prompt
        agent_file_match = re.search(r'\./(?:\.opencode|prompts)/(agents?)/([^.\s]+)\.md', prompt)
        if agent_file_match:
            # Resolve agent file from PROMPTS_DIR
            prompts_dir = os.environ.get('PROMPTS_DIR', str(Path(framework_root) / 'prompts'))
            agent_file_path = Path(prompts_dir) / agent_file_match.group(1) / f"{agent_file_match.group(2)}.md"
            if agent_file_path.exists():
                print(f"  Loading agent definition from: {agent_file_path}")
                agent_content = agent_file_path.read_text()
                # Extract content after frontmatter (between --- markers)
                parts = agent_content.split('---', 2)
                if len(parts) >= 3:
                    # Use everything after the second ---
                    prompt = parts[2].strip()
                else:
                    # No frontmatter, use full content
                    prompt = agent_content
            else:
                print(f"  ⚠ Agent file not found: {agent_file_path}")

        # If repo_path is set, prefix command to cd there first
        # Use RECON_FOUNDRY_ROOT (where foundry.toml lives) with fallback to RECON_REPO_PATH
        repo_path = os.environ.get('RECON_FOUNDRY_ROOT') or os.environ.get('RECON_REPO_PATH')
        cd_prefix = f"cd {repo_path} && " if repo_path else ""

        # Pass OPENROUTER_API_KEY inline to work around auth bug
        openrouter_key = os.environ.get('OPENROUTER_API_KEY', '')
        key_prefix = f"OPENROUTER_API_KEY={openrouter_key} " if openrouter_key else ""

        cmd = f"""{cd_prefix}{key_prefix}opencode run  \
{shlex.quote(prompt)} \
--model {resolved_model} \
--format json 2>&1 | tee {shlex.quote(str(log_file))} | python3 -u {shlex.quote(str(parser_script_file))}"""

        print(f"📝 Logging to: {log_file}\n")

        # Retry loop for stale AI processes
        max_retries = 3
        for attempt in range(max_retries):
            if attempt > 0:
                print(f"\n  🔄 Retrying stale AI step (attempt {attempt + 1}/{max_retries})")

            # Always use AI progress monitoring for OpenCode steps
            return_code = run_ai_command_with_progress(
                cmd=cmd,
                log_file=log_file,
                model_type="OPENCODE",
                env=env,
                step=step,
                step_id=step_id
            )

            if return_code == STALE and attempt < max_retries - 1:
                print(f"  ⚠️  AI process went stale, will retry...")
                continue

            break  # Exit retry loop on success, skip, failure, or final attempt

        if return_code == STOPPED:
            return (STOPPED, "STOPPED", None, None)
        if return_code == SKIPPED:
            return (SUCCESS, "SKIPPED", None, None)
        if return_code == STALE:
            print(f"  ❌ OpenCode execution went stale after {max_retries} retries")
            return (FAILURE, "STALE_FAILED", None, None)
        if return_code != 0:
            print(f"  ❌ OpenCode execution failed with exit code {return_code}")
            return (FAILURE, "CONTINUE", None, None)

        return (SUCCESS, "CONTINUE", None, None)

    if step.model.type == ModelType.DISPATCH_FUZZING_JOB:
        """
        Dispatch a fuzzing job to the backend.
        Reads worker context from environment variables.
        """
        import requests

        # Get worker context from environment
        api_url = os.environ.get('WORKER_API_URL')
        bearer_token = os.environ.get('WORKER_BEARER_TOKEN')
        job_id = os.environ.get('WORKER_JOB_ID')

        if not all([api_url, bearer_token, job_id]):
            print("  ❌ Missing worker context (WORKER_API_URL, WORKER_BEARER_TOKEN, WORKER_JOB_ID)")
            print("     This step only works when running inside a ClaudeJob worker.")
            return (FAILURE, "CONTINUE", None, None)

        # Build dispatch config from step config or defaults
        config = step.dispatchConfig or DispatchConfig()

        # Determine the directory for the fuzzing job
        # Priority: 1) Explicit config, 2) RECON_FOUNDRY_ROOT relative path, 3) let backend default
        directory = config.directory
        if directory is None:
            # Check if we have a foundry root that differs from repo root
            foundry_root = os.environ.get('RECON_FOUNDRY_ROOT')
            repo_path = os.environ.get('RECON_REPO_PATH')
            if foundry_root and repo_path and foundry_root != repo_path:
                # Compute relative path from repo root to foundry root
                try:
                    directory = os.path.relpath(foundry_root, repo_path)
                    print(f"  📁 Detected monorepo: foundry root at '{directory}'")
                except ValueError:
                    # On Windows, relpath can fail if paths are on different drives
                    pass

        # Only include fields that are explicitly set - backend applies all defaults
        payload = {}
        if config.fuzzerType is not None:
            payload["fuzzerType"] = config.fuzzerType
        if config.duration is not None:
            payload["duration"] = config.duration
        if directory is not None:
            payload["directory"] = directory
        if config.fuzzerArgs is not None:
            payload["fuzzerArgs"] = config.fuzzerArgs
        if config.label is not None:
            payload["label"] = config.label

        # The API URL is like: https://api.example.com/claude/jobs/worker
        # We need to call: POST /claude/jobs/worker/{jobId}/dispatch-fuzzing
        dispatch_url = f"{api_url}/{job_id}/dispatch-fuzzing"

        print(f"  🚀 Dispatching fuzzing job (backend applies defaults)...")
        if payload:
            print(f"     Overrides: {payload}")

        try:
            headers = {
                "Authorization": f"Bearer {bearer_token}",
                "Content-Type": "application/json"
            }

            response = requests.post(dispatch_url, headers=headers, json=payload)
            response.raise_for_status()

            result_data = response.json()
            data = result_data.get("data", {})

            print(f"  ✓ Fuzzing job dispatched successfully!")
            print(f"     Job ID: {data.get('jobId')}")
            print(f"     Status: {data.get('status')}")
            print(f"     Fuzzer: {data.get('fuzzer')}")

            return (SUCCESS, "CONTINUE", None, None)

        except requests.exceptions.HTTPError as e:
            error_body = ""
            try:
                error_body = e.response.json().get("message", str(e))
            except:
                error_body = str(e)
            print(f"  ❌ Failed to dispatch fuzzing job: {error_body}")
            return (FAILURE, "CONTINUE", None, None)
        except Exception as e:
            print(f"  ❌ Error dispatching fuzzing job: {e}")
            return (FAILURE, "CONTINUE", None, None)

    else:
        print(f"Skipping {step.name}: Model type {step.model.type} not supported yet")
        return (SUCCESS, "CONTINUE", None, None)
