"""
Decision execution module for workflow steps.
"""

import os
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .model_decision import perform_decision_with_model
from core.path_utils import get_base_path



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
    READ_FILE = "READ_FILE"          # Read from filesystem (e.g., file exists check)
    USE_MODEL = "USE_MODEL"          # Use a model to decide
    READ_FILE_WITH_MODEL_DIGEST = "READ_FILE_WITH_MODEL_DIGEST" # Read from filesystem and use a model to digest the file contents
    JSON_KEY_VALUE = "JSON_KEY_VALUE"  # Read a specific key value from a JSON file


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
    model: Model | None = None  # Only required for USE_MODEL and READ_FILE_WITH_MODEL_DIGEST modes
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
        base_path = get_base_path()
        pattern = step.modeInfo["fileName"]

        print(f"  Base path: {base_path}")
        print(f"  Pattern: {pattern}")
        print(f"  RECON_FOUNDRY_ROOT: {os.environ.get('RECON_FOUNDRY_ROOT', '(not set)')}")
        print(f"  RECON_REPO_PATH: {os.environ.get('RECON_REPO_PATH', '(not set)')}")
        print(f"  Current working directory: {Path.cwd()}")

        # Find the file using glob (supports wildcards like *.txt)
        matches = list(base_path.glob(pattern))
        exists = 1.0 if matches else 0.0

        print(f"  Matches found: {len(matches)}")
        if matches:
            for match in matches:
                print(f"    - {match}")
        else:
            print(f"  No matches found for pattern: {pattern}")
            # List what IS in the expected directory (if it's looking in a magic/ subdirectory)
            if 'magic/' in pattern or pattern.startswith('magic/'):
                magic_dir = base_path / "magic"
                if magic_dir.exists() and magic_dir.is_dir():
                    print(f"  Files in {magic_dir}:")
                    try:
                        for f in magic_dir.iterdir():
                            print(f"    - {f.name}")
                    except Exception as e:
                        print(f"    (Error listing directory: {e})")

        print(f"  File exists result: {exists}")

        action, destination = evaluate_decisions(step.decision, exists)
        return (SUCCESS, action, destination)

    if decision_mode == DecisionMode.READ_FILE:
        base_path = get_base_path()

        # Read the file
        matches = list(base_path.glob(step.modeInfo["fileName"]))

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

    if decision_mode == DecisionMode.JSON_KEY_VALUE:
        import json

        base_path = get_base_path()
        file_pattern = step.modeInfo.get("fileName")
        json_key_path = step.modeInfo.get("keyPath")  # e.g., "summary.functions_with_missing_coverage"

        if not file_pattern:
            print("⚠ fileName not specified in modeInfo, defaulting to CONTINUE")
            return (SUCCESS, "CONTINUE", None)

        if not json_key_path:
            print("⚠ keyPath not specified in modeInfo, defaulting to CONTINUE")
            return (SUCCESS, "CONTINUE", None)

        # Find the file using glob pattern
        matches = list(base_path.glob(file_pattern))

        if not matches:
            print(f"⚠ No JSON file found matching pattern: {file_pattern}, defaulting to CONTINUE")
            return (SUCCESS, "CONTINUE", None)

        file_path = matches[0]  # Get first match
        print(f"📄 Found JSON file: {file_path}")

        try:
            with open(file_path) as f:
                data = json.load(f)

            # Navigate through nested keys (e.g., "summary.functions_with_missing_coverage")
            keys = json_key_path.split(".")
            value = data
            for key in keys:
                value = value[key]

            print(f"  Key path '{json_key_path}' = {value}")

            # Convert to float for comparison
            numeric_value = float(value)

            action, destination = evaluate_decisions(step.decision, numeric_value)
            return (SUCCESS, action, destination)

        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            print(f"⚠ Error reading JSON or accessing key '{json_key_path}': {e}, defaulting to CONTINUE")
            return (SUCCESS, "CONTINUE", None)

    if decision_mode == DecisionMode.USE_MODEL:
        # Use LLM to make decision based on prompt
        prompt = step.modeInfo.get("prompt")
        if not prompt:
            print("⚠ prompt not specified in modeInfo for USE_MODEL, defaulting to CONTINUE")
            return (SUCCESS, "CONTINUE", None)

        try:
            selected_value, reasoning = perform_decision_with_model(
                decisions=step.decision,
                prompt=prompt,
                model_config=step.model
            )

            print(f"Model decision: {selected_value}")
            print(f"Reasoning: {reasoning}")

            action, destination = evaluate_decisions(step.decision, selected_value)
            return (SUCCESS, action, destination)

        except Exception as e:
            print(f"⚠ Error calling model: {e}, defaulting to CONTINUE")
            return (SUCCESS, "CONTINUE", None)

    if decision_mode == DecisionMode.READ_FILE_WITH_MODEL_DIGEST:
        # Find and read file, then use LLM to digest content and make decision
        file_name = step.modeInfo.get("fileName")
        if not file_name:
            print("⚠ fileName not specified in modeInfo, defaulting to CONTINUE")
            return (SUCCESS, "CONTINUE", None)

        prompt = step.modeInfo.get("prompt")
        if not prompt:
            print("⚠ prompt not specified in modeInfo for READ_FILE_WITH_MODEL_DIGEST, defaulting to CONTINUE")
            return (SUCCESS, "CONTINUE", None)

        base_path = get_base_path()

        # Try to find the file
        matches = list(base_path.glob(file_name))

        if not matches:
            print(f"⚠ File not found: {file_name}, defaulting to CONTINUE")
            return (SUCCESS, "CONTINUE", None)

        file_path = matches[0]  # Get first match
        print(f"📄 Found file: {file_path}")

        try:
            content = file_path.read_text()
            print(f"📖 Read {len(content)} characters from file")

            # Combine prompt with file contents
            combined_prompt = f"{prompt}\n\n---\nFile contents:\n{content}"

            # Use model to digest and make decision
            selected_value, reasoning = perform_decision_with_model(
                decisions=step.decision,
                prompt=combined_prompt,
                model_config=step.model
            )

            print(f"Model decision: {selected_value}")
            print(f"Reasoning: {reasoning}")

            action, destination = evaluate_decisions(step.decision, selected_value)
            return (SUCCESS, action, destination)

        except Exception as e:
            print(f"⚠ Error processing file or calling model: {e}, defaulting to CONTINUE")
            return (SUCCESS, "CONTINUE", None)

    # Default case if no mode matches
    print(f"⚠ Unhandled decision mode: {decision_mode}, defaulting to CONTINUE")
    return (SUCCESS, "CONTINUE", None)
