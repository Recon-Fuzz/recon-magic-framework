"""
Worker module for recon-magic framework.
Main job listener loop that orchestrates the workflow.
"""

import json
import os
import shlex
import subprocess
import sys
import time

import requests


def _ask_ai_for_foundry_root(repo_path: str) -> str | None:
    """Ask AI to find the main foundry.toml. Returns absolute path or None."""
    try:
        runner_env = os.environ.get('RUNNER_ENV', '').lower()
        cmd = ["claude"]
        if runner_env == 'production':
            cmd.append("--dangerously-skip-permissions")
        cmd.extend([
            "-p", "Find the MAIN foundry.toml (not in lib/ or dependencies). "
                  "Print ONLY the relative path to its directory (e.g., 'contracts' or '.'). No explanation.",
            "--max-turns", "1", "--output-format", "text"
        ])

        result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True, timeout=60)
        if result.returncode == 0 and result.stdout.strip():
            ai_path = result.stdout.strip().strip('"').strip("'")
            if ai_path and not ai_path.startswith('/'):
                candidate = os.path.join(repo_path, ai_path)
                if os.path.isfile(os.path.join(candidate, "foundry.toml")):
                    print(f"  ✓ AI detected foundryRoot: {ai_path}")
                    return candidate
    except Exception as e:
        print(f"  ⚠ AI detection failed: {e}")
    return None


def find_foundry_root(repo_path: str, explicit_root: str | None = None) -> str:
    """
    Find the Foundry root directory.
    Priority: 1) Explicit config  2) Auto-detect (if exactly 1)  3) AI  4) Repo root
    """
    # 1. Explicit override
    if explicit_root and explicit_root != ".":
        candidate = os.path.join(repo_path, explicit_root)
        if os.path.isfile(os.path.join(candidate, "foundry.toml")):
            print(f"  ✓ Using explicit foundryRoot: {explicit_root}")
            return candidate
        print(f"  ⚠ Explicit foundryRoot '{explicit_root}' invalid, auto-detecting...")

    # 2. Auto-detect (only if exactly one foundry.toml found)
    foundry_paths = []
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in ['node_modules', '.git', 'lib', 'out', 'cache', 'broadcast']]
        if 'foundry.toml' in files:
            foundry_paths.append(root)

    if len(foundry_paths) == 1:
        rel_path = os.path.relpath(foundry_paths[0], repo_path)
        print(f"  ✓ Auto-detected foundryRoot: {rel_path}")
        return foundry_paths[0]

    # 3. AI detection (0 or multiple foundry.toml)
    print(f"  🤖 Using AI to detect foundryRoot...")
    ai_choice = _ask_ai_for_foundry_root(repo_path)
    if ai_choice:
        return ai_choice

    # 4. Default to repo root
    print(f"  ⚠ Defaulting to repo root")
    return repo_path

from server.github import create_github_repo, invite_collaborator, install_github_app_on_repo, push_to_github, setup_repo_remote
from server.jobs import check_stop_requested, fetch_job_details, fetch_pending_jobs
from server.postprocess import generate_failure_summary_with_claude, generate_summary_with_claude, mark_job_complete
from server.setup import clone_claude_config, clone_opencode_config, clone_repository, setup_workspace
from server.utils import parse_repo_info


# Global tracker for workflow failure info
# This gets populated by worker_after_step_hook when a step fails
_workflow_failure_info: dict | None = None


def reset_workflow_failure_info():
    """Reset the failure tracker before each job."""
    global _workflow_failure_info
    _workflow_failure_info = None


def set_workflow_failure_info(step_name: str, step_num: int, reason: str = "step_failure", failure_tail: str | None = None):
    """Set failure info when workflow fails."""
    global _workflow_failure_info
    _workflow_failure_info = {
        "step_name": step_name,
        "step_num": step_num,
        "reason": reason,  # "step_failure", "stop_action", "exception"
        "failure_tail": failure_tail  # Last 10 lines of output for PROGRAM steps
    }


