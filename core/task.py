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
        # Check if we should skip permissions (only in production)
        runner_env = os.environ.get('RUNNER_ENV', '').lower()
        skip_permissions = '--dangerously-skip-permissions' if runner_env == 'production' else ''

        # Create the full pipeline command using shlex for proper escaping
        # We'll write the parser script to a temp file to avoid quoting issues
        parser_script_file = Path(framework_root) / 'log_formatters' / 'claude_code.py'

        # Process prompt - if it references an agent file, read and inject its content
        prompt = step.prompt
        import re
        agent_file_match = re.search(r'\./(\.opencode|\.claude)/agents?/([^.\s]+)\.md', prompt)
        if agent_file_match:
            # Handle both 'agent' and 'agents' directory names
            agent_dir = 'agents' if agent_file_match.group(1) == '.claude' else 'agent'
            agent_file_path = Path(framework_root) / agent_file_match.group(1) / agent_dir / f"{agent_file_match.group(2)}.md"
            if agent_file_path.exists():
                print(f"  Loading agent definition from: {agent_file_path}")
                agent_content = agent_file_path.read_text()
                # Extract content after frontmatter (between --- markers)
                parts = agent_content.split('---', 2)
                if len(parts) >= 3:
                    # Use everything after the second ---
                    prompt = parts[2].strip()
                else:
                    # No frontmatter, use full content
                    prompt = agent_content
            else:
                print(f"  ⚠ Agent file not found: {agent_file_path}")

        cmd = f"""claude {skip_permissions} \
-p {shlex.quote(json.dumps(prompt))} \
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

        # Default model - can be overridden via OPENCODE_MODEL env var
        model = os.environ.get('OPENCODE_MODEL', 'openrouter/anthropic/claude-sonnet-4.5')

        # Process prompt - if it references an agent file, read and inject its content
        prompt = step.prompt
        import re
        agent_file_match = re.search(r'\./(\.opencode|\.claude)/agent/([^.\s]+)\.md', prompt)
        if agent_file_match:
            agent_file_path = Path(framework_root) / agent_file_match.group(1) / 'agent' / f"{agent_file_match.group(2)}.md"
            if agent_file_path.exists():
                print(f"  Loading agent definition from: {agent_file_path}")
                agent_content = agent_file_path.read_text()
                # Extract content after frontmatter (between --- markers)
                parts = agent_content.split('---', 2)
                if len(parts) >= 3:
                    # Use everything after the second ---
                    prompt = parts[2].strip()
                else:
                    # No frontmatter, use full content
                    prompt = agent_content
            else:
                print(f"  ⚠ Agent file not found: {agent_file_path}")

        cmd = f"""opencode run  \
{shlex.quote(json.dumps(prompt))} \
-m {model} \
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
