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


def execute_task_step(step: TaskStep, step_num: int) -> tuple[int, str, str | None]:
    """
    Execute a task step based on its model type.

    Returns:
        tuple[int, str, str | None]: (return_code, action, destination_step_name)
            - For task steps, destination_step_name is always None
    """

    ## NOTE: ./ for programs within this code, PATH/W/e for relative to the pwd. Just the name to run cli stuff, e.g. echidna.
    if step.model.type == ModelType.PROGRAM:
        # Resolve ./ paths to framework root
        command = step.prompt
        framework_root = os.environ.get('RECON_FRAMEWORK_ROOT')

        if framework_root and './' in command:
            # Only process if command contains ./ references
            # Use simple string replacement to avoid breaking shell operators
            command = command.replace('./', str(Path(framework_root)) + '/')

        # Run the program (CWD remains in target repo)
        result = subprocess.run(
            command,
            shell=True,
            env=os.environ.copy()
        )
        return (SUCCESS, "CONTINUE", None)

    ## AI Models
    # Create logs directory in framework, not target repo
    framework_root = os.environ.get('RECON_FRAMEWORK_ROOT', '.')
    logs_dir = Path(framework_root) / "logs"
    logs_dir.mkdir(exist_ok=True)

    # Build the command with extended timeouts and streaming output
    env = os.environ.copy()
    env['BASH_DEFAULT_TIMEOUT_MS'] = '214748364'
    env['BASH_MAX_TIMEOUT_MS'] = '214748364'

    # Generate log filename with timestamp and step name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Sanitize step name: replace spaces with underscores and remove special characters
    import re
    safe_step_name = step.name.lower().replace(" ", "_")
    safe_step_name = re.sub(r'[^a-z0-9_-]', '', safe_step_name)
    log_file = logs_dir / f"{timestamp}_step{step_num}_{safe_step_name}.log"

    if step.model.type == ModelType.CLAUDE_CODE:
        # Check if we should skip permissions (only in production)
        runner_env = os.environ.get('RUNNER_ENV', '').lower()
        skip_permissions = '--dangerously-skip-permissions' if runner_env == 'production' else ''

        # Create the full pipeline command using shlex for proper escaping
        # We'll write the parser script to a temp file to avoid quoting issues
        parser_script_file = Path(framework_root) / 'log_formatters' / 'claude_code.py'

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

        return (result.returncode, "CONTINUE", None)

    if step.model.type == ModelType.OPENCODE:
        parser_script_file = Path(framework_root) / 'log_formatters' / 'opencode.py'

        cmd = f"""opencode run  \
{json.dumps(step.prompt)} \
--format json | tee {log_file} | python3 -u {parser_script_file}"""

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
