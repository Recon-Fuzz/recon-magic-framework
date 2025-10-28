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
    OPENROUTER = "OPENROUTER"


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
    action: Literal["CONTINUE", "COUNTER_MINUS_ONE", "STOP"]


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


## TODO: Repeated visits of the same step should increase a counter, and if the counter is greater than the value, then the step should CONTINUE and ignore the decision.
def execute_decision_step(step: DecisionStep, step_num: int) -> tuple[int, str]:
    """Execute a decision step based on its model type."""
    print(f"Executing decision step: {step.name}")

    # # Check that we have at least one decision
    # if not step.decision:
    #     print("⚠ No decisions defined, defaulting to CONTINUE")
    #     return (SUCCESS, "CONTINUE")

    # Get the mode from the first decision (all decisions in a step should have the same mode)
    decision_mode = step.mode
    print(f"Decision mode: {decision_mode}")

    if decision_mode == DecisionMode.FILE_EXISTS:
        # Find the file
        matches = list(Path('.').rglob(step.modeInfo["fileName"]))
        exists = 1 if matches else 0

        print(f"matches: {matches}")
        print(f"File exists: {exists}")

        for decision in step.decision:
            if decision.operator == "eq" and decision.value == exists:
                print(f"Decision matched: {decision.action}")
                return (SUCCESS, decision.action)

        print("⚠ No decision matched, defaulting to CONTINUE")
        return (SUCCESS, "CONTINUE")
    
    if decision_mode == DecisionMode.READ_FILE:
        # Read the file
        matches = list(Path('.').rglob(step.modeInfo["fileName"]))

        if not matches:
            print("⚠ File doesnt exist, defaulting to CONTINUE")
            return (SUCCESS, "CONTINUE")
        else:
            file_path = matches[0]  # Get first match
            content = file_path.read_text()

        ## TODO: Refactor this match stuff to be more generic
        for decision in step.decision:
            if decision.operator == "eq" and decision.value == float(content):
                print(f"Decision matched: {decision.action}")
                return (SUCCESS, decision.action)
        print("⚠ No decision matched, defaulting to CONTINUE")
        return (SUCCESS, "CONTINUE")
  