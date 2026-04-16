"""
GitHub operations for repository creation and pushing.
"""

import os
import shutil
import subprocess

import requests


def create_github_repo(repo_name: str, github_token: str, private: bool = True) -> tuple[bool, str, str, int]:
    """
    Create a new GitHub repository via API.
    - POST to https://api.github.com/user/repos
    - Handle error cases (repo already exists, etc.)
    - Return (success, repo_url, owner_name, repo_id)
    """
    try:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {github_token}"
        }

        payload = {
            "name": repo_name,
            "private": private
        }

        response = requests.post(
            "https://api.github.com/user/repos",
            headers=headers,
            json=payload
        )

        if response.status_code == 201:
            data = response.json()
            repo_url = data.get("html_url", "")
            owner = data.get("owner", {}).get("login", "")
            repo_id = data.get("id", 0)
            print(f"Repository created successfully: {repo_url}")
            return True, repo_url, owner, repo_id
        else:
            print(f"Failed to create repository. HTTP status: {response.status_code}")
            print(response.text)
            return False, "", "", 0
    except Exception as e:
        print(f"Exception creating GitHub repo: {e}")
        return False, "", "", 0


def invite_collaborator(owner: str, repo_name: str, github_token: str, github_handle: str, permission: str = "push") -> bool:
    """
    Invite a collaborator to the repository.
    - PUT to https://api.github.com/repos/{owner}/{repo}/collaborators/{handle}
    - Handle cases where user is already a collaborator
    - Return success status
    """
    try:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {github_token}"
        }

        payload = {
            "permission": permission
        }

        response = requests.put(
            f"https://api.github.com/repos/{owner}/{repo_name}/collaborators/{github_handle}",
            headers=headers,
            json=payload
        )

        if response.status_code == 201:
            print(f"Collaborator invite sent successfully to {github_handle}")
            return True
        elif response.status_code == 204:
            print(f"{github_handle} is already a collaborator on this repository")
            return True
        else:
            print(f"Failed to send collaborator invite. HTTP status: {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print(f"Exception inviting collaborator: {e}")
        return False


def install_github_app_on_repo(installation_id: str, repository_id: int, github_token: str) -> bool:
    """
    Add a repository to an existing GitHub App installation.
    - PUT to https://api.github.com/user/installations/{installation_id}/repositories/{repository_id}
    - Requires the token owner to have permissions to manage the app installation
    - Return success status
    """
    try:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {github_token}"
        }

        response = requests.put(
            f"https://api.github.com/user/installations/{installation_id}/repositories/{repository_id}",
            headers=headers
        )

        if response.status_code == 204:
            print(f"GitHub App (installation {installation_id}) installed on repository {repository_id}")
            return True
        else:
            print(f"Failed to install GitHub App. HTTP status: {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print(f"Exception installing GitHub App: {e}")
        return False


def setup_repo_remote(repo_path: str, github_token: str, repo_url: str) -> bool:
    """
    Setup the 'recon' remote in a repository for pushing.
    Call this BEFORE workflow runs so per-step pushes work.

    Args:
        repo_path: Path to the repository
        github_token: GitHub personal access token
        repo_url: GitHub repository URL

    Returns:
        bool: True if successful
    """
    try:
        if not repo_url.startswith("https://github.com/"):
            print(f"Invalid GitHub repository URL format: {repo_url}")
            return False

        # Extract owner/repo from URL
        parts = repo_url.replace("https://github.com/", "").rstrip("/").rstrip(".git")
        token_url = f"https://{github_token}@github.com/{parts}.git"

        original_dir = os.getcwd()
        os.chdir(repo_path)

        try:
            # Initialize git if not already
            if not os.path.exists(".git"):
                subprocess.run(["git", "init"], check=True, capture_output=True)
                subprocess.run(["git", "branch", "-M", "main"], check=True, capture_output=True)

            # Delete the .github folder (workflows etc)
            github_dir = ".github"
            if os.path.exists(github_dir):
                shutil.rmtree(github_dir)

            # Add or update recon remote
            result = subprocess.run(["git", "remote", "add", "recon", token_url], capture_output=True, text=True)
            if result.returncode != 0:
                subprocess.run(["git", "remote", "set-url", "recon", token_url], check=True, capture_output=True)

            print(f"  ✓ Git remote 'recon' configured for {repo_url}")
            return True
        finally:
            os.chdir(original_dir)

    except Exception as e:
        print(f"  ⚠ Failed to setup git remote: {e}")
        return False


def push_to_github(repo_path: str, github_token: str, repo_url: str, branch: str = "main") -> bool:
    """
    Push repository to GitHub.
    - Initialize git if needed
    - Add/update remote with token-embedded URL
    - Delete .github folder
    - Add all files, commit, and push
    - Return success status
    """
    try:
        # Parse repo URL to embed token
        if not repo_url.startswith("https://github.com/"):
            print(f"Invalid GitHub repository URL format: {repo_url}")
            return False

        # Extract owner/repo from URL
        parts = repo_url.replace("https://github.com/", "").rstrip("/").rstrip(".git")
        token_url = f"https://{github_token}@github.com/{parts}.git"

        # Change to repo directory
        original_dir = os.getcwd()
        os.chdir(repo_path)

        try:
            # Initialize git if not already
            if not os.path.exists(".git"):
                print("Initializing git repository...")
                subprocess.run(["git", "init"], check=True)

            # Set main branch
            subprocess.run(["git", "branch", "-M", branch], check=True)

            # Add or update recon remote
            print("Setting up recon remote...")
            result = subprocess.run(["git", "remote", "add", "recon", token_url], capture_output=True, text=True)
            if result.returncode != 0:
                # Remote might already exist, update it
                subprocess.run(["git", "remote", "set-url", "recon", token_url], check=True)

            # Delete the .github folder
            github_dir = ".github"
            if os.path.exists(github_dir):
                shutil.rmtree(github_dir)

            # Add all files and commit
            print("Adding and committing changes...")
            subprocess.run(["git", "add", "."], check=True)

            result = subprocess.run(
                ["git", "commit", "-m", "Push to recon remote"],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print("No changes to commit or commit failed")

            # Push to recon remote
            print("Pushing to recon remote...")
            subprocess.run(["git", "push", "-u", "recon", branch], check=True)
            print("Successfully pushed to recon remote")

            return True
        finally:
            # Change back to original directory
            os.chdir(original_dir)

    except subprocess.CalledProcessError as e:
        print(f"Git command failed: {e}")
        return False
    except Exception as e:
        print(f"Exception pushing to GitHub: {e}")
        return False
