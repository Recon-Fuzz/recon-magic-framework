"""
Post-processing operations for summary generation and job completion.
"""

import subprocess

import requests


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
