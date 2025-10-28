"""
Utility functions for LangGraph workflow execution.
"""

from typing import Any, Dict, Callable
import asyncio

from langgraph.config import get_stream_writer
from agents.utilities.decision import DecisionStep, execute_decision_step
from agents.utilities.task import TaskStep, execute_task_step
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
        
        writer({"type": "task_start", "name": step_name, "task_type": step_config.type, "model": step_config.model.type, "description": step_config.description or "N/A"})
        
        # Execute the task in a thread pool to avoid blocking
        return_code, action = await asyncio.to_thread(execute_task_step, step_config, 0)
        
        if return_code != SUCCESS:
            writer({"type": "task_error", "name": step_name, "return_code": return_code})
            return {"should_stop": True}
        
        writer({"type": "task_complete", "name": step_name})
        
        # Handle post-step actions
        if step_config.shouldCreateSummary:
            writer({"type": "summary_start", "name": step_name})
            await asyncio.to_thread(create_summary, step_config, step_name)
            writer({"type": "summary_complete", "name": step_name})
        
        if step_config.shouldCommitChanges:
            writer({"type": "commit_start", "name": step_name})
            await asyncio.to_thread(commit_changes, step_config, step_name)
            writer({"type": "commit_complete", "name": step_name})
        
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
        
        writer({"type": "decision_start", "name": step_name, "description": step_config.description or "N/A"})
        
        # Execute the decision in a thread pool to avoid blocking
        return_code, action = await asyncio.to_thread(execute_decision_step, step_config, 0)
        
        if return_code != SUCCESS:
            writer({"type": "decision_error", "name": step_name, "return_code": return_code})
            return {"should_stop": True}
        
        writer({"type": "decision_result", "name": step_name, "action": action})
        
        # Map action to state update
        if action == "STOP":
            return {"should_stop": True}
        
        return {"should_stop": False}
    
    return decision_node


def create_summary(step: TaskStep | DecisionStep, step_name: str) -> None:
    """Create a summary for the completed step."""
    # Summary creation logic would go here
    pass


def commit_changes(step: TaskStep | DecisionStep, step_name: str) -> None:
    """Commit changes made during the step execution."""
    
    # Check if git repo exists, initialize if not
    if not is_git_repo():
        if not init_git_repo(verbose=False):
            return
    
    # Check if there are any changes to commit
    success, stdout, _ = run_command("git status --porcelain")
    if not success or not stdout:
        return
    
    # Add all changes
    success, _, stderr = run_command("git add .")
    if not success:
        return
    
    # Commit changes with a descriptive message
    commit_message = f"{step_name}: {step.name}"
    if step.description:
        commit_message += f"\n\n{step.description}"
    
    # Escape single quotes in the message
    escaped_message = commit_message.replace("'", "'\\''")
    run_command(f"git commit -m '{escaped_message}'")
