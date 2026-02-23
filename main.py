"""
Main workflow execution module.
Use this when using recon-magic framework as a library.
"""

import json
import os
import sys
from enum import Enum
from pathlib import Path
from typing import Annotated, Callable, Union

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from core.decision import DecisionStep, execute_decision_step
from core.task import TaskStep, execute_task_step
from core.git_commit import is_git_repo, init_git_repo, run_command

# Load environment variables from .env file
load_dotenv()

# Exit codes
SUCCESS = 0
FAILURE = 1
STOPPED = 2  # Graceful stop requested

# Default loop hardcap to prevent infinite loops
DEFAULT_LOOP_HARDCAP = 5

# Global gates storage
_workflow_gates: dict[str, dict] = {}


def load_gates(workflows_dir: Path) -> dict[str, dict]:
    """
    Load shared gates from workflow-gates.json.

    Args:
        workflows_dir: Directory containing workflow files

    Returns:
        Dict mapping gate name to gate configuration
    """
    global _workflow_gates

    gates_file = workflows_dir / "workflow-gates.json"
    if not gates_file.exists():
        print("  ℹ️  No workflow-gates.json found, skipping gates loading")
        return {}

    with open(gates_file, 'r') as f:
        data = json.load(f)

    _workflow_gates = data.get("gates", {})
    print(f"  ✓ Loaded {len(_workflow_gates)} gates: {list(_workflow_gates.keys())}")
    return _workflow_gates


class ModelType(str, Enum):
    """Model type enum matching TypeScript ModelType."""
    INHERIT = "INHERIT"
    PROGRAM = "PROGRAM"
    CLAUDE_CODE = "CLAUDE_CODE"
    OPENCODE = "OPENCODE"


class Model(BaseModel):
    """Model configuration."""
    type: ModelType
    model: str


class Step(BaseModel):
    """Base step interface."""
    name: str
    description: str | None = None
    shouldCreateSummary: bool = Field(alias="shouldCreateSummary")
    shouldCommitChanges: bool = Field(alias="shouldCommitChanges")


# Union type for all step types with discriminator
StepType = Annotated[Union[TaskStep, DecisionStep], Field(discriminator="type")]


class Workflow(BaseModel):
    """Workflow configuration."""
    name: str
    steps: list[StepType]


# Internal storage for step metadata (IDs, source workflow)
# Maps step index (1-based) to metadata
_step_metadata: dict[int, dict] = {}


def _get_workflow_key(filepath: str) -> str:
    """Extract a short key from workflow filepath for ID generation."""
    return Path(filepath).stem  # e.g., "workflow-fuzzing-coverage" from full path


def _flatten_workflow_steps(
    steps: list[dict],
    workflows_dir: Path,
    source_file: str,
    visited: set[str] | None = None
) -> list[dict]:
    """
    Recursively flatten workflow steps, inlining any 'workflow' type steps.

    Args:
        steps: List of step dictionaries from JSON
        workflows_dir: Directory containing workflow files
        source_file: Name of the source workflow file (for ID generation)
        visited: Set of already-visited workflow files (for cycle detection)

    Returns:
        Flattened list of steps with internal IDs added
    """
    if visited is None:
        visited = set()

    # Detect cycles
    if source_file in visited:
        raise ValueError(f"Circular workflow reference detected: {source_file}")
    visited.add(source_file)

    workflow_key = _get_workflow_key(source_file)
    flattened = []

    for idx, step in enumerate(steps):
        step_type = step.get("type")

        if step_type == "workflow":
            # This is a workflow reference - inline it
            sub_workflow_file = step.get("workflow_file")
            if not sub_workflow_file:
                raise ValueError(f"Workflow step missing 'workflow_file' field: {step}")

            # Resolve the sub-workflow path
            sub_workflow_path = workflows_dir / sub_workflow_file
            if not sub_workflow_path.exists():
                raise FileNotFoundError(f"Sub-workflow not found: {sub_workflow_path}")

            print(f"  📂 Inlining sub-workflow: {sub_workflow_file}")

            # Load and flatten the sub-workflow
            with open(sub_workflow_path, 'r') as f:
                sub_data = json.load(f)

            sub_steps = _flatten_workflow_steps(
                sub_data.get("steps", []),
                workflows_dir,
                sub_workflow_file,
                visited.copy()  # Copy to allow same workflow in different branches
            )

            flattened.extend(sub_steps)
        else:
            # Regular step - add internal ID metadata
            step_copy = step.copy()
            step_copy["_internal_id"] = f"{workflow_key}:{idx}"
            step_copy["_source_workflow"] = source_file
            flattened.append(step_copy)

    return flattened


