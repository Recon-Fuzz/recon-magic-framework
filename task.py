"""
Task execution module for workflow steps.
"""

import json
import os
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
    OPENROUTER = "OPENROUTER"


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


def execute_task_step(step: TaskStep, step_num: int) -> tuple[int, str]:
    """Execute a task step based on its model type."""
    if step.model.type == ModelType.CLAUDE_CODE:

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
        print(f"Skipping {step.name}: Model type {step.model.type} not supported yet")
        return (SUCCESS, "CONTINUE")
