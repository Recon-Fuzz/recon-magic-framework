"""
Decision execution module for workflow steps.
"""

import os
from enum import Enum
from pathlib import Path
from typing import Literal, Union

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
    FILE_CONTAINS = "FILE_CONTAINS"  # check if a file contains a specific string (returns 1 or 0)
    READ_FILE = "READ_FILE"          # Read from filesystem (e.g., file exists check)
    USE_MODEL = "USE_MODEL"          # Use a model to decide
    READ_FILE_WITH_MODEL_DIGEST = "READ_FILE_WITH_MODEL_DIGEST" # Read from filesystem and use a model to digest the file contents
    JSON_KEY_VALUE = "JSON_KEY_VALUE"  # Read a specific key value from a JSON file
    GREP = "GREP"                    # Run grep pattern on a file/glob, returns match count
    SHELL = "SHELL"                  # Run a shell command, returns exit code


class Model(BaseModel):
    """Model configuration."""
    type: str
    model: str


class Decision(BaseModel):
    """Decision configuration for DecisionStep."""
    operator: Literal["eq", "gt", "lt", "gte", "lte", "neq"]
    value: Union[float, str]  # Support both numeric and string comparisons
    action: Literal["CONTINUE", "CONTINUE_WITH_WARNING", "STOP", "REPEAT_PREVIOUS_STEP", "JUMP_TO_STEP"]
    destinationStep: str | None = None  # Required when action is JUMP_TO_STEP
    NOTE: str | None = None  # Optional documentation note


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


def evaluate_decisions(decisions: list[Decision], actual_value: Union[float, str], debug: bool = True) -> tuple[str, str | None]:
    """
    Evaluate a list of decisions against an actual value.

    Args:
        decisions: List of Decision objects to evaluate
        actual_value: The actual value to compare against (can be numeric or string)
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

        # Handle string comparisons
        if isinstance(actual_value, str) and isinstance(decision.value, str):
            if decision.operator == "eq" and actual_value == decision.value:
                matched = True
            elif decision.operator == "neq" and actual_value != decision.value:
                matched = True
            # String comparison operators like gt, lt don't make sense in most contexts
            # but we could support them for lexicographic comparisons if needed
            elif decision.operator in ["gt", "lt", "gte", "lte"]:
                print(f"⚠ Warning: Using {decision.operator} with strings, using lexicographic comparison")
                if decision.operator == "gt" and actual_value > decision.value:
                    matched = True
                elif decision.operator == "lt" and actual_value < decision.value:
                    matched = True
                elif decision.operator == "gte" and actual_value >= decision.value:
                    matched = True
                elif decision.operator == "lte" and actual_value <= decision.value:
                    matched = True
        # Handle numeric comparisons
        else:
            # Try to convert both to float for comparison
            try:
                actual_num = float(actual_value) if isinstance(actual_value, str) else actual_value
                decision_num = float(decision.value) if isinstance(decision.value, str) else decision.value

                if decision.operator == "eq" and actual_num == decision_num:
                    matched = True
                elif decision.operator == "neq" and actual_num != decision_num:
                    matched = True
                elif decision.operator == "gt" and actual_num > decision_num:
                    matched = True
                elif decision.operator == "lt" and actual_num < decision_num:
                    matched = True
                elif decision.operator == "gte" and actual_num >= decision_num:
                    matched = True
                elif decision.operator == "lte" and actual_num <= decision_num:
                    matched = True
            except (ValueError, TypeError):
                # If we can't convert to numbers, treat as string comparison
                if decision.operator == "eq" and str(actual_value) == str(decision.value):
                    matched = True
                elif decision.operator == "neq" and str(actual_value) != str(decision.value):
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

        # Check if this is a glob pattern or direct file path
        has_wildcard = '*' in file_pattern or '?' in file_pattern

        if has_wildcard:
            # Use glob to find matching files
            matches = list(base_path.glob(file_pattern))

            if not matches:
                print(f"⚠ No JSON file found matching pattern: {file_pattern}, defaulting to CONTINUE")
                return (SUCCESS, "CONTINUE", None)

            file_path = matches[0]  # Get first match
        else:
            # Direct file path - no glob needed
            file_path = base_path / file_pattern
            if not file_path.exists():
                print(f"⚠ JSON file not found: {file_path}, defaulting to CONTINUE")
                return (SUCCESS, "CONTINUE", None)

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

            # Keep value as-is (string or number) for comparison
            # The evaluate_decisions function now handles both types
            action, destination = evaluate_decisions(step.decision, value)
            return (SUCCESS, action, destination)

        except (json.JSONDecodeError, KeyError, TypeError) as e:
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

    if decision_mode == DecisionMode.FILE_CONTAINS:
        base_path = get_base_path()
        pattern = step.modeInfo.get("fileName")
        search_string = step.modeInfo.get("searchString")

        if not pattern or search_string is None:
            print("⚠ fileName or searchString not specified in modeInfo, defaulting to CONTINUE")
            return (SUCCESS, "CONTINUE", None)

        matches = list(base_path.glob(pattern))
        if not matches:
            print(f"  File not found matching pattern: {pattern}")
            action, destination = evaluate_decisions(step.decision, 0.0)
            return (SUCCESS, action, destination)

        file_path = matches[0]
        content = file_path.read_text()
        found = 1.0 if search_string in content else 0.0
        print(f"  Search '{search_string}' in {file_path.name}: {'found' if found else 'not found'}")
        action, destination = evaluate_decisions(step.decision, found)
        return (SUCCESS, action, destination)

    if decision_mode == DecisionMode.GREP:
        import subprocess
        base_path = get_base_path()
        pattern = step.modeInfo.get("pattern")
        file_glob = step.modeInfo.get("file")

        if not pattern or not file_glob:
            print("⚠ pattern or file not specified in modeInfo, defaulting to CONTINUE")
            return (SUCCESS, "CONTINUE", None)

        matches = list(base_path.glob(file_glob))
        if not matches:
            print(f"  No files found matching glob: {file_glob}")
            action, destination = evaluate_decisions(step.decision, 0.0)
            return (SUCCESS, action, destination)

        total_count = 0
        for file_path in matches:
            result = subprocess.run(
                ["grep", "-c", pattern, str(file_path)],
                capture_output=True, text=True
            )
            try:
                total_count += int(result.stdout.strip())
            except ValueError:
                pass

        print(f"  Grep '{pattern}' in {[m.name for m in matches]}: {total_count} matches")
        action, destination = evaluate_decisions(step.decision, float(total_count))
        return (SUCCESS, action, destination)

    if decision_mode == DecisionMode.SHELL:
        import subprocess
        command = step.modeInfo.get("command")
        if not command:
            print("⚠ command not specified in modeInfo, defaulting to CONTINUE")
            return (SUCCESS, "CONTINUE", None)

        foundry_root = os.environ.get('RECON_FOUNDRY_ROOT') or os.environ.get('RECON_REPO_PATH', '.')
        print(f"  Running shell command: {command}")
        result = subprocess.run(
            command, shell=True, cwd=foundry_root,
            capture_output=True, text=True
        )
        exit_code = float(result.returncode)
        print(f"  Exit code: {int(exit_code)}")
        if result.stdout:
            print(f"  stdout: {result.stdout.strip()[-500:]}")
        if result.stderr:
            print(f"  stderr: {result.stderr.strip()[-500:]}")
        action, destination = evaluate_decisions(step.decision, exit_code)
        return (SUCCESS, action, destination)

    # Default case if no mode matches
    print(f"⚠ Unhandled decision mode: {decision_mode}, defaulting to CONTINUE")
    return (SUCCESS, "CONTINUE", None)
