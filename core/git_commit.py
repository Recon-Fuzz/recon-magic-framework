#!/usr/bin/env python3
"""
Git commit utility library that handles repos that may or may not be initialized.
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd, cwd=None, check=False):
    """Run a shell command and return the result."""
    result = subprocess.run(
        cmd,
        cwd=cwd,
        shell=True,
        capture_output=True,
        text=True,
        check=False  # Never raise, always return output
    )
    return result.returncode == 0, result.stdout.strip(), result.stderr.strip()


def is_git_repo(path="."):
    """Check if the current directory is a git repository."""
    success, _, _ = run_command("git rev-parse --git-dir", cwd=path, check=False)
    return success


def init_git_repo(path=".", verbose=True):
    """Initialize a git repository."""
    if verbose:
        print("Initializing git repository...")
    success, stdout, stderr = run_command("git init", cwd=path)
    if success:
        if verbose:
            print("Git repository initialized successfully.")
        return True
    else:
        if verbose:
            print(f"Failed to initialize git repository: {stderr}")
        return False


def commit_changes(message, path="."):
    """
    Commit changes to the git repository.
    Handles initialization if the repo doesn't exist.

    Args:
        message: Commit message
        path: Path to the repository (default: current directory)

    Returns:
        bool: True if successful, False otherwise
    """
    # Check if git repo exists, initialize if not
    if not is_git_repo(path):
        if not init_git_repo(path):
            return False

    # Check if there are any changes to commit
    success, stdout, _ = run_command("git status --porcelain", cwd=path)
    if not success:
        print("Failed to check git status")
        return False

    if not stdout:
        print("No changes to commit")
        return True

    # Add all changes
    print("Adding changes...")
    success, _, stderr = run_command("git add .", cwd=path)
    if not success:
        print(f"Failed to add changes: {stderr}")
        return False

    # Commit changes
    print(f"Committing with message: '{message}'")
    # Escape single quotes in the message
    escaped_message = message.replace("'", "'\\''")
    success, stdout, stderr = run_command(f"git commit -m '{escaped_message}'", cwd=path)

    if success:
        print("Changes committed successfully!")
        print(stdout)
        return True
    else:
        # Check if the error is due to no changes staged (can happen with .gitignore)
        if "nothing to commit" in stderr or "nothing to commit" in stdout:
            print("No changes to commit (all changes may be ignored by .gitignore)")
            return True
        print(f"Failed to commit changes: {stderr}")
        return False


def main():
    """Main function to handle command line usage."""
    if len(sys.argv) < 2:
        print("Usage: python git_commit.py <commit_message> [path]")
        print("Example: python git_commit.py 'Initial commit'")
        print("Example: python git_commit.py 'Add new feature' /path/to/repo")
        sys.exit(1)

    commit_message = sys.argv[1]
    repo_path = sys.argv[2] if len(sys.argv) > 2 else "."

    success = commit_changes(commit_message, repo_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
