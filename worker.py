"""
Worker module for recon-magic framework.
Main job listener loop that orchestrates the workflow.
"""

import json
import os
import subprocess
import sys
import time

import requests

from server.github import create_github_repo, invite_collaborator, push_to_github, setup_repo_remote
from server.jobs import fetch_job_details, fetch_pending_jobs
from server.postprocess import generate_summary_with_claude, mark_job_complete
from server.setup import clone_claude_config, clone_opencode_config, clone_repository, setup_workspace
from server.utils import parse_repo_info


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


def update_current_phase(api_url: str, bearer_token: str, job_id: str, step_num: int, step_name: str) -> bool:
    """
    Update the current phase in the backend.

    Args:
        api_url: Base API URL
        bearer_token: Authentication token
        job_id: Job ID
        step_num: Current step number
        step_name: Current step name

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
                "currentPhase": {
                    "step_num": step_num,
                    "step_name": step_name
                }
            }
        }

        response = requests.put(
            f"{api_url}/data",
            headers=headers,
            json=payload
        )

        response.raise_for_status()
        print(f"  ✓ Current phase updated: Step {step_num} - {step_name}")
        return True
    except Exception as e:
        print(f"  ⚠ Failed to update current phase: {e}")
        return False


def worker_before_step_hook(step, step_num: int) -> None:
    """
    Worker-specific hook that runs before step execution.
    Updates the backend with the current phase.

    Args:
        step: The workflow step being executed
        step_num: The step number (1-indexed)
    """
    print(f"[Worker] Before step {step_num}: {step.name}")
    print(f"Type: {step.type}")
    if hasattr(step, 'model') and step.model:
        print(f"Model: {step.model.type}")
    print(f"Description: {step.description or 'N/A'}")

    # Update current phase in backend
    api_url = os.environ.get('WORKER_API_URL')
    bearer_token = os.environ.get('WORKER_BEARER_TOKEN')
    job_id = os.environ.get('WORKER_JOB_ID')

    if all([api_url, bearer_token, job_id]):
        update_current_phase(api_url, bearer_token, job_id, step_num, step.name)


def worker_after_step_hook(step, step_num: int, return_code: int, action: str, step_result: dict | None = None) -> None:
    """
    Worker-specific hook that runs after step execution.
    Sends step results to the backend API.

    Args:
        step: The workflow step that was executed
        step_num: The step number (1-indexed)
        return_code: The exit code from step execution (0 = success)
        action: The action taken (CONTINUE, STOP, JUMP_TO_STEP, etc.)
        step_result: Dictionary containing summary, commit_info, pushed status
    """
    print(f"[Worker] After step {step_num}: {step.name}")
    print(f"Return code: {return_code}, Action: {action}")

    # Get API credentials from environment
    api_url = os.environ.get('WORKER_API_URL')
    bearer_token = os.environ.get('WORKER_BEARER_TOKEN')
    job_id = os.environ.get('WORKER_JOB_ID')

    if not all([api_url, bearer_token, job_id]):
        print("  ⚠ Missing API credentials, skipping backend update")
        return

    # Build step data for backend
    step_data = {
        "step_num": step_num,
        "step_name": step.name,
        "return_code": return_code,
        "action": action,
    }

    # Add step_result data if available
    if step_result:
        if step_result.get("summary"):
            step_data["summary"] = step_result["summary"]
        if step_result.get("commit_info"):
            step_data["commit_hash"] = step_result["commit_info"].get("commit_hash")
            step_data["files_changed"] = step_result["commit_info"].get("files_changed", [])
        if step_result.get("pushed"):
            step_data["pushed"] = step_result["pushed"]

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

                print(f"Job Type: {job_type}")
                print(f"Repo URL: {repo_url}")
                print(f"Claude URL: {claude_url}")

                # Setup workspace in /app
                if not setup_workspace("/app"):
                    print("Failed to setup workspace")
                    continue

                # Clone target repository to /app/repo
                if not clone_repository(repo_url, repo_ref, "/app/repo"):
                    print("Failed to clone repository")
                    continue

                # Rename current branch to 'main' for consistent push behavior
                # This ensures we always push to 'main' regardless of source repo's default branch
                subprocess.run(
                    ["git", "branch", "-M", "main"],
                    cwd="/app/repo",
                    capture_output=True
                )

                # Execute workflow using main.py
                from pathlib import Path
                from main import run_workflow

                # Set environment variable for framework root
                framework_root = Path(__file__).parent.resolve()
                os.environ['RECON_FRAMEWORK_ROOT'] = str(framework_root)

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
                        continue

                elif job_type == "relativeWorkflow":
                    # Mode 3: Use workflow from .claude repo (legacy)
                    workflow_name = job_info.get("workflowName")

                    # Clone claude config for this mode
                    if not clone_claude_config(claude_url, claude_ref, "/app/.claude"):
                        print("Failed to clone Claude config")
                        continue

                    workflow_file = f"/app/.claude/workflows/{workflow_name}.json"
                    print(f"Relative Workflow Mode: {workflow_name}")

                    if not os.path.exists(workflow_file):
                        print(f"Error: Workflow not found: {workflow_file}")
                        continue
                else:
                    print(f"Error: Unknown job type: {job_type}")
                    continue

                print(f"Executing workflow: {workflow_file}")

                # Create GitHub repo BEFORE workflow runs so we can push per-step
                timestamp = int(time.time())
                repo_basename = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
                new_repo_name = f"{repo_basename}-processed-{timestamp}"

                github_token = os.environ.get("GITHUB_TOKEN", "")

                success, new_repo_url, owner = create_github_repo(new_repo_name, github_token)
                if not success:
                    print("Failed to create GitHub repository")
                    continue

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

                # Send repo URL to backend immediately (not as a step)
                org_name, _ = parse_repo_info(new_repo_url)
                update_job_data(api_url, bearer_token, job_id, {
                    "repoUrl": new_repo_url,
                    "orgName": org_name,
                    "repoName": new_repo_name
                })

                # All job types now run from /app/repo since configs are also in /app
                effective_repo_path = "/app/repo"

                # Run the workflow with worker-specific hooks
                workflow_result = run_workflow(
                    workflow_file=workflow_file,
                    dangerous=permissions_flag,
                    loop_hardcap=5,  # TODO: Make configurable via API
                    logs_dir="/app/logs",
                    repo_path=effective_repo_path,
                    before_hook=worker_before_step_hook,
                    after_hook=worker_after_step_hook
                )

                if workflow_result != 0:
                    print(f"Workflow execution failed with code {workflow_result}")
                    # Still continue to mark job complete with error

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
