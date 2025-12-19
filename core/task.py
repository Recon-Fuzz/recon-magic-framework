"""
Task execution module for workflow steps.
"""

import json
import os
import shlex
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

# Exit codes
SUCCESS = 0
FAILURE = 1


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
    """Configuration for DISPATCH_FUZZING_JOB steps."""
    fuzzerType: str = "echidna"
    duration: int = 1800  # 30 minutes default
    directory: str = "."
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


def resolve_model_string(model_type: str, model_string: str) -> str:
    """
    Resolve the model string, handling 'inherit' by returning appropriate defaults.

    Args:
        model_type: The model type (CLAUDE_CODE, OPENCODE, etc.)
        model_string: The model string from the workflow (may be "inherit")

    Returns:
        str: The resolved model string to use in commands
    """
    if model_string.lower() != "inherit":
        return model_string

    # Handle inherit based on model type
    if model_type == ModelType.CLAUDE_CODE:
        return "sonnet"
    elif model_type == ModelType.OPENCODE:
        return "openrouter/anthropic/claude-sonnet-4.5"
    else:
        return model_string  # For PROGRAM or unknown types, return as-is


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
    from datetime import datetime
    import re

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


def execute_task_step(step: TaskStep, step_num: int) -> tuple[int, str, str | None]:
    """
    Execute a task step based on its model type.

    Returns:
        tuple[int, str, str | None]: (return_code, action, destination_step_name)
            - For task steps, destination_step_name is always None
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

        # Check if we need to capture output
        capture_output = step.output and step.output.capture

        # Run the program
        result = subprocess.run(
            command,
            shell=True,
            env=os.environ.copy(),
            capture_output=capture_output,
            text=True if capture_output else False
        )

        # Check if the command failed
        if result.returncode != 0:
            error_msg = f"  ❌ Command failed with exit code {result.returncode}"
            print(error_msg)
            if capture_output:
                if result.stdout:
                    print(f"  📤 stdout:\n{result.stdout}")
                if result.stderr:
                    print(f"  📤 stderr:\n{result.stderr}")

            # If allowFailure is set, continue despite the failure
            if hasattr(step, 'allowFailure') and step.allowFailure:
                print(f"  ⚠️  Continuing despite failure (allowFailure is enabled)")
                return (SUCCESS, "CONTINUE", None)

            return (FAILURE, "CONTINUE", None)

        # Handle output if configured
        if capture_output and step.output and step.output.save_to:
            try:
                # Parse JSON output from stdout
                output_data = json.loads(result.stdout)

                # Resolve the save path using tool output data for placeholders
                save_path = resolve_path_template(step.output.save_to, step_num, output_data)

                # Make save_path absolute relative to RECON_FOUNDRY_ROOT (not Python's cwd)
                # This ensures files are saved in the foundry project root (handles monorepos)
                # Falls back to RECON_REPO_PATH for non-monorepo cases
                foundry_root = os.environ.get('RECON_FOUNDRY_ROOT') or os.environ.get('RECON_REPO_PATH')
                if foundry_root and not save_path.is_absolute():
                    save_path = Path(foundry_root) / save_path

                # Ensure directory exists
                save_path.parent.mkdir(parents=True, exist_ok=True)

                # Write the output
                with open(save_path, 'w') as f:
                    # If output has a 'data' field, write that; otherwise write everything
                    if isinstance(output_data, dict) and 'data' in output_data:
                        json.dump(output_data['data'], f, indent=2)
                    else:
                        json.dump(output_data, f, indent=2)

                print(f"  💾 Output saved to: {save_path}")

            except json.JSONDecodeError as e:
                print(f"  ❌ Error: Failed to parse JSON output: {e}")
                if result.stdout:
                    print(f"  📤 stdout received:\n{result.stdout}")
                return (FAILURE, "CONTINUE", None)
            except Exception as e:
                print(f"  ❌ Error: Failed to save output: {e}")
                return (FAILURE, "CONTINUE", None)

        return (SUCCESS, "CONTINUE", None)

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

    # Generate log filename with timestamp and step name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Sanitize step name: remove/replace all special characters
    import re
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
        import re
        agent_file_match = re.search(r'\./(\.opencode|\.claude)/(agents?)/([^.\s]+)\.md', prompt)
        if agent_file_match:
            # Try /app first (worker/Docker), fall back to framework_root (local dev)
            # Preserve the actual directory name (agent or agents) from the match
            agent_rel_path = Path(agent_file_match.group(1)) / agent_file_match.group(2) / f"{agent_file_match.group(3)}.md"
            agent_file_path = Path("/app") / agent_rel_path
            if not agent_file_path.exists():
                agent_file_path = Path(framework_root) / agent_rel_path
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
        repo_path = os.environ.get('RECON_REPO_PATH')
        cd_prefix = f"cd {repo_path} && " if repo_path else ""

        cmd = f"""{cd_prefix}claude {skip_permissions} \
