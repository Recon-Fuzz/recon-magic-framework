"""
Main workflow execution module.
"""

import json
import sys
from enum import Enum
from typing import Annotated, Literal, Union

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from decision import DecisionStep, execute_decision_step
from task import TaskStep, execute_task_step
from git_commit import is_git_repo, init_git_repo, run_command

# Load environment variables from .env file
load_dotenv()

# Exit codes
SUCCESS = 0
FAILURE = 1

# Loop hardcap to prevent infinite loops
LOOP_HARDCAP = 5


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
    model: Model
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

def before_step_execution(step: Step, step_num: int) -> None:
    """
    Run before the step execution.
    """
    print(f"Before step {step_num}: {step.name}")
    print(f"Type: {step.type}")
    print(f"Model: {step.model.type}")
    print(f"Description: {step.description or 'N/A'}")
    print(f"Should create summary: {step.shouldCreateSummary}")
    print(f"Should commit changes: {step.shouldCommitChanges}")

    ## TODO: How do we allow the step to call the API and set it's current state?
    ## TODO: Call an API with /step and the data (basically the title), the api specification is not done
    ## But basically we'll have something like POST: jobs/:jobId/step, which updates the current step

def after_step_execution(step: Step, step_num: int, return_code: int, action: str) -> None:
    """
    Run after the step execution.
    """
    ## Create summary
    ## Commit

    ## TODO: How do we allow the step to call the API and set it's current summary?
    ## TODO: API Specification
    ## Likely POST jobs/:jobId/summaries, and it's an append only list of summaries.

def execute_step(step: Step, step_num: int, execution_count: int) -> tuple[int, str, str | None]:
    """
    Execute a workflow step based on its step type.

    Args:
        step: The step to execute
        step_num: The step number for logging
        execution_count: Number of times this step has been executed

    Returns:
        tuple[int, str, str | None]: (Return code, Action, Destination step name)
    """

    before_step_execution(step, step_num)

    return_code, action, destination = None, None, None

    # Check if we've hit the loop hardcap for decision steps
    if isinstance(step, DecisionStep) and execution_count > LOOP_HARDCAP:
        print(f"⚠️  Loop hardcap ({LOOP_HARDCAP}) reached for step {step_num}, forcing CONTINUE")
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

    after_step_execution(step, step_num, return_code, action)

    return (return_code, action, destination)


## TODO: Separate File
def create_summary(step: Step, step_num: int) -> None:
    """
    Create a summary for the completed step.

    Args:
        step: The step that was executed
        step_num: The step number for logging
    """
    print(f"📝 Creating summary for step {step_num}: {step.name}")
    # TODO: Implement summary creation logic
    print("⚠ Summary creation not yet implemented")


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


def commit_changes(step: Step, step_num: int) -> None:
    """
    Commit changes made during the step execution.

    Args:
        step: The step that was executed
        step_num: The step number for logging
    """
    print(f"\n💾 Committing changes for step {step_num}: {step.name}")

    # Check if git repo exists, initialize if not
    if not is_git_repo():
        print("  Initializing git repository...")
        if not init_git_repo(verbose=False):
            print("  ❌ Failed to initialize git repository")
            return
        print("  ✓ Git repository initialized successfully")

    # Check if there are any changes to commit
    success, stdout, _ = run_command("git status --porcelain")
    if not success:
        print("  ❌ Failed to check git status")
        return

    if not stdout:
        print("  ℹ️  No changes to commit")
        return

    # Add all changes
    print("  Adding changes...")
    success, _, stderr = run_command("git add .")
    if not success:
        print(f"  ❌ Failed to add changes: {stderr}")
        return

    # Commit changes with a descriptive message | ## TODO: Consider using a LLM to generate the commit message
    commit_message = f"Step {step_num}: {step.name}"
    if step.description:
        commit_message += f"\n\n{step.description}"

    print(f"  Committing with message: '{commit_message.split(chr(10))[0]}'")

    # Escape single quotes in the message
    escaped_message = commit_message.replace("'", "'\\''")
    success, stdout, stderr = run_command(f"git commit -m '{escaped_message}'")

    if success:
        print("  ✓ Changes committed successfully!")
    else:
        # Check if the error is due to no changes staged (can happen with .gitignore)
        if "nothing to commit" in stderr or "nothing to commit" in stdout:
            print("  ℹ️  No changes to commit (all changes may be ignored by .gitignore)")
        else:
            print(f"  ❌ Failed to commit changes: {stderr}")


def main(workflow_file: str = "workflow.json"):
    """
    Execute the workflow.

    Args:
        workflow_file: Path to the workflow JSON file (defaults to "workflow.json")
    """
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

        # Track execution count for this step
        if i not in step_execution_count:
            step_execution_count[i] = 0
        step_execution_count[i] += 1

        print(f"\n[Step {i}/{len(workflow.steps)}] {step.name} (execution #{step_execution_count[i]})")
        print(f"Type: {step.type}")
        print(f"Model: {step.model.type}")

        # Execute the step
        return_code, action, destination_step_name = execute_step(step, i, step_execution_count[i])

        if return_code != SUCCESS:
            print(f"\n❌ Step {i} failed with return code {return_code}")
            print("Stopping workflow execution.")
            return return_code

        print(f"\n✓ Step {i} completed successfully")

        # Check if we should create a summary
        if step.shouldCreateSummary:
            create_summary(step, i)

        # Check if we should commit changes
        if step.shouldCommitChanges:
            commit_changes(step, i)

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
    # Parse command line arguments
    workflow_file = sys.argv[1] if len(sys.argv) > 1 else "workflows/workflow.json"
    exit(main(workflow_file))
