"""
Decision execution module for workflow steps.
"""

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
    prompt: str
    model: Model
    shouldCreateSummary: bool = Field(alias="shouldCreateSummary")
    shouldCommitChanges: bool = Field(alias="shouldCommitChanges")
    decision: list[Decision]


def execute_decision_step(step: DecisionStep, step_num: int) -> tuple[int, str]:
    """Execute a decision step based on its model type."""
    if step.model.type == ModelType.PROGRAM:
        if step.model.model == "file_exists_check":
            print(f"\n{'='*60}")
            print(f"Checking: {step.name}")
            print(f"Description: {step.description or 'N/A'}")
            print(f"{'='*60}\n")

            # Check if CRITICAL_STOP.MD exists
            file_path = Path("CRITICAL_STOP.MD")
            exists = 1 if file_path.exists() else 0

            print(f"🔍 Checking for CRITICAL_STOP.MD: {'✓ EXISTS' if exists == 1 else '✗ NOT FOUND'}")

            # Evaluate decisions
            for decision in step.decision:
                if decision.operator == "eq" and exists == decision.value:
                    print(f"✓ Decision matched: value={exists}, action={decision.action}")
                    return (SUCCESS, decision.action)
                elif decision.operator == "neq" and exists != decision.value:
                    print(f"✓ Decision matched: value={exists}, action={decision.action}")
                    return (SUCCESS, decision.action)
                elif decision.operator == "gt" and exists > decision.value:
                    print(f"✓ Decision matched: value={exists}, action={decision.action}")
                    return (SUCCESS, decision.action)
                elif decision.operator == "lt" and exists < decision.value:
                    print(f"✓ Decision matched: value={exists}, action={decision.action}")
                    return (SUCCESS, decision.action)
                elif decision.operator == "gte" and exists >= decision.value:
                    print(f"✓ Decision matched: value={exists}, action={decision.action}")
                    return (SUCCESS, decision.action)
                elif decision.operator == "lte" and exists <= decision.value:
                    print(f"✓ Decision matched: value={exists}, action={decision.action}")
                    return (SUCCESS, decision.action)

            # No decision matched, default to CONTINUE
            print("⚠ No decision matched, defaulting to CONTINUE")
            return (SUCCESS, "CONTINUE")
        else:
            print(f"❌ Unknown PROGRAM model: {step.model.model}")
            return (FAILURE, "CONTINUE")
    else:
        print(f"❌ Decision step '{step.name}' has unsupported model type: {step.model.type}")
        return (FAILURE, "CONTINUE")