def get_workflow_failure_info() -> dict | None:
    """Get the current failure info."""
    return _workflow_failure_info


def create_stop_checker() -> callable:
    """
    Create a stop checker function that checks with the backend API.
    Uses environment variables for API credentials.

    Returns:
        Callable that returns True if stop was requested, False otherwise
    """
    def check_stop() -> bool:
        api_url = os.environ.get('WORKER_API_URL')
        bearer_token = os.environ.get('WORKER_BEARER_TOKEN')
        job_id = os.environ.get('WORKER_JOB_ID')

        if not all([api_url, bearer_token, job_id]):
            return False

        return check_stop_requested(api_url, bearer_token, job_id)

    return check_stop


def update_job_data(api_url: str, bearer_token: str, job_id: str, data: dict) -> bool:
    """
    Send generic data to the backend API (not step data).

    Args:
        api_url: Base API URL
        bearer_token: Authentication token
        job_id: Job ID
        data: Data to merge into resultData

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
            "resultData": data
        }

        response = requests.put(
            f"{api_url}/data",
            headers=headers,
            json=payload
        )

        response.raise_for_status()
        print(f"  ✓ Job data sent to backend")
        return True
    except Exception as e:
        print(f"  ⚠ Failed to send job data to backend: {e}")
        return False


def update_job_step_data(api_url: str, bearer_token: str, job_id: str, step_data: dict) -> bool:
    """
    Send step data to the backend API (appends to steps array).

    Args:
        api_url: Base API URL
        bearer_token: Authentication token
        job_id: Job ID
        step_data: Step result data to send

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
            "resultData": {
                "steps": [step_data]  # Backend merges into existing steps array
            }
        }

        response = requests.put(
            f"{api_url}/data",
            headers=headers,
            json=payload
        )

        response.raise_for_status()
        print(f"  ✓ Step data sent to backend")
        return True
    except Exception as e:
        print(f"  ⚠ Failed to send step data to backend: {e}")
        return False


def update_current_phase(api_url: str, bearer_token: str, job_id: str, step_num: int, step_name: str, step=None, step_id: str | None = None) -> bool:
    """
    Update the current phase in the backend.

    Args:
        api_url: Base API URL
        bearer_token: Authentication token
        job_id: Job ID
        step_num: Current step number
        step_name: Current step name
        step: Optional step object for additional metadata
        step_id: Optional internal step ID (e.g., "audit:3")

    Returns:
        bool: True if successful
    """
    try:
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json"
        }

        # Derive model category from step
        model_category = "infra"
        can_skip = False
        if step:
            model_type = step.model.type if hasattr(step, 'model') and step.model else None
            if model_type == "PROGRAM":
                model_category = "tool"
            elif model_type in ("OPENCODE", "CLAUDE_CODE"):
                model_category = "ai"
            elif model_type == "DISPATCH_FUZZING_JOB":
                model_category = "infra"
            elif model_type == "INHERIT":
                model_category = "infra"  # INHERIT resolves at runtime
            can_skip = getattr(step, 'canSkip', False)

        current_phase = {
            "step_num": step_num,
            "step_name": step_name,
            "model_category": model_category,
            "can_skip": can_skip,
            "internal_id": step_id
        }

        payload = {
            "jobId": job_id,
            "resultData": {
                "currentPhase": current_phase,
                "liveProgress": None  # Clear old progress when phase changes
            }
        }

        response = requests.put(
            f"{api_url}/data",
            headers=headers,
            json=payload
        )

        response.raise_for_status()
        print(f"  ✓ Current phase updated: Step {step_num} - {step_name} (category={model_category}, canSkip={can_skip})")
        return True
    except Exception as e:
        print(f"  ⚠ Failed to update current phase: {e}")
        return False

