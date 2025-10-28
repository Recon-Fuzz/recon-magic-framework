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

    if step.model.type == ModelType.PROGRAM:
        # Resolve ./ paths to framework root using shlex
        command = step.prompt
        framework_root = os.environ.get('RECON_FRAMEWORK_ROOT')

        if framework_root:
            # Parse command tokens properly
            tokens = shlex.split(command)

            # Resolve any tokens starting with ./
            resolved_tokens = []
            for token in tokens:
                if token.startswith('./'):
                    token = str(Path(framework_root) / token.lstrip('./'))
                resolved_tokens.append(token)

            # Rejoin into command string
            command = shlex.join(resolved_tokens)

        # Run the program (CWD remains in target repo)
        result = subprocess.run(
            command,
            shell=True,
            env=os.environ.copy()
        )
        return (SUCCESS, "CONTINUE")

    if step.model.type == ModelType.CLAUDE_CODE:

        # Create logs directory in framework, not target repo
        framework_root = os.environ.get('RECON_FRAMEWORK_ROOT', '.')
        logs_dir = Path(framework_root) / "logs"
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


def execute_task_step_with_streaming(step: TaskStep, step_num: int, writer) -> tuple[int, str]:
    """Execute a task step with streaming support for LangGraph.
    
    Args:
        step: TaskStep configuration
        step_num: Current step number
        writer: LangGraph stream writer for emitting custom events
    
    Returns:
        Tuple of (return_code, action) where action is the next step
    """
    if step.model.type == ModelType.PROGRAM:
        # Resolve ./ paths to framework root using shlex
        command = step.prompt
        framework_root = os.environ.get('RECON_FRAMEWORK_ROOT')

        if framework_root:
            # Parse command tokens properly
            tokens = shlex.split(command)

            # Resolve any tokens starting with ./
            resolved_tokens = []
            for token in tokens:
                if token.startswith('./'):
                    token = str(Path(framework_root) / token.lstrip('./'))
                resolved_tokens.append(token)

            # Rejoin into command string
            command = shlex.join(resolved_tokens)

        writer({"log": f"Executing: {command}"})
        
        # Run the program with streaming output
        result = subprocess.run(
            command,
            shell=True,
            env=os.environ.copy(),
            capture_output=True,
            text=True
        )
        
        if result.stdout:
            for line in result.stdout.strip().split("\n"):
                if line:
                    writer({"program_output": line})
        
        if result.stderr:
            for line in result.stderr.strip().split("\n"):
                if line:
                    writer({"program_error": line})
        
        return (SUCCESS, "CONTINUE")

    if step.model.type == ModelType.CLAUDE_CODE:
        # Create logs directory in framework, not target repo
        framework_root = os.environ.get('RECON_FRAMEWORK_ROOT', '.')
        logs_dir = Path(framework_root) / "logs"
        logs_dir.mkdir(exist_ok=True)

        # Generate log filename with timestamp and step name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_step_name = step.name.lower().replace(" ", "_")
        log_file = logs_dir / f"{timestamp}_step{step_num}_{safe_step_name}.log"

        # Build the command with extended timeouts
        env = os.environ.copy()
        env['BASH_DEFAULT_TIMEOUT_MS'] = '214748364'
        env['BASH_MAX_TIMEOUT_MS'] = '214748364'

        # Check if we should skip permissions (only in production)
        runner_env = os.environ.get('RUNNER_ENV', '').lower()
        skip_permissions = '--dangerously-skip-permissions' if runner_env == 'production' else ''

        cmd_parts = [
            'claude',
            skip_permissions,
            '-p', step.prompt,
            '--max-turns', '9999999999',
            '--output-format', 'stream-json',
            '--verbose'
        ]
        
        # Filter out empty strings
        cmd_parts = [part for part in cmd_parts if part]
        
        writer({"log": f"📝 Logging to: {log_file}"})
        writer({"log": f"Executing: {' '.join(cmd_parts)}"})

        # Execute with streaming output
        try:
            # Open log file for writing
            with open(log_file, 'w') as log:
                process = subprocess.Popen(
                    cmd_parts,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    env=env,
                    text=True,
                    bufsize=1  # Line buffered
                )
                
                # Process output line by line
                if process.stdout:
                    for line in process.stdout:
                        # Write to log file
                        log.write(line)
                        log.flush()
                        
                        # Parse and stream JSON
                        line = line.strip()
                        if not line:
                            continue
                        
                        try:
                            data = json.loads(line)
                            _process_claude_json_streaming(data, writer)
                        except json.JSONDecodeError:
                            # Not JSON, just log it
                            writer({"log": line})
                
                # Wait for process to complete
                return_code = process.wait()
                
                return (return_code, "CONTINUE")
                
        except Exception as e:
            writer({"error": f"Failed to execute Claude CLI: {str(e)}"})
            return (FAILURE, "CONTINUE")
    
    else:
        writer({"log": f"Skipping {step.name}: Model type {step.model.type} not supported yet"})
        return (SUCCESS, "CONTINUE")


def _process_claude_json_streaming(data: dict, writer) -> None:
    """Process a single line of JSON output from Claude CLI and emit to stream.
    
    Args:
        data: Parsed JSON object
        writer: LangGraph stream writer
    """
    if data.get('type') == 'assistant' and data.get('message', {}).get('content'):
        for item in data['message']['content']:
            if item.get('type') == 'text':
                text = item.get('text', '')
                if text:
                    writer({
                        "claude": "thought",
                        "content": f"💭 {text}"
                    })
            elif item.get('type') == 'tool_use':
                tool_name = item.get('name', 'unknown')
                if 'input' in item and 'command' in item['input']:
                    writer({
                        "claude": "tool_use",
                        "tool": tool_name,
                        "content": f"⚡ [{tool_name}] {item['input']['command']}"
                    })
                else:
                    writer({
                        "claude": "tool_use",
                        "tool": tool_name,
                        "content": f"⚡ [{tool_name}]"
                    })
    
    elif data.get('type') == 'user' and data.get('message', {}).get('content'):
        for item in data['message']['content']:
            if item.get('type') == 'tool_result' and item.get('is_error'):
                tool_name = item.get('tool_use', {}).get('name', 'unknown')
                error_line = item.get('content', '').split('\n')[0]
                writer({
                    "claude": "error",
                    "tool": tool_name,
                    "content": f"❌ [{tool_name}] {error_line}"
                })