def _build_step_metadata(steps: list[dict]) -> dict[int, dict]:
    """
    Build metadata mapping from flattened steps.

    Args:
        steps: Flattened list of step dictionaries

    Returns:
        Dict mapping 1-based step index to metadata
    """
    metadata = {}
    for idx, step in enumerate(steps, start=1):
        metadata[idx] = {
            "internal_id": step.get("_internal_id", f"unknown:{idx}"),
            "source_workflow": step.get("_source_workflow", "unknown"),
            "name": step.get("name", ""),
        }
    return metadata


def _build_name_to_index_map(steps: list[dict]) -> dict[str, list[int]]:
    """
    Build a map from step names to their indices (1-based).
    Names can map to multiple indices if duplicated across sub-workflows.

    Args:
        steps: Flattened list of step dictionaries

    Returns:
        Dict mapping step name to list of 1-based indices
    """
    name_map: dict[str, list[int]] = {}
    for idx, step in enumerate(steps, start=1):
        name = step.get("name", "")
        if name not in name_map:
            name_map[name] = []
        name_map[name].append(idx)
    return name_map


def load_workflow(filepath: str) -> Workflow:
    """
    Load and parse a workflow JSON file with type validation.
    Supports workflow composition via 'workflow' type steps that reference
    other workflow files.

    Args:
        filepath: Path to the workflow.json file

    Returns:
        Workflow: Parsed and validated workflow object

    Raises:
        FileNotFoundError: If the workflow file doesn't exist
        json.JSONDecodeError: If the JSON is malformed
        pydantic.ValidationError: If the data doesn't match the schema
        ValueError: If circular workflow references are detected
    """
    global _step_metadata

    filepath_path = Path(filepath)
    workflows_dir = filepath_path.parent

    with open(filepath, 'r') as f:
        data = json.load(f)

    # Flatten any embedded workflows
    original_steps = data.get("steps", [])
    has_workflow_steps = any(s.get("type") == "workflow" for s in original_steps)

    if has_workflow_steps:
        print(f"🔗 Flattening workflow composition...")
        flattened_steps = _flatten_workflow_steps(
            original_steps,
            workflows_dir,
            filepath_path.name
        )

        # Build metadata before stripping internal fields
        _step_metadata = _build_step_metadata(flattened_steps)

        # Strip internal fields before Pydantic validation
        for step in flattened_steps:
            step.pop("_internal_id", None)
            step.pop("_source_workflow", None)

        data["steps"] = flattened_steps
        print(f"  ✓ Flattened to {len(flattened_steps)} total steps")
    else:
        # No composition - build metadata with proper internal IDs
        workflow_key = _get_workflow_key(filepath)
        for idx, step in enumerate(original_steps):
            step["_internal_id"] = f"{workflow_key}:{idx}"
            step["_source_workflow"] = filepath_path.name
        _step_metadata = _build_step_metadata(original_steps)
        # Strip internal fields before Pydantic validation
        for step in original_steps:
            step.pop("_internal_id", None)
            step.pop("_source_workflow", None)

    return Workflow(**data)

def default_before_step_execution(step: Step, step_num: int, step_id: str | None = None) -> None:
    """
    Default hook that runs before step execution.
    Can be overridden by passing a custom before_hook to run_workflow().
    """
    print(f"Before step {step_num}: {step.name}")
    print(f"Type: {step.type}")
    if hasattr(step, 'model') and step.model:
        print(f"Model: {step.model.type}")
    print(f"Description: {step.description or 'N/A'}")
    print(f"Should create summary: {step.shouldCreateSummary}")
    print(f"Should commit changes: {step.shouldCommitChanges}")


def default_after_step_execution(step: Step, step_num: int, return_code: int, action: str) -> None:
    """
    Default hook that runs after step execution.
    Can be overridden by passing a custom after_hook to run_workflow().
    """
    pass  # Default implementation does nothing