def check_skip_requested(api_url: str, bearer_token: str, job_id: str, current_step_id: str) -> bool:
    """
    Check if a skip was requested for the current step.

    Args:
        api_url: Base API URL
        bearer_token: Authentication token
        job_id: Job ID
        current_step_id: The internal ID of the current step (e.g., "audit:3")

    Returns:
        bool: True if skip was requested for this step
    """
    try:
        headers = {"Authorization": f"Bearer {bearer_token}"}
        response = requests.get(f"{api_url}/{job_id}", headers=headers)
        response.raise_for_status()

        data = response.json().get("data", {})
        job_info = data.get("job", {})
        additional_data = job_info.get("additionalData", {})

        skip_step_id = additional_data.get("skipStepId")
        if skip_step_id:
            print(f"  🔍 Skip check: skipStepId='{skip_step_id}' vs current='{current_step_id}' -> match={skip_step_id == current_step_id}")
        return skip_step_id == current_step_id
    except Exception as e:
        print(f"  ⚠ Skip check error: {e}")
        return False


def clear_skip_request() -> bool:
    """
    Clear the skipStepId from additionalData after processing the skip.
    This prevents the skip from being triggered again.

    Returns:
        bool: True if successful
    """
    api_url = os.environ.get('WORKER_API_URL')
    bearer_token = os.environ.get('WORKER_BEARER_TOKEN')
    job_id = os.environ.get('WORKER_JOB_ID')

    if not all([api_url, bearer_token, job_id]):
        return False

    try:
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json"
        }

        # Clear skipStepId by setting it to None
        payload = {
            "jobId": job_id,
            "skipStepId": None
        }

        response = requests.put(
            f"{api_url}/data",
            headers=headers,
            json=payload
        )

        response.raise_for_status()
        print(f"  ✓ Cleared skipStepId from job")
        return True
    except Exception as e:
        print(f"  ⚠ Failed to clear skipStepId: {e}")
        return False


def send_live_progress(progress: str) -> None:
    """
    Send live progress data to the backend (overwrites previous, not appended to steps).

    Args:
        progress_data: Live progress data (e.g., {"log_extract": "coverage: 85%", "timestamp": ...})
    """
    if all([
        os.environ.get('WORKER_API_URL'),
        os.environ.get('WORKER_BEARER_TOKEN'),
        os.environ.get('WORKER_JOB_ID')
    ]):
        try:
            update_job_data(
                api_url=os.environ.get('WORKER_API_URL', ''),
                bearer_token=os.environ.get('WORKER_BEARER_TOKEN', ''),
                job_id=os.environ.get('WORKER_JOB_ID', ''),
                data={"liveProgress": {
                    "logExtract": progress,
                    "timestamp": int(time.time())
                }}
            )
        except Exception:
            pass  # Silent fail for progress reporting

def worker_before_step_hook(step, step_num: int, step_id: str | None = None) -> None:
    """
    Worker-specific hook that runs before step execution.
    Updates the backend with the current phase.

    Args:
        step: The workflow step being executed
        step_num: The step number (1-indexed)
        step_id: The internal step ID (e.g., "audit:3") for skip checking
    """
    print(f"[Worker] Before step {step_num}: {step.name}")
    print(f"Type: {step.type}")
    if hasattr(step, 'model') and step.model:
        print(f"Model: {step.model.type}")
    print(f"Description: {step.description or 'N/A'}")
    if hasattr(step, 'canSkip') and step.canSkip:
        print(f"Can Skip: {step.canSkip}")
    if step_id:
        print(f"Step ID: {step_id}")

    # Update current phase in backend
    api_url = os.environ.get('WORKER_API_URL')
    bearer_token = os.environ.get('WORKER_BEARER_TOKEN')
    job_id = os.environ.get('WORKER_JOB_ID')

    if all([api_url, bearer_token, job_id]):
        update_current_phase(api_url, bearer_token, job_id, step_num, step.name, step, step_id)


