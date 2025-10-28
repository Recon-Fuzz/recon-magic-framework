"""LangGraph workflow execution graph.

Defines the Audit Workflow as a LangGraph.
"""

from __future__ import annotations

from dataclasses import dataclass

from langgraph.graph import StateGraph, END

from agent.nodes import add_task, add_decision


@dataclass
class State:
    """State for the workflow graph.
    
    This tracks data that flows through the workflow as it executes.
    """

    should_stop: bool = False
    """Whether workflow should stop based on decision"""
    
    messages: list[str] = None
    """List of messages/logs from execution"""
    
    def __post_init__(self):
        if self.messages is None:
            self.messages = []


def route_after_decision(state: State) -> str:
    """Route after the critical stop decision."""
    if state.should_stop:
        print("\n🛑 STOP action triggered by decision step")
        print("Halting workflow execution early.")
        return END
    return "phase_1"


# Build the Audit Workflow graph
graph = (
    StateGraph(State)
    .add_node("phase_0", add_task(
        name="Phase 0",
        description="Initial Scoping",
        prompt="You are provided an agent definition at ./claude/agents/audit-naive-phase-0.md. Run exclusively the phase audit-naive-phase-0 using the Task tool"
    ))
    .add_node("stop_decision", add_decision(
        name="Critical Stop Decision",
        description="Check if CRITICAL_STOP.MD exists to determine if workflow should stop early",
        mode="READ_FILE",
        mode_info={"fileName": "CRITICAL_STOP.MD"},
        decisions=[
            {"operator": "eq", "value": 1, "action": "STOP"},
            {"operator": "eq", "value": 0, "action": "CONTINUE"}
        ]
    ))
    .add_node("phase_1", add_task(
        name="Phase 1",
        description="Issues Generation",
        prompt="You are provided an agent definition at ./claude/agents/audit-naive-phase-1.md. Run exclusively the phase audit-naive-phase-1 using the Task tool"
    ))
    .add_edge("__start__", "phase_0")
    .add_edge("phase_0", "stop_decision")
    .add_conditional_edges("stop_decision", route_after_decision, ["phase_1", END])
    .add_edge("phase_1", END)
    .compile(name="Audit Workflow")
)