"""
CLI entry point for recon-magic framework.
Use this when using recon-magic framework locally.
"""

import argparse
import json
import os
import sys
import tempfile
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
        recon --prompt "your prompt" [options]
    """
    parser = argparse.ArgumentParser(
        description='Execute a recon-magic workflow or direct prompt',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run a workflow by name
  recon-magic-framework --workflow audit              # Uses framework's workflows/audit.json
  recon-magic-framework --workflow workflow-loop      # Uses framework's workflows/workflow-loop.json
  recon-magic-framework --workflow ./my-workflow.json --dangerous --cap 10
  recon-magic-framework --workflow /absolute/path/to/workflow.json --logs ./custom-logs

  # Run a direct prompt
  recon-magic-framework --prompt "Analyze this code for security issues" --dangerous
  recon-magic-framework --prompt "Add tests" --model-type CLAUDE_CODE --repo ./my-repo
  recon-magic-framework --prompt "npm run build" --model-type PROGRAM

  # Resume from a specific step by ID
  recon-magic-framework --workflow audit --resume-from-step-id "audit:3"

Workflows can be run from any directory.
        """
    )

    # Mutually exclusive group for workflow vs prompt
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        '--workflow',
        type=str,
        help='Workflow name (e.g. "audit") or path to workflow JSON file (relative or absolute)'
    )

    mode_group.add_argument(
        '--prompt',
        type=str,
        help='Direct prompt to execute (creates a single-step workflow)'
    )

    parser.add_argument(
        '--model-type',
        type=str,
        default='CLAUDE_CODE',
        choices=['CLAUDE_CODE', 'OPENCODE', 'PROGRAM'],
        help='Model type for direct prompt mode (default: CLAUDE_CODE)'
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

    parser.add_argument(
        '--resume-from-step-id',
        type=str,
        default=None,
        metavar='ID',
        help='Resume workflow from step with internal ID (e.g., "audit:2", "workflow-fuzzing:3")'
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

    # Set prompts directory (where agent reference documents live)
    os.environ['PROMPTS_DIR'] = str(framework_root / 'prompts')

    # Determine workflow file
    if args.prompt:
        # Direct prompt mode - create dynamic workflow
        workflow = {
            "name": "Direct Prompt Execution",
            "steps": [{
                "type": "task",
                "name": "Execute Direct Prompt",
                "description": f"Direct prompt execution with {args.model_type}",
                "prompt": args.prompt,
                "model": {
                    "type": args.model_type,
                    "model": "inherit"
                },
                "shouldCreateSummary": False,
                "shouldCommitChanges": True
            }]
        }

        # Write to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(workflow, f, indent=2)
            workflow_file = f.name

        print(f"🎯 Target repo: {repo_root}")
        print(f"💬 Direct Prompt Mode - Model: {args.model_type}")
        print(f"📝 Prompt: {args.prompt[:100]}..." if len(args.prompt) > 100 else f"📝 Prompt: {args.prompt}")
    else:
        # Workflow mode - resolve workflow file
        workflow_file = args.workflow

        # If it's just a name (no path separators), look in framework workflows/
        if os.sep not in workflow_file and '/' not in workflow_file:
            # Strip .json if user included it, we add it back
            if workflow_file.endswith('.json'):
                workflow_file = workflow_file[:-5]
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
    if args.resume_from_step_id:
        print(f"🔄 Resume mode: Starting from step ID '{args.resume_from_step_id}'")
    print()

    # Run the workflow
    exit_code = run_workflow(
        workflow_file=workflow_file,
        dangerous=args.dangerous,
        loop_hardcap=args.cap,
        logs_dir=args.logs,
        repo_path=repo_root,
        resume_from_step_id=args.resume_from_step_id
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
