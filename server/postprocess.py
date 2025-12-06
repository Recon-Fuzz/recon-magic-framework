"""
Post-processing operations for summary generation and job completion.
"""

import os
import subprocess

import requests


def generate_summary_with_claude(since_commit: str | None = None) -> str:
    """
    Generate a summary of changes using Claude Code.

    Args:
        since_commit: If provided, summarize all changes since this commit hash.
                      If None, summarize only the last commit.
    """
    try:
        if since_commit:
            prompt = (
                f"Summarize all changes made since commit {since_commit} "
                "in 2-3 sentences in markdown format, return exclusively the summary, "
                "no other text. Ignore the deletions of the Github Workflows. "
                "Talk as if you performed the tasks."
            )
        else:
            prompt = (
                "Summarize the changes done in the last commit "
                "in 2-3 sentences in markdown format, return exclusively the summary, "
                "no other text. Ignore the deletions of the Github Workflows. "
                "Do not mention the last commit but instead talk as if you performed the task."
            )

        # Build command with permissions flag if in production
        cmd = ["claude"]
        if os.environ.get('RUNNER_ENV', '').lower() == 'production':
            cmd.append("--dangerously-skip-permissions")
        cmd.extend(["-p", prompt])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            cwd="/app/repo"
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
