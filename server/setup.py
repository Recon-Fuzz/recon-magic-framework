"""
Setup operations for workspace and repository cloning.
"""

import os
import shutil
import subprocess


def setup_workspace() -> bool:
    """
    Clean up old repos and claude definitions, create artifacts directory.
    - Remove ./repo and ./.claude directories
    - Create ./artifacts directory
    - Return success status
    """
    try:
        # Remove old directories
        if os.path.exists("repo"):
            shutil.rmtree("repo")
        if os.path.exists(".claude"):
            shutil.rmtree(".claude")

        # Create artifacts directory
        os.makedirs("artifacts", exist_ok=True)

        return True
    except Exception as e:
        print(f"Error setting up workspace: {e}")
        return False


def clone_repository(repo_url: str, repo_ref: str = "main", target_dir: str = "repo") -> bool:
    """
    Clone a git repository with submodules.
    - Clone with --recurse-submodules
    - Checkout specific branch/ref
    - Clone to target directory
    """
    try:
        cmd = [
            "git", "clone",
            "--recurse-submodules",
            "-b", repo_ref,
            "--single-branch",
            repo_url,
            target_dir
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"Error cloning repository: {result.stderr}")
            return False

        return True
    except Exception as e:
        print(f"Exception cloning repository: {e}")
        return False


def clone_claude_config(claude_url: str, claude_ref: str = "main", target_dir: str = ".claude") -> bool:
    """
    Clone Claude configuration repository.
    - Clone with --recurse-submodules
    - Checkout specific branch/ref
    - Clone to .claude directory
    """
    try:
        cmd = [
            "git", "clone",
            "--recurse-submodules",
            "-b", claude_ref,
            "--single-branch",
            claude_url,
            target_dir
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"Error cloning Claude config: {result.stderr}")
            return False

        return True
    except Exception as e:
        print(f"Exception cloning Claude config: {e}")
        return False
