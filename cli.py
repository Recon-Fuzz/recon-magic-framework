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
  recon --workflow audit              # Uses framework's workflows/audit.json
  recon --workflow workflow-loop      # Uses framework's workflows/workflow-loop.json
  recon --workflow ./my-workflow.json --dangerous --cap 10
  recon --workflow /absolute/path/to/workflow.json --logs ./custom-logs

Workflows can be run from any directory.
        """
    )

    parser.add_argument(
        '--workflow',
        type=str,
        required=True,
        help='Workflow name (e.g. "audit") or path to workflow JSON file (relative or absolute)'
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

    parser.add_argument(
        '--repo',
        type=str,
        default=None,
        help='Path to repository directory (default: current directory)'
    )

    args = parser.parse_args()

    # Store the repository root (use --repo if provided, otherwise current dir)
    repo_root = args.repo if args.repo else os.getcwd()
    if args.repo:
        repo_root = os.path.abspath(args.repo)

    # Get framework root (where this cli.py is installed)
    framework_root = Path(__file__).parent.resolve()

    # Set environment variable for framework root so other modules can resolve paths
    os.environ['RECON_FRAMEWORK_ROOT'] = str(framework_root)

    # Resolve workflow file
    workflow_file = args.workflow

    # If it's just a name (no path separators), look in framework workflows/
    if os.sep not in workflow_file and '/' not in workflow_file:
        # Look in framework's workflows directory
        framework_workflow = framework_root / 'workflows' / f"{workflow_file}.json"
        if framework_workflow.exists():
            workflow_file = str(framework_workflow)
        else:
            print(f"❌ Error: Workflow '{workflow_file}.json' not found in framework workflows/")
            sys.exit(1)
    else:
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

    # Run the workflow
    exit_code = run_workflow(
        workflow_file=workflow_file,
        dangerous=args.dangerous,
        loop_hardcap=args.cap,
        logs_dir=args.logs,
        repo_path=repo_root if args.repo else None
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
