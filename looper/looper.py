#!/usr/bin/env -S uv run
"""
Simple CLI script to repeat a Claude Code prompt X times.
Usage: uv run looper.py "your prompt here" --times 5 [--dangerous]
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def run_claude_code(prompt: str, dangerous: bool = False, iteration: int = 1, total: int = 1) -> int:
    """
    Execute Claude Code with the given prompt.

    Args:
        prompt: The prompt to send to Claude Code
        dangerous: Whether to skip permissions (use --dangerously-skip-permissions)
        iteration: Current iteration number
        total: Total number of iterations

    Returns:
        Return code from Claude Code execution
    """
    print(f"\n{'='*60}")
    print(f"Iteration {iteration}/{total}")
    print(f"{'='*60}\n")

    # Build the command
    env = os.environ.copy()
    env['BASH_DEFAULT_TIMEOUT_MS'] = '214748364'
    env['BASH_MAX_TIMEOUT_MS'] = '214748364'

    skip_permissions = '--dangerously-skip-permissions' if dangerous else ''

    cmd = f"claude {skip_permissions} -p \"{prompt}\" --max-turns 9999999999 --output-format stream-json --verbose"

    # Execute the command with streaming output
    result = subprocess.run(
        cmd,
        shell=True,
        env=env,
        text=True
    )

    return result.returncode


def main():
    """Main entry point for the looper CLI."""
    parser = argparse.ArgumentParser(
        description='Repeat a Claude Code prompt X times',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run looper.py "Fix all type errors" --times 3
  uv run looper.py "Run tests and fix failures" --times 5 --dangerous
  uv run looper.py "Refactor the code" -t 2 -d
        """
    )

    parser.add_argument(
        'prompt',
        type=str,
        help='The prompt to send to Claude Code'
    )

    parser.add_argument(
        '--times', '-t',
        type=int,
        default=1,
        help='Number of times to repeat the prompt (default: 1)'
    )

    parser.add_argument(
        '--dangerous', '-d',
        action='store_true',
        help='Enable dangerous mode (skip permissions with --dangerously-skip-permissions)'
    )

    args = parser.parse_args()

    # Validate times parameter
    if args.times < 1:
        print("Error: --times must be at least 1", file=sys.stderr)
        return 1

    if args.times > 100:
        print("Warning: Running more than 100 iterations may take a very long time")
        response = input("Continue? (y/N): ")
        if response.lower() != 'y':
            print("Cancelled.")
            return 0

    # Show configuration
    print(f"\nStarting Claude Code Looper")
    print(f"Prompt: {args.prompt}")
    print(f"Iterations: {args.times}")
    print(f"Dangerous mode: {'ENABLED' if args.dangerous else 'DISABLED'}")

    if args.dangerous:
        print("\nWARNING: Dangerous mode will skip all permission prompts!")
        print("This should only be used in trusted/production environments.\n")

    # Execute the prompt X times
    for i in range(1, args.times + 1):
        return_code = run_claude_code(args.prompt, args.dangerous, i, args.times)

        if return_code != 0:
            print(f"\nIteration {i} failed with return code {return_code}")
            print("Stopping execution.")
            return return_code

        print(f"\nIteration {i}/{args.times} completed successfully")

    print(f"\n{'='*60}")
    print(f"All {args.times} iterations completed successfully!")
    print(f"{'='*60}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
