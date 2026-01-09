"""
Setup operations for workspace and repository cloning.
"""

import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse


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


def _inject_github_token(repo_url: str) -> str:
    """Inject GitHub token into https URL when available."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return repo_url
    parsed = urlparse(repo_url)
    if parsed.scheme != "https" or parsed.netloc != "github.com":
        return repo_url
    if "@" in parsed.netloc:
        return repo_url
    return f"https://{token}@github.com{parsed.path}"


def clone_claude_config(claude_url: str, claude_ref: str = "main", target_dir: str = "/app/.claude") -> bool:
    """
    Clone Claude configuration repository.
    - Clone with --recurse-submodules
    - Checkout specific branch/ref
    - Clone to .claude directory (default: /app/.claude)
    """
    try:
        if os.path.isdir("/app/.ai-agent-primers"):
            source_dir = "/app/.ai-agent-primers"
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir)
            source_path = Path(source_dir) / "agents"
            if not source_path.exists():
                source_path = Path(source_dir) / "agent"
            if source_path.exists():
                target_path = Path(target_dir) / source_path.name
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(source_path, target_path)
                return True
            print("Error: ai-agent-primers missing agents/ or agent/ directory")
            return False

        cmd = [
            "git", "clone",
            "--recurse-submodules",
            "-b", claude_ref,
            "--single-branch",
            _inject_github_token(claude_url),
            target_dir
        ]
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)

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
        if os.path.isdir("/app/.ai-agent-primers"):
            source_dir = "/app/.ai-agent-primers"
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir)
            source_path = Path(source_dir) / "agent"
            if not source_path.exists():
                source_path = Path(source_dir) / "agents"
            if source_path.exists():
                target_path = Path(target_dir) / source_path.name
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(source_path, target_path)
                return True
            print("Error: ai-agent-primers missing agent/ or agents/ directory")
            return False

        cmd = [
            "git", "clone",
            "--recurse-submodules",
            "-b", opencode_ref,
            "--single-branch",
            _inject_github_token(opencode_url),
            target_dir
        ]
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)

        if result.returncode != 0:
            print(f"Error cloning OpenCode config: {result.stderr}")
            return False

        return True
    except Exception as e:
        print(f"Exception cloning OpenCode config: {e}")
        return False
