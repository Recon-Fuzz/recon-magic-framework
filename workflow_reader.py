"""
Workflow reader with typed data structures matching type.ts definitions.
"""

import json
from enum import Enum
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field


class ModelType(str, Enum):
    """Model type enum matching TypeScript ModelType."""
    INHERIT = "INHERIT"
    PROGRAM = "PROGRAM"
    CLAUDE_CODE = "CLAUDE_CODE"
    OPENROUTER = "OPENROUTER"


class Model(BaseModel):
    """Model configuration."""
    type: ModelType
    model: str


class Step(BaseModel):
    """Base step interface."""
    name: str
    description: str | None = None
    prompt: str
    model: Model
    shouldCreateSummary: bool = Field(alias="shouldCreateSummary")
    shouldCommitChanges: bool = Field(alias="shouldCommitChanges")


class TaskStep(Step):
    """Task step type."""
    type: Literal["task"]


class Decision(BaseModel):
    """Decision configuration for DecisionStep."""
    operator: Literal["eq", "gt", "lt", "gte", "lte", "neq"]
    value: float
    action: Literal["CONTINUE", "COUNTER_MINUS_ONE", "STOP"]


class DecisionStep(Step):
    """Decision step type."""
    type: Literal["decision"]
    decision: list[Decision]


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


def main():
    """Example usage of the workflow reader."""
    # Load the workflow
    workflow = load_workflow("workflow.json")

    print(f"Workflow: {workflow.name}")
    print(f"Number of steps: {len(workflow.steps)}")
    print()

    # Iterate through steps
    for i, step in enumerate(workflow.steps, 1):
        print(f"Step {i}: {step.name}")
        print(f"  Type: {step.type}")
        print(f"  Description: {step.description or 'N/A'}")
        print(f"  Model: {step.model.type.value} ({step.model.model})")
        print(f"  Create Summary: {step.shouldCreateSummary}")
        print(f"  Commit Changes: {step.shouldCommitChanges}")

        if isinstance(step, DecisionStep):
            print(f"  Decisions: {len(step.decision)}")
            for j, decision in enumerate(step.decision, 1):
                print(f"    {j}. {decision.operator} {decision.value} -> {decision.action}")

        print()


if __name__ == "__main__":
    main()
