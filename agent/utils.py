"""
Utility functions for LangGraph workflow execution.
"""

from typing import Any, Dict, Callable
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from decision import DecisionStep, execute_decision_step
from task import TaskStep, execute_task_step
from git_commit import is_git_repo, init_git_repo, run_command

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
        print(f"\n[Task] {step_name}")
        print(f"Type: {step_config.type}")
        print(f"Model: {step_config.model.type}")
        print(f"Description: {step_config.description or 'N/A'}")
        
        # Execute the task in a thread pool to avoid blocking
        return_code, action = await asyncio.to_thread(execute_task_step, step_config, 0)
        
        if return_code != SUCCESS:
            print(f"\n❌ {step_name} failed with return code {return_code}")
            return {"should_stop": True}
        
        print(f"\n✓ {step_name} completed successfully")
        
        # Handle post-step actions
        if step_config.shouldCreateSummary:
            await asyncio.to_thread(create_summary, step_config, step_name)
        
        if step_config.shouldCommitChanges:
            await asyncio.to_thread(commit_changes, step_config, step_name)
        
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
        print(f"\n[Decision] {step_name}")
        print(f"Description: {step_config.description or 'N/A'}")
        
        # Execute the decision in a thread pool to avoid blocking
        return_code, action = await asyncio.to_thread(execute_decision_step, step_config, 0)
        
        if return_code != SUCCESS:
            print(f"\n❌ {step_name} failed with return code {return_code}")
            return {"should_stop": True}
        
        print(f"\n✓ {step_name} evaluated: {action}")
        
        # Map action to state update
        if action == "STOP":
            return {"should_stop": True}
        
        return {"should_stop": False}
    
    return decision_node


def create_summary(step: TaskStep | DecisionStep, step_name: str) -> None:
    """Create a summary for the completed step."""
    print(f"📝 Creating summary for {step_name}")
    print("⚠ Summary creation not yet implemented")


def commit_changes(step: TaskStep | DecisionStep, step_name: str) -> None:
    """Commit changes made during the step execution."""
    print(f"\n💾 Committing changes for {step_name}")
    
    # Check if git repo exists, initialize if not
    if not is_git_repo():
        print("  Initializing git repository...")
        if not init_git_repo(verbose=False):
            print("  ❌ Failed to initialize git repository")
            return
        print("  ✓ Git repository initialized successfully")
    
    # Check if there are any changes to commit
    success, stdout, _ = run_command("git status --porcelain")
    if not success:
        print("  ❌ Failed to check git status")
        return
    
    if not stdout:
        print("  ℹ️  No changes to commit")
        return
    
    # Add all changes
    print("  Adding changes...")
    success, _, stderr = run_command("git add .")
    if not success:
        print(f"  ❌ Failed to add changes: {stderr}")
        return
    
    # Commit changes with a descriptive message
    commit_message = f"{step_name}: {step.name}"
    if step.description:
        commit_message += f"\n\n{step.description}"
    
    print(f"  Committing with message: '{commit_message.split(chr(10))[0]}'")
    
    # Escape single quotes in the message
    escaped_message = commit_message.replace("'", "'\\''")
    success, stdout, stderr = run_command(f"git commit -m '{escaped_message}'")
    
    if success:
        print("  ✓ Changes committed successfully!")
    else:
        # Check if the error is due to no changes staged
        if "nothing to commit" in stderr or "nothing to commit" in stdout:
            print("  ℹ️  No changes to commit (all changes may be ignored by .gitignore)")
        else:
            print(f"  ❌ Failed to commit changes: {stderr}")
