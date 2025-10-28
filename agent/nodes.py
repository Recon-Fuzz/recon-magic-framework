"""
Node factory functions for creating workflow tasks and decisions.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from decision import DecisionStep
from task import TaskStep
from agent.utils import create_task_node, create_decision_node


def add_task(name: str, description: str, prompt: str, 
             model_type: str = "CLAUDE_CODE", 
             should_summary: bool = True,
             should_commit: bool = True):
    """Factory function to create a task node.
    
    Args:
        name: Task name
        description: Task description
        prompt: Prompt for the task
        model_type: Type of model to use (default: CLAUDE_CODE)
        should_summary: Whether to create summary (default: True)
        should_commit: Whether to commit changes (default: True)
    
    Returns:
        Async function that executes the task
    """
    step_config = TaskStep(
        type="task",
        name=name,
        description=description,
        prompt=prompt,
        model={"type": model_type, "model": "inherit"},
        shouldCreateSummary=should_summary,
        shouldCommitChanges=should_commit
    )
    
    return create_task_node(step_config, name)


def add_decision(name: str, description: str, 
                 mode: str, mode_info: dict,
                 decisions: list[dict],
                 should_summary: bool = False,
                 should_commit: bool = False):
    """Factory function to create a decision node.
    
    Args:
        name: Decision name
        description: Decision description
        mode: Decision mode (READ_FILE, FILE_EXISTS, etc.)
        mode_info: Mode-specific configuration
        decisions: List of decision rules
        should_summary: Whether to create summary (default: False)
        should_commit: Whether to commit changes (default: False)
    
    Returns:
        Async function that evaluates the decision
    """
    step_config = DecisionStep(
        type="decision",
        name=name,
        description=description,
        mode=mode,
        modeInfo=mode_info,
        decision=decisions,
        shouldCreateSummary=should_summary,
        shouldCommitChanges=should_commit,
        prompt="Ignored",
        model={"type": "PROGRAM", "model": "IGNORED"}
    )
    
    return create_decision_node(step_config, name)