def check_gate_condition(gate: dict) -> bool:
    """
    Check if a gate's success condition is met.

    Args:
        gate: Gate configuration dict

    Returns:
        bool: True if condition is met (gate passes), False otherwise
    """
    from core.path_utils import get_base_path

    condition = gate.get("successCondition", {})
    mode = condition.get("mode")
    mode_info = condition.get("modeInfo", {})
    success_value = condition.get("successValue", 1)  # Default: file exists = success

    if mode == "FILE_EXISTS":
        base_path = get_base_path()
        pattern = mode_info.get("fileName", "")
        matches = list(base_path.glob(pattern))
        actual_value = 1 if matches else 0
        return actual_value == success_value

    # Default: assume pass if no condition specified
    return True


def execute_gate(
    gate_name: str,
    step_num: int
) -> tuple[bool, str | None, str | None]:
    """
    Execute a gate's check and fix cycle.

    Gate steps are executed exactly like regular workflow steps, producing:
    - Logs in the logs directory with step numbering: {step_num}.{gate_step}
    - Git commits if shouldCommitChanges is set
    - Summaries if shouldCreateSummary is set

    Args:
        gate_name: Name of the gate to execute
        step_num: Current step number (for logging)

    Returns:
        tuple[bool, str | None, str | None]: (success, error_message, failure_tail)
            - success: True if gate passed, False if max retries exceeded
            - error_message: Description of failure if gate failed
            - failure_tail: Last output lines from check step (for error reporting)
    """
    global _workflow_gates
    from worker import send_live_progress

    if gate_name not in _workflow_gates:
        print(f"  ❌ Gate '{gate_name}' not found in workflow-gates.json")
        return (False, f"Gate '{gate_name}' not found - check preconditions spelling", None)

    gate = _workflow_gates[gate_name]
    max_retries = gate.get("maxRetries", 2)

    print(f"\n🔒 Executing gate: {gate_name}")
    print(f"   Max retries: {max_retries}")

    # Send gate checking status via liveProgress
    send_live_progress(f"🔐 Gate: {gate_name} checking...")

    # Gate sub-step counter for unique log naming
    gate_sub_step = 0
    last_failure_tail = None

    for attempt in range(max_retries + 1):
        print(f"\n   [Gate attempt {attempt + 1}/{max_retries + 1}]")

        # Execute the check step
        check_step_data = gate.get("check", {})
        if check_step_data:
            gate_sub_step += 1
            # Use decimal step number for gate sub-steps (e.g., 1.1, 1.2)
            gate_step_num = float(f"{step_num}.{gate_sub_step}")

            check_step = TaskStep(**check_step_data)
            print(f"   Running check: {check_step.name}")
            return_code, _, _, failure_tail = execute_task_step(check_step, int(gate_step_num * 10))
            last_failure_tail = failure_tail

            if return_code != SUCCESS and not check_step.allowFailure:
                print(f"   ❌ Check step failed")

        # Evaluate success condition
        if check_gate_condition(gate):
            print(f"   ✅ Gate '{gate_name}' PASSED")
            send_live_progress(f"✅ Gate: {gate_name} passed")
            return (True, None, None)

        print(f"   ❌ Gate condition not met")

        # If we have retries left, run the fix step
        if attempt < max_retries:
            send_live_progress(f"🔧 Gate: {gate_name} fixing (attempt {attempt + 1}/{max_retries})...")
            fix_step_data = gate.get("fix", {})
            if fix_step_data:
                gate_sub_step += 1
                gate_step_num = float(f"{step_num}.{gate_sub_step}")

                fix_step = TaskStep(**fix_step_data)
                print(f"   🔧 Running fix: {fix_step.name}")
                return_code, _, _, _ = execute_task_step(fix_step, int(gate_step_num * 10))

                # Handle artifacts exactly like regular workflow steps
                if fix_step.shouldCreateSummary:
                    create_summary(fix_step, int(gate_step_num * 10))

                if fix_step.shouldCommitChanges:
                    commit_info = commit_changes(fix_step, int(gate_step_num * 10))
                    if commit_info:
                        push_changes(int(gate_step_num * 10))
        else:
            print(f"   ❌ Max retries ({max_retries}) exceeded for gate '{gate_name}'")
            send_live_progress(f"❌ Gate: {gate_name} failed")

            # Execute onFailure handler if defined (e.g., generate failure report)
            on_failure_data = gate.get("onFailure", {})
            if on_failure_data:
                gate_sub_step += 1
                gate_step_num = float(f"{step_num}.{gate_sub_step}")

                on_failure_step = TaskStep(**on_failure_data)
                print(f"\n   📋 Running failure handler: {on_failure_step.name}")
                _, _, _, _ = execute_task_step(on_failure_step, int(gate_step_num * 10))

                # Handle artifacts exactly like regular workflow steps
                if on_failure_step.shouldCreateSummary:
                    create_summary(on_failure_step, int(gate_step_num * 10))

                if on_failure_step.shouldCommitChanges:
                    commit_info = commit_changes(on_failure_step, int(gate_step_num * 10))
                    if commit_info:
                        push_changes(int(gate_step_num * 10))

            return (False, f"Gate '{gate_name}' failed after {max_retries} retries", last_failure_tail)

    return (False, f"Gate '{gate_name}' failed", last_failure_tail)

