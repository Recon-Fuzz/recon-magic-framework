"""
Single-job runner entrypoint for AWS ECS run-task dispatch.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from server.jobs import fetch_job_details
from worker import process_job


def parse_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y"}


def load_job_payload(payload_text: str) -> tuple[str | None, dict | None]:
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid WORKER_JOB_PAYLOAD JSON: {exc}") from exc

    if isinstance(payload, dict) and "jobData" in payload:
        job_data = payload["jobData"]
        job_id = payload.get("jobId")
        return job_id, job_data

    if isinstance(payload, dict):
        job_id = payload.get("jobId") or payload.get("id")
        return job_id, payload

    raise ValueError("WORKER_JOB_PAYLOAD must be a JSON object")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a single magic job")
    parser.add_argument("--api-url", default=os.environ.get("WORKER_API_URL"))
    parser.add_argument("--bearer-token", default=os.environ.get("WORKER_BEARER_TOKEN"))
    parser.add_argument("--job-id", default=os.environ.get("WORKER_JOB_ID"))
    parser.add_argument("--payload", default=os.environ.get("WORKER_JOB_PAYLOAD"))
    parser.add_argument(
        "--permissions",
        default=os.environ.get("WORKER_PERMISSIONS"),
        help="Enable dangerous permissions (true/false)."
    )
    args = parser.parse_args()

    permissions_flag = parse_bool(args.permissions)
    job_data = None
    job_id = args.job_id

    if args.payload:
        payload_job_id, job_data = load_job_payload(args.payload)
        if not job_id and payload_job_id:
            job_id = payload_job_id

    if not all([args.api_url, args.bearer_token]):
        print("Error: api_url and bearer_token are required.")
        return 2

    if not job_data:
        if not job_id:
            print("Error: job_id is required when no payload is provided.")
            return 2
        job_data = fetch_job_details(args.api_url, args.bearer_token, job_id)

    if not job_data:
        print("Error: Could not resolve job data.")
        return 2

    if not job_id:
        print("Error: job_id is required.")
        return 2

    success = process_job(job_id, job_data, args.api_url, args.bearer_token, permissions_flag)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
