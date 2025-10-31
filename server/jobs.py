"""
Job fetching operations for API communication.
"""

import requests


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
