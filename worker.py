"""
Worker module for recon-magic framework.
Main job listener loop that orchestrates the workflow.
"""

import os
import subprocess
import sys
import time

from server.github import create_github_repo, invite_collaborator, push_to_github
from server.jobs import fetch_job_details, fetch_pending_jobs
from server.postprocess import generate_summary_with_claude, mark_job_complete
from server.setup import clone_claude_config, clone_repository, setup_workspace
from server.utils import parse_repo_info


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
                prompt = data.get("job", {}).get("claudePromptCommand") ## TODO: Workflow identifier ot content of the workflow
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
                ## TODO: ADD THE WORKFLOW PART

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
    # Parse command line arguments
    if len(sys.argv) < 3:
        print("Usage: python worker.py <api_url> <bearer_token> [permissions_flag]")
        print("Example: python worker.py https://api.example.com/jobs your_token true")
        sys.exit(1)

    api_url = sys.argv[1]
    bearer_token = sys.argv[2]
    permissions_flag = sys.argv[3].lower() == "true" if len(sys.argv) > 3 else False

    start_job_listener(api_url, bearer_token, permissions_flag)
