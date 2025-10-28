"""
Workflow reader with typed data structures matching type.ts definitions.
"""

import json
import os
import subprocess
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field

# Exit codes
SUCCESS = 0
FAILURE = 1


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


def execute_step(step: Step, step_num: int) -> tuple[int, str]:
    """
    Execute a workflow step based on its step type.

    Args:
        step: The step to execute
        step_num: The step number for logging

    Returns:
        tuple[int, str]: (Return code from the execution, Action to take: "CONTINUE", "STOP", etc.)
    """
    # Switch on step.type first
    if isinstance(step, TaskStep):
        return _execute_task_step(step, step_num)
    elif isinstance(step, DecisionStep):
        return _execute_decision_step(step, step_num)
    else:
        print(f"❌ Unknown step type: {type(step)}")
        return (FAILURE, "CONTINUE")


def _execute_task_step(step: TaskStep, step_num: int) -> tuple[int, str]:
    """Execute a task step based on its model type."""
    if step.model.type == ModelType.CLAUDE_CODE:
        print(f"\n{'='*60}")
        print(f"Executing: {step.name}")
        print(f"Description: {step.description or 'N/A'}")
        print(f"{'='*60}\n")

        # Create logs directory if it doesn't exist
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        # Generate log filename with timestamp and step name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_step_name = step.name.lower().replace(" ", "_")
        log_file = logs_dir / f"{timestamp}_step{step_num}_{safe_step_name}.log"

        # Build the command with extended timeouts and streaming output
        env = os.environ.copy()
        env['BASH_DEFAULT_TIMEOUT_MS'] = '214748364'
        env['BASH_MAX_TIMEOUT_MS'] = '214748364'

        # Check if we should skip permissions (only in production)
        runner_env = os.environ.get('RUNNER_ENV', '').lower()
        skip_permissions = '--dangerously-skip-permissions' if runner_env == 'production' else ''

        # Create the full pipeline command using shlex for proper escaping
        # We'll write the parser script to a temp file to avoid quoting issues
        import tempfile
        parser_script_content = r"""import sys, json
for line in sys.stdin:
    try:
        data = json.loads(line)
        if data.get('type') == 'assistant' and data.get('message', {}).get('content'):
            for item in data['message']['content']:
                if item.get('type') == 'text':
                    print('💭 ' + item['text'])
                elif item.get('type') == 'tool_use':
                    tool_name = item.get('name', 'unknown')
                    if 'input' in item and 'command' in item['input']:
                        print(f'⚡ [{tool_name}] ' + item['input']['command'])
                    else:
                        print(f'⚡ [{tool_name}]')
        elif data.get('type') == 'user' and data.get('message', {}).get('content'):
            for item in data['message']['content']:
                if item.get('type') == 'tool_result' and item.get('is_error'):
                    tool_name = item.get('tool_use', {}).get('name', 'unknown')
                    print(f'❌ [{tool_name}] ' + item['content'].split('\n')[0])
    except: pass
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(parser_script_content)
            parser_script_file = f.name

        cmd = f"""claude {skip_permissions} \
-p {json.dumps(step.prompt)} \
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

        return (result.returncode, "CONTINUE")
    else:
        print(f"Skipping {step.name}: Model type {step.model.type.value} not supported yet")
        return (SUCCESS, "CONTINUE")


def _execute_decision_step(step: DecisionStep, step_num: int) -> tuple[int, str]:
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
        print(f"❌ Decision step '{step.name}' has unsupported model type: {step.model.type.value}")
        return (FAILURE, "CONTINUE")


def main():
    """Execute the workflow."""
    # Load the workflow
    workflow = load_workflow("workflow.json")

    print(f"\n{'#'*60}")
    print(f"# Workflow: {workflow.name}")
    print(f"# Number of steps: {len(workflow.steps)}")
    print(f"{'#'*60}\n")

    # Execute each step
    for i, step in enumerate(workflow.steps, 1):
        print(f"\n[Step {i}/{len(workflow.steps)}] {step.name}")
        print(f"Type: {step.type}")
        print(f"Model: {step.model.type.value}")

        # Execute the step
        return_code, action = execute_step(step, i)

        if return_code != SUCCESS:
            print(f"\n❌ Step {i} failed with return code {return_code}")
            print("Stopping workflow execution.")
            return return_code

        print(f"\n✓ Step {i} completed successfully")

        # Handle decision actions
        if action == "STOP":
            print(f"\n🛑 STOP action triggered by step {i}")
            print("Halting workflow execution early.")
            return SUCCESS
        elif action == "COUNTER_MINUS_ONE":
            # Future implementation for loop counter decrement
            print(f"\n⚠ COUNTER_MINUS_ONE action not yet implemented")
        # CONTINUE is default, do nothing special

    print(f"\n{'#'*60}")
    print(f"# Workflow '{workflow.name}' completed successfully!")
    print(f"{'#'*60}\n")
    return SUCCESS


if __name__ == "__main__":
    exit(main())
