"""
Main entry point for running LangGraph workflows.
"""

import asyncio
import sys
from pathlib import Path


async def run_graph(graph_name: str = "graph"):
    """
    Load and execute a LangGraph workflow with streaming output.
    
    Args:
        graph_name: Name of the graph module to run (default: "graph")
    """
    print(f"\n{'#'*60}")
    print(f"# Running LangGraph: {graph_name}")
    print(f"{'#'*60}\n")
    
    # Import the graph dynamically
    try:
        if graph_name == "audit_graph":
            from agents.audit_graph import graph
        else:
            # For future graphs, import from agents.{graph_name}
            module = __import__(f"agents.{graph_name}", fromlist=["graph"])
            graph = module.graph
    except ImportError as e:
        print(f"❌ Error: Could not import graph '{graph_name}'")
        print(f"   {e}")
        return 1
    
    # Execute the graph with streaming
    try:
        async for chunk in graph.astream({}, stream_mode=["updates", "custom"]):
            # Handle different stream modes
            if isinstance(chunk, tuple) and len(chunk) == 2:
                mode, data = chunk
                
                if mode == "custom":
                    # Handle custom streaming events
                    _display_custom_event(data)
                elif mode == "updates":
                    # Handle node updates
                    for node_name, node_data in data.items():
                        if node_data:
                            print(f"\n[Node: {node_name}] {node_data}")
            else:
                # Fallback for simple chunks
                print(chunk)
        
        print(f"\n{'#'*60}")
        print(f"# Graph '{graph_name}' completed successfully!")
        print(f"{'#'*60}\n")
        
        return 0
    except Exception as e:
        print(f"\n❌ Graph execution failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


def _display_custom_event(data: dict) -> None:
    """Display custom streaming events from the graph.
    
    Args:
        data: Custom event data dictionary
    """
    # Task lifecycle events
    if "task" in data:
        if data["task"] == "start":
            print(f"\n{'='*60}")
            print(f"▶ Starting task: {data.get('name', 'unknown')}")
            print(f"{'='*60}")
        elif data["task"] == "complete":
            print(f"\n{'='*60}")
            print(f"✓ Completed task: {data.get('name', 'unknown')}")
            print(f"{'='*60}")
        elif data["task"] == "failed":
            print(f"\n{'='*60}")
            print(f"❌ Failed task: {data.get('name', 'unknown')} (code: {data.get('return_code')})")
            print(f"{'='*60}")
    
    # Decision lifecycle events
    elif "decision" in data:
        if data["decision"] == "start":
            print(f"\n{'='*60}")
            print(f"🔀 Evaluating decision: {data.get('name', 'unknown')}")
            print(f"{'='*60}")
        elif data["decision"] == "complete":
            print(f"\n{'='*60}")
            print(f"✓ Decision result: {data.get('action', 'unknown')}")
            print(f"{'='*60}")
        elif data["decision"] == "failed":
            print(f"\n{'='*60}")
            print(f"❌ Failed decision: {data.get('name', 'unknown')}")
            print(f"{'='*60}")
    
    # Claude streaming events
    elif "claude" in data:
        content = data.get("content", "")
        if data["claude"] == "thought":
            print(content)
        elif data["claude"] == "tool_use":
            print(content)
        elif data["claude"] == "error":
            print(content)
    
    # Program output
    elif "program_output" in data:
        print(f"  {data['program_output']}")
    elif "program_error" in data:
        print(f"  ⚠️  {data['program_error']}")
    
    # General logs
    elif "log" in data:
        print(f"  {data['log']}")
    
    # Errors
    elif "error" in data:
        print(f"  ❌ {data['error']}")



def main():
    """
    Main CLI entry point.
    
    Usage:
        python main.py [graph_name]
    
    The graph_name defaults to "graph" if not specified.
    """
    # Parse command line arguments
    graph_name = sys.argv[1] if len(sys.argv) > 1 else "audit_graph"
    
    # Run the async workflow
    return_code = asyncio.run(run_graph(graph_name))
    
    sys.exit(return_code)


if __name__ == "__main__":
    main()
