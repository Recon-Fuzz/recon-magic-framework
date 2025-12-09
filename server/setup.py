"""
Setup operations for workspace and repository cloning.
"""

import os
import shutil
import subprocess


def setup_workspace(workspace_root: str = "/app") -> bool:
    """
    Clean up old repos and config directories, create artifacts directory.
    - Remove repo, .claude, and .opencode directories
    - Create artifacts directory
    - Return success status

    Args:
        workspace_root: Base directory for workspace (default: /app)
    """
    try:
        repo_path = os.path.join(workspace_root, "repo")
        claude_path = os.path.join(workspace_root, ".claude")
        opencode_path = os.path.join(workspace_root, ".opencode")
        artifacts_path = os.path.join(workspace_root, "artifacts")

        # Remove old directories
        if os.path.exists(repo_path):
            shutil.rmtree(repo_path)
        if os.path.exists(claude_path):
            shutil.rmtree(claude_path)
        if os.path.exists(opencode_path):
            shutil.rmtree(opencode_path)

        # Create artifacts directory
        os.makedirs(artifacts_path, exist_ok=True)

        return True
    except Exception as e:
        print(f"Error setting up workspace: {e}")
        return False


def clone_repository(repo_url: str, repo_ref: str = "main", target_dir: str = "/app/repo") -> bool:
    """
    Clone a git repository with submodules.
    - Clone with --recurse-submodules
    - Checkout specific branch/ref
    - Clone to target directory (default: /app/repo)
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


def clone_claude_config(claude_url: str, claude_ref: str = "main", target_dir: str = "/app/.claude") -> bool:
    """
    Clone Claude configuration repository.
    - Clone with --recurse-submodules
    - Checkout specific branch/ref
    - Clone to .claude directory (default: /app/.claude)
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


def clone_opencode_config(opencode_url: str, opencode_ref: str = "main", target_dir: str = "/app/.opencode") -> bool:
    """
    Clone OpenCode configuration repository.
    - Clone with --recurse-submodules
    - Checkout specific branch/ref
    - Clone to .opencode directory (default: /app/.opencode)
    """
    try:
        cmd = [
            "git", "clone",
            "--recurse-submodules",
            "-b", opencode_ref,
            "--single-branch",
            opencode_url,
            target_dir
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"Error cloning OpenCode config: {result.stderr}")
            return False

        return True
    except Exception as e:
        print(f"Exception cloning OpenCode config: {e}")
        return False
