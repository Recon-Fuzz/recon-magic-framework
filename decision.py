"""
Decision execution module for workflow steps.
"""

from enum import Enum
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


class DecisionMode(str, Enum):
    """Decision mode enum defining how decisions are evaluated."""
    FILE_EXISTS = "FILE_EXISTS"      # check if a file exists
    READ_FILE = "READ_FILE"      # Read from filesystem (e.g., file exists check)
    API_CALL = "API_CALL"        # Make an API call to evaluate decision
    COUNTER = "COUNTER"          # Counter-based decision (for loops)
    COMPUTED = "COMPUTED"        # Computed value from previous steps


class Model(BaseModel):
    """Model configuration."""
    type: str
    model: str


class Decision(BaseModel):
    """Decision configuration for DecisionStep."""
    operator: Literal["eq", "gt", "lt", "gte", "lte", "neq"]
    value: float
    action: Literal["CONTINUE", "STOP", "REPEAT_PREVIOUS_STEP", "JUMP_TO_STEP"]
    destinationStep: str | None = None  # Required when action is JUMP_TO_STEP


class DecisionStep(BaseModel):
    """Decision step type."""
    type: Literal["decision"]
    name: str
    description: str | None = None
    mode: DecisionMode
    modeInfo: dict[str, str]
    prompt: str
    model: Model
    shouldCreateSummary: bool = Field(alias="shouldCreateSummary")
    shouldCommitChanges: bool = Field(alias="shouldCommitChanges")
    decision: list[Decision]


def evaluate_decisions(decisions: list[Decision], actual_value: float, debug: bool = True) -> tuple[str, str | None]:
    """
    Evaluate a list of decisions against an actual value.

    Args:
        decisions: List of Decision objects to evaluate
        actual_value: The actual value to compare against
        debug: Whether to print debug information

    Returns:
        tuple[str, str | None]: (action, destination_step_name)
            - action: The action to take (CONTINUE, STOP, REPEAT_PREVIOUS_STEP, JUMP_TO_STEP)
            - destination_step_name: The name of step to jump to (only set when action is JUMP_TO_STEP)
    """
    for decision in decisions:
        if debug:
            print(f"Checking: {actual_value} {decision.operator} {decision.value}")

        matched = False

        if decision.operator == "eq" and actual_value == decision.value:
            matched = True
        elif decision.operator == "neq" and actual_value != decision.value:
            matched = True
        elif decision.operator == "gt" and actual_value > decision.value:
            matched = True
        elif decision.operator == "lt" and actual_value < decision.value:
            matched = True
        elif decision.operator == "gte" and actual_value >= decision.value:
            matched = True
        elif decision.operator == "lte" and actual_value <= decision.value:
            matched = True

        if matched:
            if debug:
                print(f"✓ Decision matched: {decision.action}")
                if decision.action == "JUMP_TO_STEP":
                    print(f"  Destination: {decision.destinationStep}")
            return (decision.action, decision.destinationStep)

    if debug:
        print("⚠ No decision matched, defaulting to CONTINUE")
    return ("CONTINUE", None)


## TODO: Repeated visits of the same step should increase a counter, and if the counter is greater than the value, then the step should CONTINUE and ignore the decision.
def execute_decision_step(step: DecisionStep, step_num: int) -> tuple[int, str, str | None]:
    """
    Execute a decision step based on its model type.

    Returns:
        tuple[int, str, str | None]: (return_code, action, destination_step_name)
    """
    print(f"Executing decision step: {step.name}")

    # # Check that we have at least one decision
    # if not step.decision:
    #     print("⚠ No decisions defined, defaulting to CONTINUE")
    #     return (SUCCESS, "CONTINUE", None)

    # Get the mode from the first decision (all decisions in a step should have the same mode)
    decision_mode = step.mode
    print(f"Decision mode: {decision_mode}")

    if decision_mode == DecisionMode.FILE_EXISTS:
        # Find the file
        matches = list(Path('.').rglob(step.modeInfo["fileName"]))
        exists = 1.0 if matches else 0.0

        print(f"matches: {matches}")
        print(f"File exists: {exists}")

        action, destination = evaluate_decisions(step.decision, exists)
        return (SUCCESS, action, destination)

    if decision_mode == DecisionMode.READ_FILE:
        # Read the file
        matches = list(Path('.').rglob(step.modeInfo["fileName"]))

        if not matches:
            print("⚠ File doesnt exist, defaulting to CONTINUE")
            return (SUCCESS, "CONTINUE", None)

        file_path = matches[0]  # Get first match
        content = file_path.read_text().strip()

        print(f"File content: '{content}'")

        try:
            file_value = float(content)
        except ValueError:
            print(f"⚠ Could not parse file content as number: '{content}', defaulting to CONTINUE")
            return (SUCCESS, "CONTINUE", None)

        action, destination = evaluate_decisions(step.decision, file_value)
        return (SUCCESS, action, destination)
  