-p {shlex.quote(prompt)} \
--model {resolved_model} \
--max-turns 9999999999 \
--output-format stream-json \
--verbose 2>&1 | tee {log_file} | python3 -u {parser_script_file}"""

        print(f"📝 Logging to: {log_file}\n")

        # Execute the command
        result = subprocess.run(
            cmd,
            shell=True,
            env=env,
            text=True
        )

        if result.returncode != 0:
            print(f"  ❌ Claude Code execution failed with exit code {result.returncode}")
            return (FAILURE, "CONTINUE", None)

        return (SUCCESS, "CONTINUE", None)

    if step.model.type == ModelType.OPENCODE:
        # Resolve the model string (handle "inherit")
        resolved_model = resolve_model_string(step.model.type, step.model.model)

        parser_script_file = Path(framework_root) / 'log_formatters' / 'opencode.py'

        # Process prompt - if it references an agent file, read and inject its content
        prompt = step.prompt
        import re
        agent_file_match = re.search(r'\./(\.opencode|\.claude)/(agents?)/([^.\s]+)\.md', prompt)
        if agent_file_match:
            # Try /app first (worker/Docker), fall back to framework_root (local dev)
            # Preserve the actual directory name (agent or agents) from the match
            agent_rel_path = Path(agent_file_match.group(1)) / agent_file_match.group(2) / f"{agent_file_match.group(3)}.md"
            agent_file_path = Path("/app") / agent_rel_path
            if not agent_file_path.exists():
                agent_file_path = Path(framework_root) / agent_rel_path
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
        repo_path = os.environ.get('RECON_REPO_PATH')
        cd_prefix = f"cd {repo_path} && " if repo_path else ""

        # Pass OPENROUTER_API_KEY inline to work around auth bug
        openrouter_key = os.environ.get('OPENROUTER_API_KEY', '')
        key_prefix = f"OPENROUTER_API_KEY={openrouter_key} " if openrouter_key else ""

        cmd = f"""{cd_prefix}{key_prefix}opencode run  \
{shlex.quote(prompt)} \
--model {resolved_model} \
--format json 2>&1 | tee {shlex.quote(str(log_file))} | python3 -u {shlex.quote(str(parser_script_file))}"""

        print(f"📝 Logging to: {log_file}\n")

        result = subprocess.run(
            cmd,
            shell=True,
            env=env,
            text=True
        )

        if result.returncode != 0:
            print(f"  ❌ OpenCode execution failed with exit code {result.returncode}")
            return (FAILURE, "CONTINUE", None)

        return (SUCCESS, "CONTINUE", None)

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
            return (FAILURE, "CONTINUE", None)

        # Build dispatch config from step config or defaults
        config = step.dispatchConfig or DispatchConfig()

        # Determine the directory for the fuzzing job
        # Priority: 1) Explicit config (if not "."), 2) RECON_FOUNDRY_ROOT relative path, 3) "."
        directory = config.directory
        if directory == ".":
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
                    directory = "."

        payload = {
            "fuzzerType": config.fuzzerType,
            "duration": config.duration,
            "directory": directory,
        }
        if config.fuzzerArgs:
            payload["fuzzerArgs"] = config.fuzzerArgs
        if config.label:
            payload["label"] = config.label

        # The API URL is like: https://api.example.com/claude/jobs/worker
        # We need to call: POST /claude/jobs/worker/{jobId}/dispatch-fuzzing
        dispatch_url = f"{api_url}/{job_id}/dispatch-fuzzing"

        print(f"  🚀 Dispatching fuzzing job...")
        print(f"     Fuzzer: {config.fuzzerType}")
        print(f"     Duration: {config.duration}s")
        print(f"     Directory: {directory}")

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

            return (SUCCESS, "CONTINUE", None)

        except requests.exceptions.HTTPError as e:
            error_body = ""
            try:
                error_body = e.response.json().get("message", str(e))
            except:
                error_body = str(e)
            print(f"  ❌ Failed to dispatch fuzzing job: {error_body}")
            return (FAILURE, "CONTINUE", None)
        except Exception as e:
            print(f"  ❌ Error dispatching fuzzing job: {e}")
            return (FAILURE, "CONTINUE", None)

    else:
        print(f"Skipping {step.name}: Model type {step.model.type} not supported yet")
        return (SUCCESS, "CONTINUE", None)
