# Recon Magic Framework

A LangGraph-based workflow automation framework for building multi-step AI agent workflows.

## Installation

```bash
# Create virtual environment
uv venv

# Install dependencies
uv sync
```

## Usage

### Running Workflows

Execute a LangGraph workflow:

```bash
# Run the default audit_graph workflow
python main.py

# Run a specific graph
python main.py <graph_name>
```

### Development with LangGraph Studio

Start the LangGraph development server with live visualization:

```bash
langgraph dev
```

This will:
- Start the LangGraph API server
- Open LangGraph Studio at `http://localhost:8000/studio/`
- Provide real-time graph visualization and debugging
- Auto-reload on code changes

## Project Structure

```
agents/
├── audit_graph.py          # Main audit workflow graph
└── utilities/
    ├── decision.py         # Decision step execution
    ├── task.py            # Task step execution  
    ├── git_commit.py      # Git operations
    ├── nodes.py           # Node factory functions (add_task, add_decision)
    └── utils.py           # Utility functions for async execution
```

## Creating New Workflows

1. Create a new graph file in `agents/` (e.g., `agents/my_workflow.py`)
2. Use the factory functions from `agents.utilities.nodes`:

```python
from langgraph.graph import StateGraph, END
from agents.utilities.nodes import add_task, add_decision

# Define your graph using add_task() and add_decision()
graph = (
    StateGraph(State)
    .add_node("step1", add_task(
        name="My Task",
        description="Task description",
        prompt="Your prompt here"
    ))
    .add_edge("__start__", "step1")
    .add_edge("step1", END)
    .compile(name="My Workflow")
)
```

3. Run it:
```bash
python main.py my_workflow
```