def execute_step(
    step: Step,
    step_num: int,
    execution_count: int,
    loop_hardcap: int = DEFAULT_LOOP_HARDCAP,
    before_hook: Callable[[Step, int, str | None], None] | None = None,
    step_id: str | None = None,
) -> tuple[int, str, str | None, str | None]:
    """
    Execute a workflow step based on its step type.

    Args:
        step: The step to execute
        step_num: The step number for logging
        execution_count: Number of times this step has been executed
        loop_hardcap: Maximum number of times a decision step can loop
        before_hook: Optional callback to run before step execution (receives step, step_num, step_id)
        step_id: Optional internal step ID (e.g., "audit:3") for skip checking

    Returns:
        tuple[int, str, str | None, str | None]: (Return code, Action, Destination step name, Failure tail)
            - failure_tail contains last 10 lines of output for failed PROGRAM steps, None otherwise
    """
    # Use provided hooks or default ones
    _before_hook = before_hook or default_before_step_execution

    _before_hook(step, step_num, step_id)

    return_code, action, destination, failure_tail = None, None, None, None

    # Check if we've hit the loop hardcap for decision steps
    if isinstance(step, DecisionStep) and execution_count >= loop_hardcap:
        print(f"⚠️  Loop hardcap ({loop_hardcap}) reached for step {step_num}, forcing CONTINUE")
        return_code, action, destination, failure_tail = (SUCCESS, "CONTINUE", None, None)
    else:
        # Switch on step.type first
        if isinstance(step, TaskStep):
            return_code, action, destination, failure_tail = execute_task_step(step, step_num, step_id)
        elif isinstance(step, DecisionStep):
            return_code, action, destination = execute_decision_step(step, step_num)
            failure_tail = None  # Decision steps don't have failure tails
        else:
            print(f"❌ Unknown step type: {type(step)}")
            return_code, action, destination, failure_tail = (FAILURE, "CONTINUE", None, None)

    return (return_code, action, destination, failure_tail)


## TODO: Separate File
def create_summary(step: Step, step_num: int) -> str | None:
    """
    Create a summary for the completed step using Claude.

    Gives Claude full permissions to check git status, git diff, and read
    any new files to generate an accurate summary.

    Args:
        step: The step that was executed
        step_num: The step number for logging

    Returns:
        str | None: The generated summary or None if failed
    """
    print(f"📝 Creating summary for step {step_num}: {step.name}")

    try:
        import subprocess

        # Build the prompt - let Claude explore the changes itself
        prompt = f"""You are summarizing changes made during a workflow step.

Step name: {step.name}
Step description: {step.description or 'N/A'}

Your task:
1. Run `git status` to see what files changed
2. Run `git diff HEAD` to see modifications to tracked files
3. For any new untracked files (shown with ?? in git status), read them to understand what was created
4. Write a 2-3 sentence summary focusing on WHAT was accomplished, not implementation details

Write in first person as if you performed the work (e.g., "I created...", "I updated...").
Return ONLY the summary text, nothing else."""

        # Build command - skip permissions only in production
        cmd = ["claude"]
        runner_env = os.environ.get('RUNNER_ENV', '').lower()
        if runner_env == 'production':
            cmd.append("--dangerously-skip-permissions")
        cmd.extend(["-p", prompt, "--model", "haiku"])

        # IMPORTANT: Must set cwd to repo path, otherwise Claude runs in wrong directory
        repo_path = os.environ.get('RECON_REPO_PATH', '.')

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=repo_path
        )

        if result.returncode == 0 and result.stdout.strip():
            summary = result.stdout.strip()
            print(f"  ✓ Summary: {summary[:100]}...")
            return summary
        else:
            print(f"  ⚠ Failed to generate summary: {result.stderr}")
            return None
    except subprocess.TimeoutExpired:
        print("  ⚠ Summary generation timed out")
        return None
    except Exception as e:
        print(f"  ⚠ Exception generating summary: {e}")
        return None


