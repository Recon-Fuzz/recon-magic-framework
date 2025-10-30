"""
CLI entry point for recon-magic framework.
Use this when using recon-magic framework locally.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

from main import main as run_workflow

# Load environment variables from .env file
load_dotenv()


def main():
    """
    Main CLI entry point.

    Usage:
        recon [workflow_file]

    The workflow_file defaults to "workflows/workflow.json" if not specified.
    The command must be run from the root of a target repository.
    """
    # Store the repository root (where the command is run from)
    repo_root = os.getcwd()

    # Get framework root (where this cli.py is installed)
    framework_root = Path(__file__).parent.resolve()

    # Set environment variable for framework root so other modules can resolve paths
    os.environ['RECON_FRAMEWORK_ROOT'] = str(framework_root)

    # Check if we're in a git repository
    if not (Path(repo_root) / ".git").exists():
        print("❌ Error: Must run from the root of a git repository")
        print("   Navigate to your target repo and run 'recon' from there")
        sys.exit(1)

    # Parse workflow file argument
    workflow_file = sys.argv[1] if len(sys.argv) > 1 else "workflows/workflow.json"

    # If relative path, resolve it relative to the framework installation
    if not os.path.isabs(workflow_file):
        workflow_file = str(framework_root / workflow_file)

    # Check if workflow file exists
    if not os.path.exists(workflow_file):
        print(f"❌ Error: Workflow file not found: {workflow_file}")
        sys.exit(1)

    print(f"🎯 Target repo: {repo_root}")
    print(f"📋 Workflow: {workflow_file}\n")

    # Run the workflow
    exit_code = run_workflow(workflow_file)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
