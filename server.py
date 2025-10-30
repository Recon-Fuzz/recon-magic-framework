"""
Server module for recon-magic framework.
Use this for Prod.
"""

import os
import shutil
import subprocess
import time

import requests


# ============================================================================
# Setup Operations
# ============================================================================

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


# ============================================================================
# Job Fetching
# ============================================================================

def fetch_pending_jobs(api_url: str, bearer_token: str) -> list[dict]:
    """
    Fetch pending jobs from the API.
    - GET request to api_url with Authorization header
    - Parse JSON response
    - Return list of job objects
    """
    try:
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json"
        }

        response = requests.get(api_url, headers=headers)
        response.raise_for_status()

        data = response.json()
        return data.get("data", [])
    except Exception as e:
        print(f"Error fetching pending jobs: {e}")
        return []


def fetch_job_details(api_url: str, bearer_token: str, job_id: str) -> dict | None:
    """
    Fetch detailed job information.
    - GET request to api_url/job_id
    - Parse repoAccessData, claudeAccessData, job details
    - Return job data including urls, refs, and prompt
    """
    try:
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json"
        }

        response = requests.get(f"{api_url}/{job_id}", headers=headers)
        response.raise_for_status()

        return response.json()
    except Exception as e:
        print(f"Error fetching job details for {job_id}: {e}")
        return None


# ============================================================================
# GitHub Operations
# ============================================================================