## TODO: Separate File
def find_step_index_by_name(
    workflow: Workflow,
    step_name: str,
    current_step_index: int | None = None
) -> int | None:
    """
    Find the step index (1-based) by step name, with scoped resolution.

    When workflows are composed, step names may be duplicated across sub-workflows.
    This function first tries to find the step within the same source workflow as
    the current step (scoped lookup), then falls back to global lookup.

    Args:
        workflow: The workflow containing the steps
        step_name: The name of the step to find
        current_step_index: The current step's 1-based index (for scoped resolution)

    Returns:
        int | None: The 1-based index of the step, or None if not found
    """
    global _step_metadata

    # If we have metadata and a current step, try scoped lookup first
    if _step_metadata and current_step_index is not None:
        current_source = _step_metadata.get(current_step_index, {}).get("source_workflow")

        if current_source:
            # First pass: find within same source workflow
            for idx, step in enumerate(workflow.steps, start=1):
                meta = _step_metadata.get(idx, {})
                if step.name == step_name and meta.get("source_workflow") == current_source:
                    return idx

    # Fallback: global lookup (first match)
    for idx, step in enumerate(workflow.steps, start=1):
        if step.name == step_name:
            return idx

    return None


def commit_changes(step: Step, step_num: int) -> dict | None:
    """
    Commit changes made during the step execution.

    Args:
        step: The step that was executed
        step_num: The step number for logging

    Returns:
        dict | None: Commit info with hash, message, files_changed or None if no commit
    """
    print(f"\n💾 Committing changes for step {step_num}: {step.name}")

    # Get repo path from environment (set by run_workflow)
    repo_path = os.environ.get('RECON_REPO_PATH', '.')

    # Check if git repo exists, initialize if not
    if not is_git_repo(repo_path):
        print("  Initializing git repository...")
        if not init_git_repo(repo_path, verbose=False):
            print("  ❌ Failed to initialize git repository")
            return None
        print("  ✓ Git repository initialized successfully")

    # Check if there are any changes to commit
    success, stdout, _ = run_command("git status --porcelain", cwd=repo_path)
    if not success:
        print("  ❌ Failed to check git status")
        return None

    if not stdout:
        print("  ℹ️  No changes to commit")
        return None

    # Get list of changed files before committing
    files_changed = [line.split()[-1] for line in stdout.strip().split('\n') if line]

    # Add all changes
    print("  Adding changes...")
    success, _, stderr = run_command("git add .", cwd=repo_path)
    if not success:
        print(f"  ❌ Failed to add changes: {stderr}")
        return None

    # Commit changes with a descriptive message
    commit_message = f"Step {step_num}: {step.name}"
    if step.description:
        commit_message += f"\n\n{step.description}"

    print(f"  Committing with message: '{commit_message.split(chr(10))[0]}'")

    # Escape single quotes in the message
    escaped_message = commit_message.replace("'", "'\\''")
    success, stdout, stderr = run_command(f"git commit -m '{escaped_message}'", cwd=repo_path)

    if success:
        print("  ✓ Changes committed successfully!")
        # Get the commit hash
        success, commit_hash, _ = run_command("git rev-parse HEAD", cwd=repo_path)
        if success:
            return {
                "commit_hash": commit_hash.strip()[:8],
                "commit_message": commit_message.split('\n')[0],
                "files_changed": files_changed
            }
        return {"commit_message": commit_message.split('\n')[0], "files_changed": files_changed}
    else:
        # Check if the error is due to no changes staged (can happen with .gitignore)
        if "nothing to commit" in stderr or "nothing to commit" in stdout:
            print("  ℹ️  No changes to commit (all changes may be ignored by .gitignore)")
        else:
            print(f"  ❌ Failed to commit changes: {stderr}")
        return None