def worker_after_step_hook(step, step_num: int, return_code: int, action: str, step_result: dict | None = None) -> None:
    """
    Worker-specific hook that runs after step execution.
    Sends step results to the backend API.
    Tracks failure info for error handling.

    Args:
        step: The workflow step that was executed
        step_num: The step number (1-indexed)
        return_code: The exit code from step execution (0 = success)
        action: The action taken (CONTINUE, STOP, JUMP_TO_STEP, FAILED, etc.)
        step_result: Dictionary containing summary, commit_info, pushed status
    """
    print(f"[Worker] After step {step_num}: {step.name}")
    print(f"Return code: {return_code}, Action: {action}")

    # Track failure/stop info for later use in error handling
    # Extract failure_tail from step_result if available
    failure_tail = step_result.get("failure_tail") if step_result else None
    if action == "FAILED" or return_code == 1:
        set_workflow_failure_info(step.name, step_num, "step_failure", failure_tail)
    elif action == "STOP":
        set_workflow_failure_info(step.name, step_num, "stop_action")
    elif action == "GRACEFUL_STOP" or return_code == 2:
        set_workflow_failure_info(step.name, step_num, "graceful_stop")

    # Get API credentials from environment
    api_url = os.environ.get('WORKER_API_URL')
    bearer_token = os.environ.get('WORKER_BEARER_TOKEN')
    job_id = os.environ.get('WORKER_JOB_ID')

    if not all([api_url, bearer_token, job_id]):
        print("  ⚠ Missing API credentials, skipping backend update")
        return

    # Derive model category
    model_type = step.model.type if hasattr(step, 'model') and step.model else None
    if model_type == "PROGRAM":
        model_category = "tool"
    elif model_type in ("OPENCODE", "CLAUDE_CODE"):
        model_category = "ai"
    else:
        model_category = "infra"

    # Build step data for backend
    step_data = {
        "step_num": step_num,
        "step_name": step.name,
        "return_code": return_code,
        "action": action,
        "model_category": model_category,
    }

    # Add step_result data if available
    if step_result:
        if step_result.get("internal_id"):
            step_data["internal_id"] = step_result["internal_id"]
        if step_result.get("summary"):
            step_data["summary"] = step_result["summary"]
        if step_result.get("commit_info"):
            step_data["commit_hash"] = step_result["commit_info"].get("commit_hash")
            step_data["files_changed"] = step_result["commit_info"].get("files_changed", [])
        if step_result.get("pushed"):
            step_data["pushed"] = step_result["pushed"]
        if step_result.get("failed"):
            step_data["failed"] = step_result["failed"]
        if step_result.get("stopped"):
            step_data["stopped"] = step_result["stopped"]
        if step_result.get("skipped"):
            step_data["skipped"] = step_result["skipped"]
        if step_result.get("failure_tail"):
            step_data["failure_tail"] = step_result["failure_tail"]

    # Send to backend
    update_job_step_data(api_url, bearer_token, job_id, step_data)


