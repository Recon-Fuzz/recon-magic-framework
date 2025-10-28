"""
Utility functions for LangGraph workflow execution.
"""

from typing import Any, Dict, Callable
import asyncio
import json
import subprocess

from langgraph.config import get_stream_writer
from agents.utilities.decision import DecisionStep, execute_decision_step
from agents.utilities.task import TaskStep, execute_task_step_with_streaming
from agents.utilities.git_commit import is_git_repo, init_git_repo, run_command

SUCCESS = 0
FAILURE = 1


def create_task_node(step_config: TaskStep, step_name: str) -> Callable:
    """Create a task execution node.
    
    Args:
        step_config: TaskStep configuration
        step_name: Name of the step for logging
    
    Returns:
        Async function that executes the task
    """
    async def task_node(state, runtime) -> Dict[str, Any]:
        writer = get_stream_writer()
        
        writer({"task": "start", "name": step_name})
        writer({"log": f"[Task] {step_name}"})
        writer({"log": f"Type: {step_config.type}"})
        writer({"log": f"Model: {step_config.model.type}"})
        writer({"log": f"Description: {step_config.description or 'N/A'}"})
        
        # Execute the task in a thread pool with streaming support
        return_code, action = await asyncio.to_thread(
            execute_task_step_with_streaming, step_config, 0, writer
        )
        
        if return_code != SUCCESS:
            writer({"log": f"❌ {step_name} failed with return code {return_code}"})
            writer({"task": "failed", "name": step_name, "return_code": return_code})
            return {"should_stop": True}
        
        writer({"log": f"✓ {step_name} completed successfully"})
        writer({"task": "complete", "name": step_name})
        
        # Handle post-step actions
        if step_config.shouldCreateSummary:
            await asyncio.to_thread(create_summary, step_config, step_name, writer)
        
        if step_config.shouldCommitChanges:
            await asyncio.to_thread(commit_changes, step_config, step_name, writer)
        
        return {}
    
    return task_node


def create_decision_node(step_config: DecisionStep, step_name: str) -> Callable:
    """Create a decision evaluation node.
    
    Args:
        step_config: DecisionStep configuration
        step_name: Name of the step for logging
    
    Returns:
        Async function that evaluates the decision
    """
    async def decision_node(state, runtime) -> Dict[str, Any]:
        writer = get_stream_writer()
        
        writer({"decision": "start", "name": step_name})
        writer({"log": f"[Decision] {step_name}"})
        writer({"log": f"Description: {step_config.description or 'N/A'}"})
        
        # Execute the decision in a thread pool to avoid blocking
        return_code, action = await asyncio.to_thread(execute_decision_step, step_config, 0)
        
        if return_code != SUCCESS:
            writer({"log": f"❌ {step_name} failed with return code {return_code}"})
            writer({"decision": "failed", "name": step_name, "return_code": return_code})
            return {"should_stop": True}
        
        writer({"log": f"✓ {step_name} evaluated: {action}"})
        writer({"decision": "complete", "name": step_name, "action": action})
        
        # Map action to state update
        if action == "STOP":
            return {"should_stop": True}
        
        return {"should_stop": False}
    
    return decision_node


def create_summary(step: TaskStep | DecisionStep, step_name: str, writer) -> None:
    """Create a summary for the completed step."""
    writer({"log": f"📝 Creating summary for {step_name}"})
    writer({"log": "⚠ Summary creation not yet implemented"})


def commit_changes(step: TaskStep | DecisionStep, step_name: str, writer) -> None:
    """Commit changes made during the step execution."""
    writer({"log": f"💾 Committing changes for {step_name}"})
    
    # Check if git repo exists, initialize if not
    if not is_git_repo():
        writer({"log": "  Initializing git repository..."})
        if not init_git_repo(verbose=False):
            writer({"log": "  ❌ Failed to initialize git repository"})
            return
        writer({"log": "  ✓ Git repository initialized successfully"})
    
    # Check if there are any changes to commit
    success, stdout, _ = run_command("git status --porcelain")
    if not success:
        writer({"log": "  ❌ Failed to check git status"})
        return
    
    if not stdout:
        writer({"log": "  ℹ️  No changes to commit"})
        return
    
    # Add all changes
    writer({"log": "  Adding changes..."})
    success, _, stderr = run_command("git add .")
    if not success:
        writer({"log": f"  ❌ Failed to add changes: {stderr}"})
        return
    
    # Commit changes with a descriptive message
    commit_message = f"{step_name}: {step.name}"
    if step.description:
        commit_message += f"\n\n{step.description}"
    
    writer({"log": f"  Committing with message: '{commit_message.split(chr(10))[0]}'"})
    
    # Escape single quotes in the message
    escaped_message = commit_message.replace("'", "'\\''")
    success, stdout, stderr = run_command(f"git commit -m '{escaped_message}'")
    
    if success:
        writer({"log": "  ✓ Changes committed successfully!"})
    else:
        # Check if the error is due to no changes staged
        if "nothing to commit" in stderr or "nothing to commit" in stdout:
            writer({"log": "  ℹ️  No changes to commit (all changes may be ignored by .gitignore)"})
        else:
            writer({"log": f"  ❌ Failed to commit changes: {stderr}"})
