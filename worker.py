"""
Worker module for recon-magic framework.
Main job listener loop that orchestrates the workflow.
"""

import json
import os
import subprocess
import sys
import time

from server.github import create_github_repo, invite_collaborator, push_to_github
from server.jobs import fetch_job_details, fetch_pending_jobs
from server.postprocess import generate_summary_with_claude, mark_job_complete
from server.setup import clone_claude_config, clone_repository, setup_workspace
from server.utils import parse_repo_info


def worker_before_step_hook(step, step_num: int) -> None:
    """
    Worker-specific hook that runs before step execution.
    This is where you can add API calls to update job status.

    Args:
        step: The workflow step being executed
        step_num: The step number (1-indexed)
    """
    print(f"[Worker] Before step {step_num}: {step.name}")
    print(f"Type: {step.type}")
    if hasattr(step, 'model') and step.model:
        print(f"Model: {step.model.type}")
    print(f"Description: {step.description or 'N/A'}")

    ## TODO: Add API call to update job step status

    # Example:
    # api_url = os.environ.get('WORKER_API_URL')
    # bearer_token = os.environ.get('WORKER_BEARER_TOKEN')
    # job_id = os.environ.get('WORKER_JOB_ID')
    # if api_url and bearer_token and job_id:
    #     update_job_step_status(api_url, bearer_token, job_id, step.name, "in_progress")

    ## Set Status for the step.
    ## Maybe set Repo on the first loop if that is not already done somewhere else.


def worker_after_step_hook(step, step_num: int, return_code: int, action: str) -> None:
    """
    Worker-specific hook that runs after step execution.
    This is where you can add API calls to save step summaries or results.

    Args:
        step: The workflow step that was executed
        step_num: The step number (1-indexed)
        return_code: The exit code from step execution (0 = success)
        action: The action taken (CONTINUE, STOP, JUMP_TO_STEP, etc.)
    """
    print(f"[Worker] After step {step_num}: {step.name}")
    print(f"Return code: {return_code}, Action: {action}")

    ## Commit and summary | Just do Local Commit for now.

    ## TODO: Add API call to save step summary/results
    # Example:
    # api_url = os.environ.get('WORKER_API_URL')
    # bearer_token = os.environ.get('WORKER_BEARER_TOKEN')
    # job_id = os.environ.get('WORKER_JOB_ID')
    # if api_url and bearer_token and job_id:
    #     save_step_summary(api_url, bearer_token, job_id, step_num, {
    #         "name": step.name,
    #         "return_code": return_code,
    #         "action": action
    #     })


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
                job_type = job_info.get("jobType", "directPrompt")

                print(f"Job Type: {job_type}")
                print(f"Repo URL: {repo_url}")
                print(f"Claude URL: {claude_url}")

                # Setup workspace
                if not setup_workspace():
                    print("Failed to setup workspace")
                    continue

                # Clone target repository
                if not clone_repository(repo_url, repo_ref):
                    print("Failed to clone repository")
                    continue

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

                # Determine workflow file based on job type
                if job_type == "directPrompt":
                    # Mode 1: Direct prompt execution
                    prompt = job_info.get("claudePromptCommand")
                    model_type = job_info.get("modelType", "CLAUDE_CODE")

                    print(f"Direct Prompt Mode - Model: {model_type}")
                    print(f"Prompt: {prompt[:100]}..." if len(prompt) > 100 else f"Prompt: {prompt}")

                    workflow_file = create_dynamic_workflow(prompt, model_type, str(job_id))

                elif job_type == "workflowName":
                    # Mode 2: Use workflow from framework workflows/
                    workflow_name = job_info.get("workflowName")
                    workflow_file = str(framework_root / "workflows" / f"{workflow_name}.json")

                    print(f"Framework Workflow Mode: {workflow_name}")

                    if not os.path.exists(workflow_file):
                        print(f"Error: Workflow not found: {workflow_file}")
                        continue

                elif job_type == "relativeWorkflow":
                    # Mode 3: Use workflow from .claude repo (legacy)
                    workflow_name = job_info.get("workflowName")

                    # Clone claude config for this mode
                    if not clone_claude_config(claude_url, claude_ref):
                        print("Failed to clone Claude config")
                        continue

                    workflow_file = f".claude/workflows/{workflow_name}.json"
                    print(f"Relative Workflow Mode: {workflow_name}")

                    if not os.path.exists(workflow_file):
                        print(f"Error: Workflow not found: {workflow_file}")
                        continue
                else:
                    print(f"Error: Unknown job type: {job_type}")
                    continue

                print(f"Executing workflow: {workflow_file}")

                # Run the workflow with worker-specific hooks
                workflow_result = run_workflow(
                    workflow_file=workflow_file,
                    dangerous=permissions_flag,
                    loop_hardcap=5,  # TODO: Make configurable via API
                    logs_dir="./logs",
                    repo_path="./repo",
                    before_hook=worker_before_step_hook,
                    after_hook=worker_after_step_hook
                )

                if workflow_result != 0:
                    print(f"Workflow execution failed with code {workflow_result}")
                    continue

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
