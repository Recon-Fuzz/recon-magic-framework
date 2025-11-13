"""
Task execution module for workflow steps.
"""

import json
import os
import shlex
import subprocess
import tempfile
from datetime import datetime
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


class Model(BaseModel):
    """Model configuration."""
    type: str
    model: str


class TaskStep(BaseModel):
    """Task step type."""
    type: Literal["task"]
    name: str
    description: str | None = None
    prompt: str
    model: Model
    shouldCreateSummary: bool = Field(alias="shouldCreateSummary")
    shouldCommitChanges: bool = Field(alias="shouldCommitChanges")


def resolve_model_string(model_type: str, model_string: str) -> str:
    """
    Resolve the model string, handling 'inherit' by returning appropriate defaults.

    Args:
        model_type: The model type (CLAUDE_CODE, OPENCODE, etc.)
        model_string: The model string from the workflow (may be "inherit")

    Returns:
        str: The resolved model string to use in commands
    """
    if model_string.lower() != "inherit":
        return model_string

    # Handle inherit based on model type
    if model_type == ModelType.CLAUDE_CODE:
        return "sonnet"
    elif model_type == ModelType.OPENCODE:
        return "openrouter/anthropic/claude-sonnet-4.5"
    else:
        return model_string  # For PROGRAM or unknown types, return as-is


def execute_task_step(step: TaskStep, step_num: int) -> tuple[int, str, str | None]:
    """
    Execute a task step based on its model type.

    Returns:
        tuple[int, str, str | None]: (return_code, action, destination_step_name)
            - For task steps, destination_step_name is always None
    """

    ## NOTE: Use ${RECON_FRAMEWORK_ROOT} to reference framework programs
    ## Example: ${RECON_FRAMEWORK_ROOT}/programs/my_script.py
    if step.model.type == ModelType.PROGRAM:
        command = step.prompt
        framework_root = os.environ.get('RECON_FRAMEWORK_ROOT')

        # Expand ${RECON_FRAMEWORK_ROOT} placeholder
        if framework_root and '${RECON_FRAMEWORK_ROOT}' in command:
            command = command.replace('${RECON_FRAMEWORK_ROOT}', framework_root)

        # If repo_path is set, prefix command to cd there first
        repo_path = os.environ.get('RECON_REPO_PATH')
        if repo_path:
            command = f"cd {repo_path} && {command}"

        # Run the program
        result = subprocess.run(
            command,
            shell=True,
            env=os.environ.copy()
        )
        return (SUCCESS, "CONTINUE", None)

    ## AI Models
    # Get framework root for later use
    framework_root = os.environ.get('RECON_FRAMEWORK_ROOT', '.')

    # Create logs directory - use custom logs dir if provided, otherwise framework logs/
    logs_dir_override = os.environ.get('RECON_LOGS_DIR')
    if logs_dir_override:
        logs_dir = Path(logs_dir_override)
    else:
        logs_dir = Path(framework_root) / "logs"
    logs_dir.mkdir(exist_ok=True)

    # Build the command with extended timeouts and streaming output
    env = os.environ.copy()
    env['BASH_DEFAULT_TIMEOUT_MS'] = '214748364'
    env['BASH_MAX_TIMEOUT_MS'] = '214748364'

    # Generate log filename with timestamp and step name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_step_name = step.name.lower().replace(" ", "_")
    log_file = logs_dir / f"{timestamp}_step{step_num}_{safe_step_name}.log"

    if step.model.type == ModelType.CLAUDE_CODE:
        # Resolve the model string (handle "inherit")
        resolved_model = resolve_model_string(step.model.type, step.model.model)

        # Check if we should skip permissions (only in production)
        runner_env = os.environ.get('RUNNER_ENV', '').lower()
        skip_permissions = '--dangerously-skip-permissions' if runner_env == 'production' else ''

        # Create the full pipeline command using shlex for proper escaping
        # We'll write the parser script to a temp file to avoid quoting issues
        parser_script_file = Path(framework_root) / 'log_formatters' / 'claude_code.py'

        cmd = f"""claude {skip_permissions} \
-p {json.dumps(step.prompt)} \
-m {resolved_model} \
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

        return (result.returncode, "CONTINUE", None)

    if step.model.type == ModelType.OPENCODE:
        # Resolve the model string (handle "inherit")
        resolved_model = resolve_model_string(step.model.type, step.model.model)

        parser_script_file = Path(framework_root) / 'log_formatters' / 'opencode.py'

        cmd = f"""opencode run  \
{json.dumps(step.prompt)} \
-m {resolved_model} \
--format json | tee {log_file} | python3 -u {parser_script_file}"""

        print(f"📝 Logging to: {log_file}\n")

        result = subprocess.run(
            cmd,
            shell=True,
            env=env,
            text=True
        )

        return (result.returncode, "CONTINUE", None)

    else:
        print(f"Skipping {step.name}: Model type {step.model.type} not supported yet")
        return (SUCCESS, "CONTINUE", None)
