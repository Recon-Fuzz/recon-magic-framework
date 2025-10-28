"""
Main entry point for running LangGraph workflows.
"""

import asyncio
import sys
from pathlib import Path


async def run_graph(graph_name: str = "graph"):
    """
    Load and execute a LangGraph workflow.
    
    Args:
        graph_name: Name of the graph module to run (default: "graph")
    """
    print(f"\n{'#'*60}")
    print(f"# Running LangGraph: {graph_name}")
    print(f"{'#'*60}\n")
    
    # Import the graph dynamically
    try:
        if graph_name == "graph":
            from agent.graph import graph
        else:
            # For future graphs, import from agent.{graph_name}
            module = __import__(f"agent.{graph_name}", fromlist=["graph"])
            graph = module.graph
    except ImportError as e:
        print(f"❌ Error: Could not import graph '{graph_name}'")
        print(f"   {e}")
        return 1
    
    # Execute the graph with initial state
    try:
        result = await graph.ainvoke({})
        
        print(f"\n{'#'*60}")
        print(f"# Graph '{graph_name}' completed successfully!")
        print(f"{'#'*60}\n")
        
        return 0
    except Exception as e:
        print(f"\n❌ Graph execution failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


def main():
    """
    Main CLI entry point.
    
    Usage:
        python main.py [graph_name]
    
    The graph_name defaults to "graph" if not specified.
    """
    # Parse command line arguments
    graph_name = sys.argv[1] if len(sys.argv) > 1 else "graph"
    
    # Run the async workflow
    return_code = asyncio.run(run_graph(graph_name))
    
    sys.exit(return_code)


if __name__ == "__main__":
    main()