def create_dynamic_workflow(prompt: str, model_type: str = "CLAUDE_CODE", job_id: str = "dynamic") -> str:
    """
    Create a single-step workflow from a direct prompt.

    Args:
        prompt: The prompt to execute
        model_type: The model type to use (CLAUDE_CODE, OPENCODE, PROGRAM)
        job_id: Job ID for unique temp file naming

    Returns:
        Path to the generated workflow JSON file
    """
    workflow = {
        "name": f"Dynamic Job {job_id}",
        "steps": [{
            "type": "task",
            "name": "Execute Direct Prompt",
            "description": f"Direct prompt execution with {model_type}",
            "prompt": prompt,
            "model": {
                "type": model_type,
                "model": "inherit"
            },
            "shouldCreateSummary": False,
            "shouldCommitChanges": True
        }]
    }

    workflow_file = f"/tmp/dynamic_workflow_{job_id}.json"
    with open(workflow_file, 'w') as f:
        json.dump(workflow, f, indent=2)

    return workflow_file


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
                job_info = data.get("job", {})

                repo_url = data.get("repoAccessData", {}).get("url")
                claude_url = data.get("claudeAccessData", {}).get("url")
                repo_ref = job_info.get("ref", "main")
                claude_ref = job_info.get("claudeRef", "main")

                # Get job type (directPrompt, workflowName, relativeWorkflow)
                additional_data = job_info.get("additionalData", {})
                job_type = additional_data.get("jobType", "directPrompt")
                resume_from_step_id = additional_data.get("resumeFromStepId")

                print(f"Job Type: {job_type}")
                print(f"Repo URL: {repo_url}")
                print(f"Claude URL: {claude_url}")
                if resume_from_step_id:
                    print(f"Resume from step ID: {resume_from_step_id}")

                # Setup workspace in /app
                if not setup_workspace("/app"):
                    print("Failed to setup workspace")
                    mark_job_complete(
                        api_url,
                        bearer_token,
                        job_id,
                        "Failed to setup workspace. Please try again.",
                        "unknown",
                        "unknown",
                        "main",
                        status="ERROR"
                    )
                    continue

                # Clone target repository to /app/repo
                if not clone_repository(repo_url, repo_ref, "/app/repo"):
                    print("Failed to clone repository")
                    mark_job_complete(
                        api_url,
                        bearer_token,
                        job_id,
                        f"Failed to clone repository: {repo_url}. Check that the repository exists, is accessible, and all submodules are public or have proper authentication configured.",
                        "unknown",
                        "unknown",
                        repo_ref,
                        status="ERROR"
                    )
                    continue

                # Rename current branch to 'main' for consistent push behavior
                # This ensures we always push to 'main' regardless of source repo's default branch
                subprocess.run(
                    ["git", "branch", "-M", "main"],
                    cwd="/app/repo",
                    capture_output=True
                )

                # Capture initial commit hash before workflow runs
                initial_commit_result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd="/app/repo",
                    capture_output=True,
                    text=True
                )
                initial_commit_hash = initial_commit_result.stdout.strip() if initial_commit_result.returncode == 0 else None

                # Execute workflow using main.py
                from pathlib import Path
                from main import run_workflow

                # Set environment variable for framework root
                framework_root = Path(__file__).parent.resolve()
                os.environ['RECON_FRAMEWORK_ROOT'] = str(framework_root)

                # Set prompts directory (where agent reference documents live)
                os.environ['PROMPTS_DIR'] = '/app/.opencode'

                # Set worker context in environment for hooks to use
                os.environ['WORKER_API_URL'] = api_url
                os.environ['WORKER_BEARER_TOKEN'] = bearer_token
                os.environ['WORKER_JOB_ID'] = str(job_id)

                # Clone config repo (contains both .claude and .opencode agent definitions)
                # The ai-agent-primers repo has the structure:
                #   /agents/         -> cloned to /app/.claude/agents/
                #   /agent/          -> cloned to /app/.opencode/agent/
                # We clone it twice to different locations for compatibility

                # Determine workflow file based on job type
                if job_type == "directPrompt":
                    # Mode 1: Direct prompt execution
                    prompt = job_info.get("claudePromptCommand")
                    model_type = job_info.get("modelType", "CLAUDE_CODE")

                    print(f"Direct Prompt Mode - Model: {model_type}")
                    print(f"Prompt: {prompt[:100]}..." if len(prompt) > 100 else f"Prompt: {prompt}")

                    # Clone config repo for agent definitions (to both .claude and .opencode)
                    if claude_url:
                        if not clone_claude_config(claude_url, claude_ref, "/app/.claude"):
                            print("Warning: Failed to clone Claude config, continuing without it")
                        if not clone_opencode_config(claude_url, claude_ref, "/app/.opencode"):
                            print("Warning: Failed to clone OpenCode config, continuing without it")

                    workflow_file = create_dynamic_workflow(prompt, model_type, str(job_id))

                elif job_type == "workflowName":
                    # Mode 2: Use workflow from framework workflows/
                    workflow_name = job_info.get("workflowName")
                    workflow_file = str(framework_root / "workflows" / f"{workflow_name}.json")

                    print(f"Framework Workflow Mode: {workflow_name}")

                    # Clone config repo for agent definitions (to both .claude and .opencode)
                    if claude_url:
                        if not clone_claude_config(claude_url, claude_ref, "/app/.claude"):
                            print("Warning: Failed to clone Claude config, continuing without it")
                        if not clone_opencode_config(claude_url, claude_ref, "/app/.opencode"):
                            print("Warning: Failed to clone OpenCode config, continuing without it")

                    if not os.path.exists(workflow_file):
                        print(f"Error: Workflow not found: {workflow_file}")
                        mark_job_complete(
                            api_url,
                            bearer_token,
                            job_id,
                            f"Workflow not found: {workflow_name}. Please check the workflow name is valid.",
                            "unknown",
                            "unknown",
                            repo_ref,
                            status="ERROR"
                        )
                        continue

                elif job_type == "relativeWorkflow":
                    # Mode 3: Use workflow from .claude repo (legacy)
                    workflow_name = job_info.get("workflowName")

                    # Clone claude config for this mode
                    if not clone_claude_config(claude_url, claude_ref, "/app/.claude"):
                        print("Failed to clone Claude config")
                        mark_job_complete(
                            api_url,
                            bearer_token,
                            job_id,
                            f"Failed to clone Claude config repository. Check that the repository is accessible.",
                            "unknown",
                            "unknown",
                            repo_ref,
                            status="ERROR"
                        )
                        continue

                    workflow_file = f"/app/.claude/workflows/{workflow_name}.json"
                    print(f"Relative Workflow Mode: {workflow_name}")

                    if not os.path.exists(workflow_file):
                        print(f"Error: Workflow not found: {workflow_file}")
                        mark_job_complete(
                            api_url,
                            bearer_token,
                            job_id,
                            f"Workflow not found: {workflow_name}. Please check the workflow name is valid.",
                            "unknown",
                            "unknown",
                            repo_ref,
                            status="ERROR"
                        )
                        continue
                else:
                    print(f"Error: Unknown job type: {job_type}")
                    mark_job_complete(
                        api_url,
                        bearer_token,
                        job_id,
                        f"Unknown job type: {job_type}. Please contact support.",
                        "unknown",
                        "unknown",
                        repo_ref,
                        status="ERROR"
                    )
                    continue

                print(f"Executing workflow: {workflow_file}")

                # Create GitHub repo BEFORE workflow runs so we can push per-step
                # Use first section of job UUID for traceability + timestamp for uniqueness
                job_id_prefix = str(job_id).split("-")[0]  # e.g., "a2178a85"
                timestamp = int(time.time())
                repo_basename = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
                new_repo_name = f"{job_id_prefix}-{repo_basename}-{timestamp}"

                github_token = os.environ.get("GITHUB_TOKEN", "")

                success, new_repo_url, owner, repo_id = create_github_repo(new_repo_name, github_token)
                if not success:
                    print("Failed to create GitHub repository")
                    mark_job_complete(
                        api_url,
                        bearer_token,
                        job_id,
                        "Failed to create GitHub repository. Please check GitHub credentials and try again.",
                        "unknown",
                        "unknown",
                        repo_ref,
                        status="ERROR"
                    )
                    continue

                # Install GitHub App on the new repository if configured
                github_app_installation_id = os.environ.get("GITHUB_APP_INSTALLATION_ID", "")
                if github_app_installation_id and repo_id:
                    if install_github_app_on_repo(github_app_installation_id, repo_id, github_token):
                        print(f"  ✓ GitHub App installed on repository")
                    else:
                        print(f"  ⚠ Failed to install GitHub App on repository")

                # Get user handles from job data and invite them early
                additional_data = job_info.get("additionalData", {})
                user_handles = additional_data.get("userHandles", [])
                for handle in user_handles:
                    try:
                        invite_collaborator(owner, new_repo_name, github_token, handle)
                        print(f"  ✓ Invited {handle} to repository")
                    except Exception as e:
                        print(f"  ⚠ Failed to invite {handle}: {e}")

                # Setup git remote in repo directory for per-step pushes
                setup_repo_remote("/app/repo", github_token, new_repo_url)

                # Push initial code to the repository
                try:
                    subprocess.run(
                        ["git", "-C", "/app/repo", "add", "."],
                        check=True, capture_output=True
                    )
                    subprocess.run(
                        ["git", "-C", "/app/repo", "commit", "-m", "Initial commit"],
                        capture_output=True  # May fail if no changes, that's ok
                    )
                    subprocess.run(
                        ["git", "-C", "/app/repo", "push", "-u", "recon", "main"],
                        check=True, capture_output=True
                    )
                    print("  ✓ Pushed initial code to repository")
                except subprocess.CalledProcessError as e:
                    print(f"  ⚠ Failed to push initial code: {e}")

                # Send repo URL to backend immediately (not as a step)
                org_name, _ = parse_repo_info(new_repo_url)
                update_job_data(api_url, bearer_token, job_id, {
                    "repoUrl": new_repo_url,
                    "orgName": org_name,
                    "repoName": new_repo_name
                })

                # All job types now run from /app/repo since configs are also in /app
                effective_repo_path = "/app/repo"

                # Detect Foundry root (for monorepo support)
                explicit_foundry_root = additional_data.get("foundryRoot")
                foundry_root = find_foundry_root(effective_repo_path, explicit_foundry_root)
                os.environ['RECON_FOUNDRY_ROOT'] = foundry_root
                print(f"  ✓ Foundry root set to: {foundry_root}")

                # Reset failure tracker before running workflow
                reset_workflow_failure_info()

                # Run the workflow with worker-specific hooks and stop checker
                workflow_result = run_workflow(
                    workflow_file=workflow_file,
                    dangerous=permissions_flag,
                    loop_hardcap=5,  # TODO: Make configurable via API
                    logs_dir="/app/logs",
                    repo_path=effective_repo_path,
                    before_hook=worker_before_step_hook,
                    after_hook=worker_after_step_hook,
                    stop_checker=create_stop_checker(),
                    resume_from_step_id=resume_from_step_id
                )

                # Check workflow result: 0 = success, 1 = failure, 2 = stopped
                workflow_failed = workflow_result == 1
                workflow_stopped = workflow_result == 2
                failure_info = get_workflow_failure_info()

                if workflow_failed:
                    print(f"Workflow execution failed with code {workflow_result}")
                    if failure_info:
                        print(f"  Failed at step {failure_info['step_num']}: {failure_info['step_name']} ({failure_info['reason']})")
                elif workflow_stopped:
                    print(f"Workflow was gracefully stopped")
                    if failure_info:
                        print(f"  Stopped before step {failure_info['step_num']}: {failure_info['step_name']}")

                # On failure or stop, commit and push any uncommitted changes
                # This preserves progress for potential resume
                if workflow_failed or workflow_stopped:
                    try:
                        # Check if there are any changes to commit
                        status_result = subprocess.run(
                            ["git", "-C", "/app/repo", "status", "--porcelain"],
                            capture_output=True,
                            text=True
                        )
                        if status_result.stdout.strip():
                            print("  Committing uncommitted changes before marking job...")
                            subprocess.run(
                                ["git", "-C", "/app/repo", "add", "."],
                                check=True,
                                capture_output=True
                            )
                            commit_msg = "WIP: Uncommitted changes before failure" if workflow_failed else "WIP: Uncommitted changes before stop"
                            subprocess.run(
                                ["git", "-C", "/app/repo", "commit", "-m", commit_msg],
                                capture_output=True
                            )
                            subprocess.run(
                                ["git", "-C", "/app/repo", "push", "recon", "main"],
                                check=True,
                                capture_output=True
                            )
                            print("  ✓ Pushed uncommitted changes")
                    except subprocess.CalledProcessError as e:
                        print(f"  ⚠ Failed to commit/push uncommitted changes: {e}")

                # Get branch name
                try:
                    result = subprocess.run(
                        ["git", "-C", "/app/repo", "rev-parse", "--abbrev-ref", "HEAD"],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    branch_name = result.stdout.strip()
                except Exception:
                    branch_name = "main"

                # Generate appropriate summary based on success/failure/stopped
                if workflow_failed:
                    # Check for pre-generated failure report first
                    failure_report_paths = [
                        "/app/repo/magic/WORKFLOW_FAILURE_REPORT.md",
                        f"/app/repo/{foundry_root}/magic/WORKFLOW_FAILURE_REPORT.md" if foundry_root != "/app/repo" else None
                    ]
                    failure_report_content = None
                    for report_path in failure_report_paths:
                        if report_path and os.path.exists(report_path):
                            try:
                                with open(report_path, 'r') as f:
                                    failure_report_content = f.read().strip()
                                print(f"  ✓ Using failure report from {report_path}")
                                break
                            except Exception as e:
                                print(f"  ⚠ Failed to read {report_path}: {e}")
                    
                    if failure_report_content:
                        summary = failure_report_content
                    elif failure_info:
                        # Generate failure-aware summary with step info and failure tail
                        summary = generate_failure_summary_with_claude(
                            failed_step_name=failure_info['step_name'],
                            failed_step_num=failure_info['step_num'],
                            since_commit=initial_commit_hash,
                            failure_tail=failure_info.get('failure_tail')
                        )
                    else:
                        # Workflow failed before any step ran (e.g., invalid resume step ID)
                        summary = "Workflow failed to start. Check that the resume step ID is valid."
                    job_status = "ERROR"
                elif workflow_stopped:
                    # Generate summary for gracefully stopped job
                    summary = generate_summary_with_claude(initial_commit_hash)
                    if failure_info:
                        summary = f"Job was gracefully stopped before step {failure_info['step_num']}: {failure_info['step_name']}. " + (summary or "")
                    else:
                        summary = "Job was gracefully stopped by user request. " + (summary or "")
                    job_status = "STOPPED"
                else:
                    # Generate success summary
                    summary = generate_summary_with_claude(initial_commit_hash)
                    job_status = "DONE"

                print(f"Summary: {summary}")

                # Parse org name from new repo URL
                org_name, _ = parse_repo_info(new_repo_url)

                # Mark job with appropriate status
                mark_job_complete(
                    api_url,
                    bearer_token,
                    job_id,
                    summary,
                    new_repo_name,
                    org_name,
                    branch_name,
                    status=job_status
                )

            except Exception as e:
                print(f"Error processing job {job_id}: {e}")
                import traceback
                traceback.print_exc()

                # Try to mark job as ERROR if we have the necessary info
                try:
                    error_summary = f"Job failed due to unexpected error: {str(e)}"
                    # Use variables if they were set, otherwise use defaults
                    local_vars = locals()
                    final_repo_name = local_vars.get('new_repo_name', "unknown")
                    final_org_name = local_vars.get('org_name', "unknown")
                    final_branch = local_vars.get('branch_name', "main")

                    mark_job_complete(
                        api_url,
                        bearer_token,
                        job_id,
                        error_summary,
                        final_repo_name,
                        final_org_name,
                        final_branch,
                        status="ERROR"
                    )
                except Exception as mark_error:
                    print(f"Failed to mark job as error: {mark_error}")

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