def push_changes(step_num: int) -> bool:
    """
    Push committed changes to remote.

    Args:
        step_num: The step number for logging

    Returns:
        bool: True if push succeeded, False otherwise
    """
    print(f"  📤 Pushing changes for step {step_num}...")

    # Get repo path from environment (set by run_workflow)
    repo_path = os.environ.get('RECON_REPO_PATH', '.')

    # Check if remote 'recon' exists
    success, stdout, _ = run_command("git remote", cwd=repo_path)
    if not success or "recon" not in stdout:
        print("  ⚠ No 'recon' remote configured, skipping push")
        return False

    success, _, stderr = run_command("git push recon main", cwd=repo_path)
    if success:
        print("  ✓ Changes pushed successfully!")
        return True
    else:
        print(f"  ⚠ Failed to push changes: {stderr}")
        return False


def run_workflow(
    workflow_file: str,
    dangerous: bool = False,
    loop_hardcap: int = DEFAULT_LOOP_HARDCAP,
    logs_dir: str | None = None,
    repo_path: str | None = None,
    before_hook: Callable[[Step, int, str | None], None] | None = None,
    after_hook: Callable[[Step, int, int, str, dict | None], None] | None = None,
    stop_checker: Callable[[], bool] | None = None,
    resume_from_step_id: str | None = None,
    override_gates: list[str] | None = None
) -> int:
    """
    Execute a workflow with explicit parameters.

    Args:
        workflow_file: Path to the workflow JSON file
        dangerous: Enable dangerous mode (skip permissions)
        loop_hardcap: Maximum number of times a decision step can loop
        logs_dir: Directory to store logs (defaults to framework logs/)
        repo_path: Path to cd to for PROGRAM execution (None = run in current dir)
        before_hook: Optional callback to run before each step execution
        after_hook: Optional callback to run after each step execution
        resume_from_step_id: If set, skip steps before the one with this internal ID (e.g., "audit:3")
            - Receives: (step, step_num, return_code, action, step_result)
            - step_result contains: {summary, commit_info, pushed}
        stop_checker: Optional callback to check if graceful stop was requested
            - Called before each step
            - Returns True if stop was requested, False otherwise
        override_gates: Optional list of gate names to run instead of step preconditions
            - Only applies to the resume step (the step matching resume_from_step_id)
            - None = use step's own preconditions (default behavior)
            - [] = skip all gates for the resume step
            - ["gate-name"] = run only the specified gates for the resume step
            - Subsequent steps always use their own preconditions

    Returns:
        Exit code (0 = success, 1 = failure, 2 = stopped)
    """
    # Set environment variables for use by task/decision executors
    if dangerous:
        os.environ['RUNNER_ENV'] = 'production'

    if logs_dir:
        os.environ['RECON_LOGS_DIR'] = logs_dir

    if repo_path:
        os.environ['RECON_REPO_PATH'] = repo_path

    # Load the workflow
    workflow = load_workflow(workflow_file)

    # Load gates from workflow-gates.json
    workflows_dir = Path(workflow_file).parent
    load_gates(workflows_dir)

    print(f"\n{'#'*60}")
    print(f"# Workflow: {workflow.name}")
    print(f"# Number of steps: {len(workflow.steps)}")
    if resume_from_step_id:
        print(f"# Resume from step ID: {resume_from_step_id}")
    print(f"{'#'*60}\n")

    # Resolve resume_from_step_id to flattened index if provided
    resume_from_step: int | None = None
    if resume_from_step_id is not None:
        # Find the flattened index for the given internal_id
        for idx, meta in _step_metadata.items():
            if meta.get("internal_id") == resume_from_step_id:
                resume_from_step = idx
                break

        if resume_from_step is None:
            print(f"❌ Invalid resume step ID: '{resume_from_step_id}' not found in workflow")
            print(f"   Available step IDs:")
            for idx, meta in _step_metadata.items():
                print(f"     {meta.get('internal_id')}: {meta.get('name')}")
            return FAILURE

        print(f"🔄 Resuming workflow from step ID '{resume_from_step_id}'")
        print(f"   Resolved to flattened step {resume_from_step}: {workflow.steps[resume_from_step - 1].name}")
        print(f"   Skipping steps 1-{resume_from_step - 1}\n")

    # In-memory cache to track step execution counts
    step_execution_count: dict[int, int] = {}

    # Execute each step
    i = 1
    while i <= len(workflow.steps):
        step = workflow.steps[i - 1]

        # Skip steps if resuming from a later step
        if resume_from_step and i < resume_from_step:
            print(f"⏩ Skipping step {i}/{len(workflow.steps)}: {step.name}")
            i += 1
            continue

        # Check for graceful stop request before executing each step
        if stop_checker and stop_checker():
            print(f"\n⏹️  Graceful stop requested before step {i}: {step.name}")
            print("Stopping workflow execution gracefully.")

            # Call after_hook to notify about the stop
            if after_hook:
                step_result = {"step_name": step.name, "step_num": i, "stopped": True}
                # Add internal_id for resume functionality
                if i in _step_metadata:
                    step_result["internal_id"] = _step_metadata[i].get("internal_id")
                after_hook(step, i, STOPPED, "GRACEFUL_STOP", step_result)

            return STOPPED

        # Track execution count for this step
        if i not in step_execution_count:
            step_execution_count[i] = 0
        step_execution_count[i] += 1

        # Get step_id early - needed for phase update and skip checking
        step_id = _step_metadata.get(i, {}).get("internal_id") if _step_metadata else None

        print(f"\n[Step {i}/{len(workflow.steps)}] {step.name} (execution #{step_execution_count[i]})")
        print(f"Type: {step.type}")
        if hasattr(step, 'model') and step.model:
            print(f"Model: {step.model.type}")

        # Update current phase BEFORE running gates (so UI shows correct step)
        if before_hook:
            before_hook(step, i, step_id)

        # Determine which gates to run for this step
        if override_gates is not None and resume_from_step and i == resume_from_step:
            gates_to_run = override_gates  # user override only for the resume step
        elif hasattr(step, 'preconditions') and step.preconditions:
            gates_to_run = step.preconditions  # default behavior
        else:
            gates_to_run = None

        # Check preconditions (gates) if any are defined
        if gates_to_run:
            print(f"\n🔐 Checking preconditions: {gates_to_run}")
            for gate_name in gates_to_run:
                gate_passed, error_msg, gate_failure_tail = execute_gate(gate_name, i)
                if not gate_passed:
                    print(f"\n❌ Gate '{gate_name}' failed for step {i}")
                    print(f"   {error_msg}")
                    print("Stopping workflow execution due to gate failure.")
                    if after_hook:
                        step_result = {"step_name": step.name, "step_num": i, "failed": True, "gate_failed": gate_name}
                        if gate_failure_tail:
                            step_result["failure_tail"] = gate_failure_tail
                        # Add internal_id for resume functionality
                        if i in _step_metadata:
                            step_result["internal_id"] = _step_metadata[i].get("internal_id")
                        after_hook(step, i, FAILURE, "GATE_FAILED", step_result)
                    return FAILURE

        # Execute the step (before_hook already called above, pass None to avoid duplicate)
        return_code, action, destination_step_name, failure_tail = execute_step(
            step, i, step_execution_count[i], loop_hardcap, None, step_id
        )

        # Handle mid-step stop (e.g. Echidna killed by StopChecker)
        if return_code == STOPPED or action == "STOPPED":
            print(f"\n⏹️  Step {i} was stopped by user request")
            print("Stopping workflow execution gracefully.")

            if after_hook:
                step_result = {"step_name": step.name, "step_num": i, "stopped": True}
                if i in _step_metadata:
                    step_result["internal_id"] = _step_metadata[i].get("internal_id")
                after_hook(step, i, STOPPED, "GRACEFUL_STOP", step_result)

            return STOPPED

        if return_code != SUCCESS:
            print(f"\n❌ Step {i} failed with return code {return_code}")
            print("Stopping workflow execution.")

            # Call after_hook on failure so worker can track failed step
            # Pass through the actual action from execute_step (e.g., STALE_FAILED, FAILED)
            if after_hook:
                step_result = {"step_name": step.name, "step_num": i, "failed": True}
                # Add internal_id for resume functionality
                if i in _step_metadata:
                    step_result["internal_id"] = _step_metadata[i].get("internal_id")
                # Add failure_tail for PROGRAM steps (last 10 lines of output)
                if failure_tail:
                    step_result["failure_tail"] = failure_tail
                # Use actual action if it indicates failure type, otherwise use FAILED
                failure_action = action if action in ("STALE_FAILED", "GATE_FAILED") else "FAILED"
                after_hook(step, i, return_code, failure_action, step_result)

            return return_code

        print(f"\n✓ Step {i} completed successfully")

        # Collect step results
        step_result: dict = {"step_name": step.name, "step_num": i}

        # Add internal_id for resume functionality
        if i in _step_metadata:
            step_result["internal_id"] = _step_metadata[i].get("internal_id")

        # Mark if step was skipped
        if action == "SKIPPED":
            step_result["skipped"] = True

        # Check if we should create a summary
        if step.shouldCreateSummary:
            summary = create_summary(step, i)
            step_result["summary"] = summary

        # Check if we should commit changes
        commit_info = None
        if step.shouldCommitChanges:
            commit_info = commit_changes(step, i)
            step_result["commit_info"] = commit_info

            # Push changes if commit was successful
            if commit_info:
                pushed = push_changes(i)
                step_result["pushed"] = pushed

        # Call after_hook with step results
        if after_hook:
            after_hook(step, i, return_code, action, step_result)

        # Handle decision actions
        if action == "STOP":
            print(f"\n🛑 STOP action triggered by step {i}")
            print("Halting workflow execution early.")
            return SUCCESS
        elif action == "CONTINUE_WITH_WARNING":
            print(f"\n⚠️  CONTINUE_WITH_WARNING: proceeding despite non-ideal condition")
        elif action == "SKIPPED":
            print(f"\n⏭️  Step {i} was skipped by user request")
            # Continue to next step (don't treat as failure)
        elif action == "JUMP_TO_STEP":
            if not destination_step_name:
                print(f"\n❌ JUMP_TO_STEP action requires destinationStep, but none was provided")
                print("Stopping workflow execution.")
                return FAILURE

            target_step_index = find_step_index_by_name(workflow, destination_step_name, i)

            if target_step_index is None:
                print(f"\n❌ JUMP_TO_STEP failed: Step '{destination_step_name}' not found in workflow")
                print("Stopping workflow execution.")
                return FAILURE

            # Validate the jump (prevent jumping to same step)
            if target_step_index == i:
                print(f"\n❌ JUMP_TO_STEP failed: Cannot jump to current step (would cause infinite loop)")
                print("Stopping workflow execution.")
                return FAILURE

            # Log the jump
            jump_direction = "forward" if target_step_index > i else "backward"
            jump_distance = abs(target_step_index - i)
            print(f"\n⏭️  JUMP_TO_STEP action triggered by step {i}")
            print(f"   Jumping {jump_direction} from '{step.name}' to '{destination_step_name}' ({jump_distance} steps)")

            # Perform the jump
            i = target_step_index
            continue
        elif action == "REPEAT_PREVIOUS_STEP":
            if i > 1:
                print(f"\n🔁 REPEAT_PREVIOUS_STEP action triggered, going back to step {i - 1}")
                i -= 1
                continue
            else:
                print(f"\n⚠ REPEAT_PREVIOUS_STEP cannot be executed on step 1, continuing instead")
        elif action == "COUNTER_MINUS_ONE":
            # Future implementation for loop counter decrement
            print(f"\n⚠ COUNTER_MINUS_ONE action not yet implemented")
        # CONTINUE is default, do nothing special

        i += 1

    print(f"\n{'#'*60}")
    print(f"# Workflow '{workflow.name}' completed successfully!")
    print(f"{'#'*60}\n")
    return SUCCESS


if __name__ == "__main__":
    # Simple entry point: python main.py workflow.json
    # For full-featured CLI with flags, use: recon --workflow ...

    from pathlib import Path

    # Set framework root
    os.environ['RECON_FRAMEWORK_ROOT'] = str(Path(__file__).parent.resolve())

    # Set prompts directory (where agent reference documents live)
    os.environ['PROMPTS_DIR'] = str(Path(__file__).parent.resolve() / 'prompts')

    # Parse single positional argument
    if len(sys.argv) < 2:
        print("Usage: python main.py <workflow_file>")
        print("Example: python main.py workflows/audit.json")
        print("\nFor advanced options, use: recon --workflow <file> [--dangerous] [--cap N] [--logs DIR] [--repo PATH]")
        sys.exit(1)

    workflow_file = sys.argv[1]

    # Run with defaults
    exit_code = run_workflow(
        workflow_file=workflow_file,
        dangerous=False,
        loop_hardcap=DEFAULT_LOOP_HARDCAP,
        logs_dir=None,
        repo_path=None
    )
    sys.exit(exit_code)
