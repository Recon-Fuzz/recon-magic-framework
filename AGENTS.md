# AGENTS.md

## Goal
Maximize code quality and development speed while minimizing long-term maintenance burden.

## Defaults
- Prefer simple, explicit solutions over cleverness.
- Keep modules small with clear responsibilities.
- Optimize for readability: future edits should be obvious.
- Fail fast with actionable error messages.
- Favor composition over inheritance.
- Avoid global state; use dependency injection or passing collaborators.
- Keep side effects at the edges.

## Python Style
- Target Python 3.11+ unless otherwise stated.
- Use type hints everywhere, including return types.
- Prefer `pathlib.Path` over `os.path`.
- Use `dataclasses` or `attrs` for simple data containers.
- Keep functions short; extract helpers when a function exceeds ~40 lines.
- Avoid deep nesting; use guard clauses.
- Avoid mutable default arguments.
- Prefer f-strings for formatting.
- Use `logging` over `print` for non-CLI output.

## Project Structure
- Keep public interfaces in `__init__.py` minimal and explicit.
- Avoid circular imports; refactor to shared modules if needed.
- Keep configuration in one place and validate at startup.
- Use `pyproject.toml` as the source of truth for tooling.

## Testing
- Write tests for core logic and edge cases.
- Prefer small, isolated unit tests; add integration tests for workflows.
- Avoid network calls in unit tests; use fakes or fixtures.
- Keep test data minimal and readable.
- Ensure tests are deterministic and fast.

## Error Handling
- Raise specific exceptions; avoid bare `Exception`.
- Add context with `raise ... from ...`.
- Validate inputs at boundaries.
- Do not swallow exceptions without logging.

## Performance
- Measure before optimizing.
- Keep algorithmic complexity in mind for loops over large inputs.
- Use streaming and generators for large data.

## Tooling
- Format with `ruff format`.
- Lint with `ruff`.
- Type-check with `mypy` or `pyright` if configured.
- Run tests with `pytest`.

## Documentation
- Keep docstrings for public modules/classes/functions.
- Update README or docs when behavior changes.
- Add comments only when logic is not obvious.

## Deployment Notes (Magic Worker)
### Deployment Flow
- CI builds and pushes the Docker image to ECR.
- Terraform provisions the VPC, ECS cluster, task definition, and supporting IAM.
- Backend dispatches jobs by starting ECS tasks (RunTask) using the task definition.

### Job Dispatch Flow
- Backend triggers a job by calling ECS RunTask with environment overrides:
  - WORKER_API_URL (required): base backend API URL (ex: https://api.example.com)
  - WORKER_BEARER_TOKEN (required): backend auth token for callbacks
  - WORKER_JOB_ID (required when no payload): backend job identifier
  - WORKER_JOB_PAYLOAD (optional): full job payload JSON (same shape as GET {api_url}/jobs/{job_id})
  - WORKER_PERMISSIONS (optional): true to enable dangerous permissions
- The task runs python runner.py, processes a single job, reports progress, and exits.

### Backend <-> Worker Contract
Inputs:
- The worker fetches job data from GET {WORKER_API_URL}/jobs/{WORKER_JOB_ID} unless WORKER_JOB_PAYLOAD is provided.
- Job data must include data.job, data.repoAccessData, and data.claudeAccessData as used by worker.py.

Callbacks:
- Step updates: PUT {WORKER_API_URL}/data with resultData.steps.
- Job data updates: PUT {WORKER_API_URL}/data with resultData fields like repo metadata.
- Completion: PUT {WORKER_API_URL}/end with status and summary artifacts.

### Authentication Mechanism
- Default: API-based auth via WORKER_BEARER_TOKEN.
- Tradeoff: API token isolation keeps workers decoupled from the database, but relies on API availability/retry behavior.
- Direct DB credentials would be more resilient to API outages but tightly couples the worker to backend internals.

## Code Review Checklist
- Does this change improve clarity and maintainability?
- Are edge cases covered?
- Are errors reported with useful context?
- Is the API simple and stable?
- Are tests added or updated where needed?
