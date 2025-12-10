"""
Post-processing operations for summary generation and job completion.
"""

import os
import subprocess

import requests


def generate_summary_with_claude(since_commit: str | None = None) -> str:
    """
    Generate a summary of successful changes using Claude Code.

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

        # Check if we should skip permissions (production environment)
        runner_env = os.environ.get('RUNNER_ENV', '').lower()
        cmd = ["claude"]
        if runner_env == 'production':
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


def generate_failure_summary_with_claude(
    failed_step_name: str,
    failed_step_num: int,
    since_commit: str | None = None
) -> str:
    """
    Generate a summary when workflow fails, explaining what was accomplished
    before the failure and what went wrong.

    Args:
        failed_step_name: Name of the step that failed
        failed_step_num: Step number that failed
        since_commit: If provided, summarize changes since this commit
    """
    try:
        if since_commit:
            prompt = (
                f"The workflow failed at step {failed_step_num}: '{failed_step_name}'. "
                f"Summarize what was accomplished since commit {since_commit} before the failure "
                "in 2-3 sentences in markdown format. Then briefly mention that the workflow "
                f"stopped at step {failed_step_num} ('{failed_step_name}'). "
                "Return exclusively the summary, no other text. Talk as if you performed the tasks."
            )
        else:
            prompt = (
                f"The workflow failed at step {failed_step_num}: '{failed_step_name}'. "
                "Summarize what changes were made before the failure in 2-3 sentences in markdown format. "
                f"Then briefly mention that the workflow stopped at step {failed_step_num} ('{failed_step_name}'). "
                "Return exclusively the summary, no other text. Talk as if you performed the tasks."
            )

        # Check if we should skip permissions (production environment)
        runner_env = os.environ.get('RUNNER_ENV', '').lower()
        cmd = ["claude"]
        if runner_env == 'production':
            cmd.append("--dangerously-skip-permissions")
        cmd.extend(["-p", prompt])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd="/app/repo"
        )

        if result.returncode == 0:
            return result.stdout.strip()
        else:
            print(f"Error generating failure summary: {result.stderr}")
            return f"Workflow failed at step {failed_step_num}: {failed_step_name}"
    except subprocess.TimeoutExpired:
        print("Failure summary generation timed out")
        return f"Workflow failed at step {failed_step_num}: {failed_step_name}"
    except Exception as e:
        print(f"Exception generating failure summary: {e}")
        return f"Workflow failed at step {failed_step_num}: {failed_step_name}"


def mark_job_complete(
    api_url: str,
    bearer_token: str,
    job_id: str,
    summary: str,
    repo_name: str,
    org_name: str,
    branch: str,
    status: str = "DONE"
) -> bool:
    """
    Mark a job as completed or failed via API.

    Args:
        api_url: Base API URL
        bearer_token: Authentication token
        job_id: Job ID
        summary: Summary text
        repo_name: Repository name
        org_name: Organization name
        branch: Branch name
        status: Job status - "DONE" for success, "ERROR" for failure

    Returns:
        bool: True if successful
    """
    try:
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "jobId": job_id,
            "status": status,  # Pass status to backend
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
        status_msg = "complete" if status == "DONE" else "failed (ERROR)"
        print(f"Job {job_id} marked as {status_msg}")
        return True
    except Exception as e:
        print(f"Error marking job complete: {e}")
        return False