def create_github_repo(repo_name: str, github_token: str, private: bool = True) -> tuple[bool, str, str]:
    """
    Create a new GitHub repository via API.
    - POST to https://api.github.com/user/repos
    - Handle error cases (repo already exists, etc.)
    - Return (success, repo_url, owner_name)
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
            print(f"Repository created successfully: {repo_url}")
            return True, repo_url, owner
        else:
            print(f"Failed to create repository. HTTP status: {response.status_code}")
            print(response.text)
            return False, "", ""
    except Exception as e:
        print(f"Exception creating GitHub repo: {e}")
        return False, "", ""


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


# ============================================================================
# Post-Processing Operations
# ============================================================================

def generate_summary_with_claude(repo_path: str = "./repo") -> str:
    """
    Generate a summary of changes using Claude Code.
    - Run: claude -p "Check ./repo and summarize the changes done in the last commit in 2-3 sentences..."
    - Capture and return the summary text
    """
    try:
        prompt = (
            "Check ./repo and summarize the changes done in the last commit "
            "in 2-3 sentences in markdown format, return exclusively the summary, "
            "no other text. Ignore the deletions of the Github Workflows. "
            "Do not mention the last commit but instead talk as if you performed the task."
        )

        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode == 0:
            return result.stdout.strip()
        else:
            print(f"Error generating summary: {result.stderr}")
            return "Summary generation failed"
    except subprocess.TimeoutExpired:
        print("Summary generation timed out")
        return "Summary generation timed out"
    except Exception as e:
        print(f"Exception generating summary: {e}")
        return f"Summary generation error: {str(e)}"


def mark_job_complete(
    api_url: str,
    bearer_token: str,
    job_id: str,
    summary: str,
    repo_name: str,
    org_name: str,
    branch: str
) -> bool:
    """
    Mark a job as completed via API.
    - PUT request to api_url/end
    - Include resultData with orgName, repoName, ref, and artifacts
    - Return success status
    """
    try:
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "jobId": job_id,
            "resultData": {
                "orgName": org_name,
                "repoName": repo_name,
                "ref": branch,
                "artifacts": [
                    {
                        "name": "Summary.md",
                        "format": "markdown",
                        "content": summary
                    }
                ]
            }
        }

        response = requests.put(
            f"{api_url}/end",
            headers=headers,
            json=payload
        )

        response.raise_for_status()
        print(f"Job {job_id} marked as complete")
        return True
    except Exception as e:
        print(f"Error marking job complete: {e}")
        return False


# ============================================================================
# Utility Functions
# ============================================================================

def create_log_file() -> str:
    """
    Create a timestamped log file path.
    - Generate log ID from current timestamp
    - Create path: artifacts/claude_logs_{timestamp}.json
    - Return log file path
    """
    log_id = time.strftime("%Y%m%d_%H%M%S")
    log_file = f"artifacts/claude_logs_{log_id}.json"
    return log_file


def parse_repo_info(repo_url: str) -> tuple[str, str]:
    """
    Extract organization and repo name from GitHub URL.
    - Parse https://github.com/{org}/{repo} format
    - Return (org_name, repo_name)
    """
    try:
        # Remove protocol and trailing slashes/extensions
        url = repo_url.replace("https://github.com/", "").replace("http://github.com/", "")
        url = url.rstrip("/").rstrip(".git")

        # Split into parts
        parts = url.split("/")
        if len(parts) >= 2:
            org_name = parts[0]
            repo_name = parts[1]
            return org_name, repo_name
        else:
            return "", ""
    except Exception as e:
        print(f"Error parsing repo info: {e}")
        return "", ""


def check_dependencies() -> dict[str, bool]:
    """
    Check if required tools are installed.
    - Check: forge, echidna, medusa, halmos, node, claude
    - Return dict of {tool: is_installed}
    """
    tools = ["forge", "echidna", "medusa", "halmos", "node", "claude", "git"]
    status = {}

    for tool in tools:
        try:
            result = subprocess.run(
                ["which", tool],
                capture_output=True,
                text=True
            )
            status[tool] = result.returncode == 0
        except Exception:
            status[tool] = False

    return status


def install_missing_dependencies(deps: list[str]) -> bool:
    """
    Install missing dependencies.
    - Call appropriate installers for each missing dependency
    - Return overall success status
    """
    # This is a placeholder - actual implementation would need
    # to handle different installation methods per dependency
    print(f"Missing dependencies: {deps}")
    print("Please install them manually or run the install_deps.sh script")
    return False


# ============================================================================
# Main Server Loop
# ============================================================================

def start_job_listener(
    api_url: str,
    bearer_token: str,
    permissions_flag: bool = False,
    check_interval: int = 60
):
    """
    Main server loop that listens for and processes jobs.
    - Poll API for pending jobs
    - For each job:
      1. Fetch job details
      2. Setup workspace
      3. Clone repositories
      4. Execute workflow (calls main.py)
      5. Create GitHub repo
      6. Push results
      7. Generate summary
      8. Mark job complete
    - Sleep between checks
    """
    print("=" * 40)
    print("Starting Listener Loop")
    print("=" * 40)
    print(f"API URL: {api_url}")
    print(f"Using Permissions Flag: {permissions_flag}")
    print("=" * 40)

    while True:
        print(f"\nChecking for jobs at {time.strftime('%Y-%m-%d %H:%M:%S')}")

        # Fetch pending jobs
        jobs = fetch_pending_jobs(api_url, bearer_token)

        for job in jobs:
            job_id = job.get("id")
            if not job_id:
                continue

            print(f"\nProcessing job: {job_id}")

            # Fetch job details
            job_data = fetch_job_details(api_url, bearer_token, job_id)
            if not job_data:
                print(f"Failed to fetch details for job {job_id}")
                continue

            try:
                # Extract job information
                data = job_data.get("data", {})
                repo_url = data.get("repoAccessData", {}).get("url")
                claude_url = data.get("claudeAccessData", {}).get("url")
                prompt = data.get("job", {}).get("claudePromptCommand")
                repo_ref = data.get("job", {}).get("ref", "main")
                claude_ref = data.get("job", {}).get("claudeRef", "main")

                print(f"Repo URL: {repo_url}")
                print(f"Claude URL: {claude_url}")

                # Setup workspace
                if not setup_workspace():
                    print("Failed to setup workspace")
                    continue

                # Clone repositories
                if not clone_repository(repo_url, repo_ref):
                    print("Failed to clone repository")
                    continue

                if not clone_claude_config(claude_url, claude_ref):
                    print("Failed to clone Claude config")
                    continue

                # TODO: Execute workflow using main.py
                # This would involve importing and calling main.main() or running it as subprocess
                print("TODO: Execute workflow")

                # Create GitHub repo for results
                timestamp = int(time.time())
                repo_basename = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
                new_repo_name = f"{repo_basename}-processed-{timestamp}"

                # Get GitHub token from environment or config
                github_token = os.environ.get("GITHUB_TOKEN", "")
                github_handle = os.environ.get("GITHUB_HANDLE", "")

                success, new_repo_url, owner = create_github_repo(new_repo_name, github_token)
                if not success:
                    print("Failed to create GitHub repository")
                    continue

                # Invite collaborator if handle provided
                if github_handle:
                    invite_collaborator(owner, new_repo_name, github_token, github_handle)

                # Push results to new repo
                if not push_to_github("repo", github_token, new_repo_url):
                    print("Failed to push to GitHub")
                    continue

                # Get branch name
                try:
                    result = subprocess.run(
                        ["git", "-C", "repo", "rev-parse", "--abbrev-ref", "HEAD"],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    branch_name = result.stdout.strip()
                except Exception:
                    branch_name = "main"

                # Generate summary
                summary = generate_summary_with_claude()
                print(f"Summary: {summary}")

                # Parse org name from new repo URL
                org_name, _ = parse_repo_info(new_repo_url)

                # Mark job as complete
                mark_job_complete(
                    api_url,
                    bearer_token,
                    job_id,
                    summary,
                    new_repo_name,
                    org_name,
                    branch_name
                )

            except Exception as e:
                print(f"Error processing job {job_id}: {e}")
                continue

        print(f"\nWaiting {check_interval} seconds until next check...")
        time.sleep(check_interval)


if __name__ == "__main__":
    import sys

    # Parse command line arguments
    if len(sys.argv) < 3:
        print("Usage: python server.py <api_url> <bearer_token> [permissions_flag]")
        print("Example: python server.py https://api.example.com/jobs your_token true")
        sys.exit(1)

    api_url = sys.argv[1]
    bearer_token = sys.argv[2]
    permissions_flag = sys.argv[3].lower() == "true" if len(sys.argv) > 3 else False

    start_job_listener(api_url, bearer_token, permissions_flag)
