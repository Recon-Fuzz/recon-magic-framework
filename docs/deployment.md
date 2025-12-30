## Magic Worker Deployment

This document describes the Terraform-based AWS deployment and the backend-to-worker contract for running magic jobs in parallel.

### Deployment Flow

1. CI builds and pushes the Docker image to ECR.
2. Terraform provisions the VPC, ECS cluster, task definition, and supporting IAM.
3. Backend dispatches jobs by starting ECS tasks (RunTask) using the task definition.

### Job Dispatch Flow

Backend triggers a job by calling ECS `RunTask` with environment overrides:

- `WORKER_API_URL` (required): base backend API URL (ex: `https://api.example.com/jobs`)
- `WORKER_BEARER_TOKEN` (required): backend auth token for callbacks
- `WORKER_JOB_ID` (required when no payload): backend job identifier
- `WORKER_JOB_PAYLOAD` (optional): full job payload JSON (same shape as `GET {api_url}/{job_id}`)
- `WORKER_PERMISSIONS` (optional): `true` to enable dangerous permissions

The task runs `python runner.py`, processes a single job, reports progress, and exits.

### Backend ↔ Worker Contract

Inputs:
- The worker fetches job data from `GET {WORKER_API_URL}/{WORKER_JOB_ID}` unless `WORKER_JOB_PAYLOAD` is provided.
- Job data must include `data.job`, `data.repoAccessData`, and `data.claudeAccessData` as used by `worker.py`.

Callbacks:
- Step updates: `PUT {WORKER_API_URL}/data` with `resultData.steps`.
- Job data updates: `PUT {WORKER_API_URL}/data` with `resultData` fields like repo metadata.
- Completion: `PUT {WORKER_API_URL}/end` with status and summary artifacts.

### Authentication Mechanism

Default: API-based auth via `WORKER_BEARER_TOKEN`.

Tradeoff:
- API token isolation keeps workers decoupled from the database, but relies on API availability/retry behavior.
- Direct DB credentials would be more resilient to API outages but tightly couples the worker to backend internals.

The current implementation defaults to API-based integration and keeps DB access out of the worker container.
