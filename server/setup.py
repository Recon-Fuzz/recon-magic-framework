"""
Setup operations for workspace and repository cloning.
"""

import os
import shutil
import subprocess
import time


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


def fix_submodule_ssh_urls(repo_path: str) -> None:
    """Rewrite .gitmodules SSH URLs to HTTPS after clone"""
    gitmodules = os.path.join(repo_path, ".gitmodules")
    if not os.path.exists(gitmodules):
        print("No .gitmodules found")
        return
    
    print("Fixing SSH URLs in .gitmodules...")
    with open(gitmodules, 'r') as f:
        content = f.read()
    
    # Convert SSH and git:// to HTTPS
    updated = content.replace('git@github.com:', 'https://github.com/')
    updated = updated.replace('git://github.com/', 'https://github.com/')
    
    if updated != content:
        with open(gitmodules, 'w') as f:
            f.write(updated)
        print(".gitmodules updated")
    else:
        print("No SSH URLs found in .gitmodules")


def init_submodules(repo_path: str) -> None:
    """Initialize git submodules after fixing URLs"""
    print("🔄 Initializing submodules...")
    try:
        subprocess.run(['git', 'submodule', 'sync', '--recursive'], cwd=repo_path, check=True)
        subprocess.run(['git', 'submodule', 'update', '--init', '--recursive'], cwd=repo_path, check=True)
        print("Submodules initialized")
    except subprocess.CalledProcessError as e:
        print(f"Submodule init failed (continuing): {e}")


def clone_repository(repo_url: str, repo_ref: str = "main", target_dir: str = "/app/repo", max_retries: int = 3, retry_delay: int = 5) -> bool:
    """
    Clone a git repository with submodules.
    - Clone without --recurse-submodules initially
    - Fix SSH URLs in .gitmodules
    - Initialize submodules with HTTPS
    - Checkout specific branch/ref
    - Clone to target directory (default: /app/repo)
    - Retries up to max_retries times on failure with retry_delay seconds between attempts
    """
    last_stderr = ""
    for attempt in range(1, max_retries + 1):
        try:
            # Clean up target directory from any previous failed attempt
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir)

            cmd = [
                "git", "clone",
                "-b", repo_ref,
                "--single-branch",
                repo_url,
                target_dir
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                last_stderr = result.stderr
                print(f"Clone attempt {attempt}/{max_retries} failed: {result.stderr}")
                if attempt < max_retries:
                    print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                continue

            # Fix SSH URLs and initialize submodules
            fix_submodule_ssh_urls(target_dir)
            init_submodules(target_dir)

            return True
        except Exception as e:
            last_stderr = str(e)
            print(f"Clone attempt {attempt}/{max_retries} exception: {e}")
            if attempt < max_retries:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)

    print(f"All {max_retries} clone attempts failed. Last error: {last_stderr}")
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
