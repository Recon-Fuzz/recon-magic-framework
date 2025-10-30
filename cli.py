"""
CLI entry point for recon-magic framework.
Use this when using recon-magic framework locally.
"""

import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

from main import run_workflow, DEFAULT_LOOP_HARDCAP

# Load environment variables from .env file
load_dotenv()


def main():
    """
    Main CLI entry point.

    Usage:
        recon --workflow <workflow_file> [options]
    """
    parser = argparse.ArgumentParser(
        description='Execute a recon-magic workflow',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  recon --workflow ./workflows/audit.json
  recon --workflow ./my-workflow.json --dangerous --cap 10
  recon --workflow /absolute/path/to/workflow.json --logs ./custom-logs

Workflows can be run from any directory.
        """
    )

    parser.add_argument(
        '--workflow',
        type=str,
        required=True,
        help='Path to workflow JSON file (relative or absolute)'
    )

    parser.add_argument(
        '--dangerous',
        action='store_true',
        help='Enable dangerous mode (skip permissions)'
    )

    parser.add_argument(
        '--cap',
        type=int,
        default=DEFAULT_LOOP_HARDCAP,
        help=f'Maximum number of times a decision step can loop (default: {DEFAULT_LOOP_HARDCAP})'
    )

    parser.add_argument(
        '--logs',
        type=str,
        default=None,
        help='Directory to store logs (default: framework logs/)'
    )

    args = parser.parse_args()

    # Store the repository root (where the command is run from)
    repo_root = os.getcwd()

    # Get framework root (where this cli.py is installed)
    framework_root = Path(__file__).parent.resolve()

    # Set environment variable for framework root so other modules can resolve paths
    os.environ['RECON_FRAMEWORK_ROOT'] = str(framework_root)

    # Resolve workflow file
    workflow_file = args.workflow

    # If relative path, resolve it relative to current directory (not framework)
    if not os.path.isabs(workflow_file):
        workflow_file = os.path.abspath(workflow_file)

    # Check if workflow file exists
    if not os.path.exists(workflow_file):
        print(f"❌ Error: Workflow file not found: {workflow_file}")
        sys.exit(1)

    print(f"🎯 Target repo: {repo_root}")
    print(f"📋 Workflow: {workflow_file}")
    if args.dangerous:
        print(f"⚠️  Dangerous mode: ENABLED")
    if args.logs:
        print(f"📝 Logs directory: {args.logs}")
    print()

    # Run the workflow (repo_path is None since we're running in current dir)
    exit_code = run_workflow(
        workflow_file=workflow_file,
        dangerous=args.dangerous,
        loop_hardcap=args.cap,
        logs_dir=args.logs,
        repo_path=None  # CLI runs in current directory
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
