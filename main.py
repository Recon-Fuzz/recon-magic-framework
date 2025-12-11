"""
Main workflow execution module.
Use this when using recon-magic framework as a library.
"""

import json
import os
import sys
from enum import Enum
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


def load_workflow(filepath: str) -> Workflow:
    """
    Load and parse a workflow JSON file with type validation.

    Args:
        filepath: Path to the workflow.json file

    Returns:
        Workflow: Parsed and validated workflow object

    Raises:
        FileNotFoundError: If the workflow file doesn't exist
        json.JSONDecodeError: If the JSON is malformed
        pydantic.ValidationError: If the data doesn't match the schema
    """
    with open(filepath, 'r') as f:
        data = json.load(f)

    return Workflow(**data)

def default_before_step_execution(step: Step, step_num: int) -> None:
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

def execute_step(
    step: Step,
    step_num: int,
    execution_count: int,
    loop_hardcap: int = DEFAULT_LOOP_HARDCAP,
    before_hook: Callable[[Step, int], None] | None = None,
) -> tuple[int, str, str | None]:
    """
    Execute a workflow step based on its step type.

    Args:
        step: The step to execute
        step_num: The step number for logging
        execution_count: Number of times this step has been executed
        loop_hardcap: Maximum number of times a decision step can loop
        before_hook: Optional callback to run before step execution

    Returns:
        tuple[int, str, str | None]: (Return code, Action, Destination step name)
    """
    # Use provided hooks or default ones
    _before_hook = before_hook or default_before_step_execution

    _before_hook(step, step_num)

    return_code, action, destination = None, None, None

    # Check if we've hit the loop hardcap for decision steps
    if isinstance(step, DecisionStep) and execution_count > loop_hardcap:
        print(f"⚠️  Loop hardcap ({loop_hardcap}) reached for step {step_num}, forcing CONTINUE")
        return_code, action, destination = (SUCCESS, "CONTINUE", None)
    else:
        # Switch on step.type first
        if isinstance(step, TaskStep):
            return_code, action, destination = execute_task_step(step, step_num)
        elif isinstance(step, DecisionStep):
            return_code, action, destination = execute_decision_step(step, step_num)
        else:
            print(f"❌ Unknown step type: {type(step)}")
            return_code, action, destination = (FAILURE, "CONTINUE", None)

    return (return_code, action, destination)


## TODO: Separate File
def create_summary(step: Step, step_num: int) -> str | None:
    """
    Create a summary for the completed step using Claude.

    Args:
        step: The step that was executed
        step_num: The step number for logging

    Returns:
        str | None: The generated summary or None if failed
    """
    print(f"📝 Creating summary for step {step_num}: {step.name}")

    try:
        import subprocess

        # Get repo path from environment
        repo_path = os.environ.get('RECON_REPO_PATH', '.')

        # Gather context: git diff of uncommitted changes
        git_diff = ""
        success, diff_output, _ = run_command("git diff HEAD", cwd=repo_path)
        if success and diff_output:
            git_diff = diff_output
        else:
            # Try getting staged changes if no diff against HEAD
            success, diff_output, _ = run_command("git diff --cached", cwd=repo_path)
            if success and diff_output:
                git_diff = diff_output

        # Get list of changed/new files
        changed_files = ""
        success, status_output, _ = run_command("git status --porcelain", cwd=repo_path)
        if success and status_output:
            changed_files = status_output

        # Build context string
        context_parts = []
        context_parts.append(f"Step name: {step.name}")
        if step.description:
            context_parts.append(f"Step description: {step.description}")
        if changed_files:
            context_parts.append(f"Changed files:\n{changed_files}")
        if git_diff:
            # Limit diff size to avoid overwhelming the model
            max_diff_chars = 8000
            if len(git_diff) > max_diff_chars:
                git_diff = git_diff[:max_diff_chars] + "\n... (diff truncated)"
            context_parts.append(f"Git diff:\n{git_diff}")

        context = "\n\n".join(context_parts)

        prompt = f"""Based on the following context, summarize the changes made in step '{step.name}' in 2-3 sentences. Focus on what was accomplished, not implementation details. Return only the summary text.

{context}"""

        # Check if we should skip permissions (production environment)
        runner_env = os.environ.get('RUNNER_ENV', '').lower()
        cmd = ["claude"]
        if runner_env == 'production':
            cmd.append("--dangerously-skip-permissions")
        cmd.extend(["-p", prompt, "--model", "haiku"])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
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
def find_step_index_by_name(workflow: Workflow, step_name: str) -> int | None:
    """
    Find the step index (1-based) by step name.

    Args:
        workflow: The workflow containing the steps
        step_name: The name of the step to find

    Returns:
        int | None: The 1-based index of the step, or None if not found
    """
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
    before_hook: Callable[[Step, int], None] | None = None,
    after_hook: Callable[[Step, int, int, str, dict | None], None] | None = None,
    stop_checker: Callable[[], bool] | None = None
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
            - Receives: (step, step_num, return_code, action, step_result)
            - step_result contains: {summary, commit_info, pushed}
        stop_checker: Optional callback to check if graceful stop was requested
            - Called before each step
            - Returns True if stop was requested, False otherwise

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

    print(f"\n{'#'*60}")
    print(f"# Workflow: {workflow.name}")
    print(f"# Number of steps: {len(workflow.steps)}")
    print(f"{'#'*60}\n")

    # In-memory cache to track step execution counts
    step_execution_count: dict[int, int] = {}

    # Execute each step
    i = 1
    while i <= len(workflow.steps):
        step = workflow.steps[i - 1]

        # Check for graceful stop request before executing each step
        if stop_checker and stop_checker():
            print(f"\n⏹️  Graceful stop requested before step {i}: {step.name}")
            print("Stopping workflow execution gracefully.")

            # Call after_hook to notify about the stop
            if after_hook:
                step_result = {"step_name": step.name, "step_num": i, "stopped": True}
                after_hook(step, i, STOPPED, "GRACEFUL_STOP", step_result)

            return STOPPED

        # Track execution count for this step
        if i not in step_execution_count:
            step_execution_count[i] = 0
        step_execution_count[i] += 1

        print(f"\n[Step {i}/{len(workflow.steps)}] {step.name} (execution #{step_execution_count[i]})")
        print(f"Type: {step.type}")
        if hasattr(step, 'model') and step.model:
            print(f"Model: {step.model.type}")

        # Execute the step
        return_code, action, destination_step_name = execute_step(
            step, i, step_execution_count[i], loop_hardcap, before_hook
        )

        if return_code != SUCCESS:
            print(f"\n❌ Step {i} failed with return code {return_code}")
            print("Stopping workflow execution.")

            # Call after_hook on failure so worker can track failed step
            if after_hook:
                step_result = {"step_name": step.name, "step_num": i, "failed": True}
                after_hook(step, i, return_code, "FAILED", step_result)

            return return_code

        print(f"\n✓ Step {i} completed successfully")

        # Collect step results
        step_result: dict = {"step_name": step.name, "step_num": i}

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
        elif action == "JUMP_TO_STEP":
            if not destination_step_name:
                print(f"\n❌ JUMP_TO_STEP action requires destinationStep, but none was provided")
                print("Stopping workflow execution.")
                return FAILURE

            target_step_index = find_step_index_by_name(workflow, destination_step_name)

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
