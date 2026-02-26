# Error Scenarios in RECON Magic Framework

This document catalogs all error scenarios, failure modes, and exception handling in the framework.

## Exit Codes

| Code | Constant | Meaning |
|------|----------|---------|
| 0 | `SUCCESS` | Workflow completed successfully |
| 1 | `FAILURE` | Workflow failed at a step |
| 2 | `STOPPED` | Graceful stop requested |

---

## 1. Workflow-Level Errors

### 1.1 Workflow Loading Errors

| Location | Error | Message | Raised/Returned |
|----------|-------|---------|-----------------|
| `main.py:125` | Circular reference | `Circular workflow reference detected: {source_file}` | `ValueError` |
| `main.py:138` | Missing workflow_file | `Workflow step missing 'workflow_file' field: {step}` | `ValueError` |
| `main.py:143` | Sub-workflow not found | `Sub-workflow not found: {sub_workflow_path}` | `FileNotFoundError` |
| `cli.py:159` | Workflow not in framework | `Workflow '{workflow_file}.json' not found in framework workflows/` | `sys.exit(1)` |
| `cli.py:168` | Workflow file not found | `Workflow file not found: {workflow_file}` | `sys.exit(1)` |

### 1.2 Resume Errors

| Location | Error | Message | Returned |
|----------|-------|---------|----------|
| `main.py:753-757` | Invalid resume step ID | `Invalid resume step ID: '{resume_from_step_id}' not found in workflow` | `FAILURE` |
| `worker.py:735-736` | Workflow failed to start | `Workflow failed to start. Check that the resume step ID is valid.` | Summary text |

---

## 2. Step Execution Errors

### 2.1 Unknown Step Type

| Location | Error | Message | Returned |
|----------|-------|---------|----------|
| `main.py:466-467` | Unknown step type | `Unknown step type: {type(step)}` | `(FAILURE, "CONTINUE", None)` |

### 2.2 Gate/Precondition Failures

| Location | Error | Message | Returned |
|----------|-------|---------|----------|
| `main.py:374` | Check step failed | `Check step failed` | Continues to retry |
| `main.py:381` | Gate condition not met | `Gate condition not met` | Continues to retry |
| `main.py:403` | Max retries exceeded | `Max retries ({max_retries}) exceeded for gate '{gate_name}'` | Continues to retry |
| `main.py:424` | Gate failed after retries | `Gate '{gate_name}' failed after {max_retries} retries` | `(False, error_msg)` |
| `main.py:426` | Gate failed | `Gate '{gate_name}' failed` | `(False, error_msg)` |
| `main.py:805-811` | Gate failed for step | `Gate '{gate_name}' failed for step {i}` | `FAILURE` |

### 2.3 JUMP_TO_STEP Errors

| Location | Error | Message | Returned |
|----------|-------|---------|----------|
| `main.py:865-867` | Missing destinationStep | `JUMP_TO_STEP action requires destinationStep, but none was provided` | `FAILURE` |
| `main.py:872-874` | Step not found | `JUMP_TO_STEP failed: Step '{destination_step_name}' not found in workflow` | `FAILURE` |
| `main.py:878-880` | Self-jump (infinite loop) | `JUMP_TO_STEP failed: Cannot jump to current step (would cause infinite loop)` | `FAILURE` |

---

## 3. Task Step Errors (core/task.py)

### 3.1 PROGRAM Type Errors

| Location | Error | Message | Returned |
|----------|-------|---------|----------|
| `core/task.py:200-214` | Command failed | `Command failed with exit code {result.returncode}` | `(FAILURE, "CONTINUE", None)` |
| `core/task.py:243-246` | JSON parse error | `Error: Failed to parse JSON output: {e}` | `(FAILURE, "CONTINUE", None)` |
| `core/task.py:248-249` | Save output error | `Error: Failed to save output: {e}` | `(FAILURE, "CONTINUE", None)` |

### 3.2 CLAUDE_CODE Type Errors

| Location | Error | Message | Returned |
|----------|-------|---------|----------|
| `core/task.py:312` | Agent file not found | `Agent file not found: {agent_file_path}` | Warning only, continues |
| `core/task.py:336-337` | Execution failed | `Claude Code execution failed with exit code {result.returncode}` | `(FAILURE, "CONTINUE", None)` |

### 3.3 OPENCODE Type Errors

| Location | Error | Message | Returned |
|----------|-------|---------|----------|
| `core/task.py:370` | Agent file not found | `Agent file not found: {agent_file_path}` | Warning only, continues |
| `core/task.py:395-396` | Execution failed | `OpenCode execution failed with exit code {result.returncode}` | `(FAILURE, "CONTINUE", None)` |

### 3.4 DISPATCH_FUZZING_JOB Type Errors

| Location | Error | Message | Returned |
|----------|-------|---------|----------|
| `core/task.py:413-415` | Missing worker context | `Missing worker context (WORKER_API_URL, WORKER_BEARER_TOKEN, WORKER_JOB_ID)` | `(FAILURE, "CONTINUE", None)` |
| `core/task.py:476-483` | HTTP error | `Failed to dispatch fuzzing job: {error_body}` | `(FAILURE, "CONTINUE", None)` |
| `core/task.py:485-486` | General error | `Error dispatching fuzzing job: {e}` | `(FAILURE, "CONTINUE", None)` |

---

## 4. Decision Step Errors (core/decision.py)

| Location | Error | Message | Returned |
|----------|-------|---------|----------|
| `core/decision.py:123` | Value conversion error | (silent catch) | Falls through to next condition |
| `core/decision.py:189` | MCP tool call error | `Error calling MCP tool '{tool_name}': {e}` | Returns error string |
| `core/decision.py:214` | Counter conversion error | (silent catch) | Falls through |
| `core/decision.py:274` | Model output parse error | `Failed to parse model output as JSON` | Returns error string |
| `core/decision.py:298` | HTTP error | `HTTP error: {e}` | Returns error string |
| `core/decision.py:346` | General error | `Error evaluating model decision: {e}` | Returns error string |

### 4.1 Model Decision Errors (core/model_decision.py)

| Location | Error | Message | Raised |
|----------|-------|---------|--------|
| `core/model_decision.py:47` | Missing required field | `DecisionStep with model type requires 'model' field with 'provider' and 'model' subfields` | `ValueError` |
| `core/model_decision.py:168` | File not found | `Error: File not found: {file_path}` | Returned as string |
| `core/model_decision.py:173` | File read error | Caught exception | Returns empty string |

---

## 5. Git Operations Errors

### 5.1 In main.py

| Location | Error | Message | Behavior |
|----------|-------|---------|----------|
| `main.py:602` | Init failed | `Failed to initialize git repository` | Returns None |
| `main.py:609` | Status check failed | `Failed to check git status` | Returns None |
| `main.py:623` | Add failed | `Failed to add changes: {stderr}` | Returns None |
| `main.py:653` | Commit failed | `Failed to commit changes: {stderr}` | Returns None |
| `main.py:683` | Push failed | `Failed to push changes: {stderr}` | Warning, returns False |

### 5.2 In core/git_commit.py

| Location | Error | Message | Behavior |
|----------|-------|---------|----------|
| `core/git_commit.py:41` | Init failed | `Failed to initialize git repository: {stderr}` | Returns (False, ...) |
| `core/git_commit.py:65` | Status failed | `Failed to check git status` | Returns (False, ...) |
| `core/git_commit.py:76` | Add failed | `Failed to add changes: {stderr}` | Returns (False, ...) |
| `core/git_commit.py:94` | Commit failed | `Failed to commit changes: {stderr}` | Returns (False, ...) |

---

## 6. Worker Errors (worker.py)

### 6.1 API Communication Errors

| Location | Error | Message | Behavior |
|----------|-------|---------|----------|
| `worker.py:38` | AI detection failed | `AI detection failed: {e}` | Warning, continues |
| `worker.py:165` | Send job data failed | `Failed to send job data to backend: {e}` | Warning, continues |
| `worker.py:205` | Send step data failed | `Failed to send step data to backend: {e}` | Warning, continues |
| `worker.py:249` | Update phase failed | `Failed to update current phase: {e}` | Warning, continues |

### 6.2 Setup Errors

| Location | Error | Message | Behavior |
|----------|-------|---------|----------|
| `worker.py:416` | Fetch job details failed | `Failed to fetch details for job {job_id}` | Skips job |
| `worker.py:442-447` | Setup workspace failed | `Failed to setup workspace. Please try again.` | Marks job ERROR |
| `worker.py:457-462` | Clone repository failed | `Failed to clone repository: {repo_url}...` | Marks job ERROR |
| `worker.py:518` | Clone Claude config failed | `Warning: Failed to clone Claude config, continuing without it` | Warning, continues |
| `worker.py:520` | Clone OpenCode config failed | `Warning: Failed to clone OpenCode config, continuing without it` | Warning, continues |
| `worker.py:539` | Workflow not found | `Error: Workflow not found: {workflow_file}` | Marks job ERROR |
| `worker.py:558-563` | Clone Claude config failed (CUSTOM) | `Failed to clone Claude config repository...` | Marks job ERROR |
| `worker.py:575` | Workflow not found (CUSTOM) | `Error: Workflow not found: {workflow_file}` | Marks job ERROR |
| `worker.py:588` | Unknown job type | `Error: Unknown job type: {job_type}` | Marks job ERROR |

### 6.3 GitHub Setup Errors

| Location | Error | Message | Behavior |
|----------|-------|---------|----------|
| `worker.py:614-619` | Create GitHub repo failed | `Failed to create GitHub repository...` | Marks job ERROR |
| `worker.py:633` | Install GitHub App failed | `Failed to install GitHub App on repository` | Warning, continues |
| `worker.py:643` | Invite collaborator failed | `Failed to invite {handle}: {e}` | Warning, continues |
| `worker.py:664` | Push initial code failed | `Failed to push initial code: {e}` | Warning, continues |

### 6.4 Workflow Execution Errors

| Location | Error | Message | Behavior |
|----------|-------|---------|----------|
| `worker.py:705-707` | Workflow failed | `Workflow execution failed with code {workflow_result}` / `Failed at step {step_num}: {step_name} ({reason})` | Marks job ERROR |
| `worker.py:775` | Unexpected error | `Job failed due to unexpected error: {str(e)}` | Marks job ERROR |
| `worker.py:793` | Mark job error failed | `Failed to mark job as error: {mark_error}` | Logged only |

---

## 7. Server Module Errors

### 7.1 GitHub Operations (server/github.py)

| Location | Error | Message | Behavior |
|----------|-------|---------|----------|
| `server/github.py:44` | Create repo failed | `Failed to create repository. HTTP status: {status_code}` | Returns None |
| `server/github.py:48` | Create repo exception | `Exception creating GitHub repo: {e}` | Returns None |
| `server/github.py:82` | Invite collaborator failed | `Failed to send collaborator invite. HTTP status: {status_code}` | Returns False |
| `server/github.py:86` | Invite exception | `Exception inviting collaborator: {e}` | Returns False |
| `server/github.py:112` | Install app failed | `Failed to install GitHub App. HTTP status: {status_code}` | Returns False |
| `server/github.py:116` | Install app exception | `Exception installing GitHub App: {e}` | Returns False |
| `server/github.py:167` | Setup remote failed | `Failed to setup git remote: {e}` | Warning, continues |
| `server/github.py:225` | No changes/commit failed | `No changes to commit or commit failed` | Logged |
| `server/github.py:238` | Git command failed | `Git command failed: {e}` | Logged |
| `server/github.py:241` | Push exception | `Exception pushing to GitHub: {e}` | Logged |

### 7.2 Setup Operations (server/setup.py)

| Location | Error | Message | Behavior |
|----------|-------|---------|----------|
| `server/setup.py:38` | Create workspace exception | `Exception: {e}` | Returns False |
| `server/setup.py:67` | Clone repo exception | `Exception cloning repository: {e}` | Returns False |
| `server/setup.py:95` | Clone Claude config exception | `Exception cloning Claude config: {e}` | Returns False |
| `server/setup.py:123` | Clone OpenCode config exception | `Exception cloning OpenCode config: {e}` | Returns False |

### 7.3 Job Operations (server/jobs.py)

| Location | Error | Message | Behavior |
|----------|-------|---------|----------|
| `server/jobs.py:26` | Fetch job exception | `Exception: {e}` | Returns None |
| `server/jobs.py:48` | Check stop exception | `Exception: {e}` | Returns False |
| `server/jobs.py:70` | Dequeue job exception | `Exception: {e}` | Returns None |

### 7.4 Postprocess Operations (server/postprocess.py)

| Location | Error | Message | Behavior |
|----------|-------|---------|----------|
| `server/postprocess.py:54` | Summary generation failed | `Summary generation failed` | Returns string |
| `server/postprocess.py:57` | Summary timeout | `Summary generation timed out` | Returns string |
| `server/postprocess.py:60` | Summary exception | `Summary generation error: {str(e)}` | Returns string |
| `server/postprocess.py:113` | Failure summary fallback | `Workflow failed at step {step_num}: {step_name}` | Returns string |
| `server/postprocess.py:116` | Failure summary timeout | `Workflow failed at step {step_num}: {step_name}` | Returns string |
| `server/postprocess.py:119` | Failure summary exception | `Workflow failed at step {step_num}: {step_name}` | Returns string |
| `server/postprocess.py:187` | Mark complete error | `Error marking job complete: {e}` | Returns False |

---

## 8. Tool Errors

### 8.1 Coverage Evaluation (tools/covg_eval/covg_eval.py)

| Location | Error | Message | Raised |
|----------|-------|---------|--------|
| `covg_eval.py:23` | No LCOV files | `No LCOV files found in {echidna_dir}` | `FileNotFoundError` |
| `covg_eval.py:36` | No valid LCOV files | `No valid LCOV files with timestamps found in {echidna_dir}` | `FileNotFoundError` |
| `covg_eval.py:574` | Magic dir not found | `Error: Magic directory not found: {magic_dir}` | `sys.exit` |
| `covg_eval.py:578` | Echidna dir not found | `Error: Echidna directory not found: {echidna_dir}` | `sys.exit` |
| `covg_eval.py:586` | recon-coverage.json not found | `Error: recon-coverage.json not found in {magic_dir}` | Logged |
| `covg_eval.py:591` | Invalid JSON | `Error: Invalid JSON in recon-coverage.json: {e}` | Logged |

### 8.2 Coverage Scoring (tools/covg_scoring/covg_scoring.py)

| Location | Error | Message | Raised |
|----------|-------|---------|--------|
| `covg_scoring.py:55` | Slither not installed | `Error: Slither is not installed...` | `sys.exit(1)` |
| `covg_scoring.py:64` | Slither analysis failed | `Error: Failed to analyze project with Slither: {e}` | `sys.exit(1)` |
| `covg_scoring.py:166` | No matching files | `Error: No files matching...` | `FileNotFoundError` |
| `covg_scoring.py:212` | Magic dir not found | `Error: Magic directory not found: {magic_dir}` | `sys.exit` |
| `covg_scoring.py:246` | General error | `Error: {e}` | `sys.exit` |

### 8.3 Echidna Analysis (tools/analyze_echidna_output/analyze_echidna_output.py)

| Location | Error | Message | Returned |
|----------|-------|---------|----------|
| `analyze_echidna_output.py:145` | Deployment failed | `deployment_failed` type | Error summary |
| `analyze_echidna_output.py:206` | setUp failed | `setUp() function failed during contract initialization` | Error summary |
| `analyze_echidna_output.py:281` | Compilation failed | `Solidity compilation failed...` | Error summary |
| `analyze_echidna_output.py:375` | No log file | `Echidna failed with exit code {exit_code} but no log file found...` | JSON |

### 8.4 Target Functions (tools/targeted_functions/extract_target_functions.py)

| Location | Error | Message | Raised |
|----------|-------|---------|--------|
| `extract_target_functions.py:243` | recon/ not found | `Error: 'recon/' directory not found in current working directory...` | `FileNotFoundError` |
| `extract_target_functions.py:286` | Targets dir not found | `Error: Targets directory not found: {targets_dir}` | `sys.exit` |
| `extract_target_functions.py:290` | Setup file not found | `Error: Setup file not found: {setup_file}` | `sys.exit` |

### 8.5 Filter Build Info (tools/filter_build_info/filter_build_info.py)

| Location | Error | Message | Behavior |
|----------|-------|---------|----------|
| `filter_build_info.py:119` | Input file not found | `Error: Input file not found: {args.input_file}` | `sys.exit` |
| `filter_build_info.py:123` | Not a file | `Error: Input path is not a file: {args.input_file}` | `sys.exit` |
| `filter_build_info.py:130` | Invalid JSON | `Error: Invalid JSON in input file: {e}` | `sys.exit` |

### 8.6 Merge Paths Prerequisites (tools/merge_paths_prerequisites/merge_paths_prerequisites.py)

| Location | Error | Message | Behavior |
|----------|-------|---------|----------|
| `merge_paths_prerequisites.py:36-38` | Paths file not found | `Error: Paths file not found: {paths_file}` | `sys.exit(1)` |
| `merge_paths_prerequisites.py:41-43` | Prerequisites file not found | `Error: Prerequisites file not found: {prerequisites_file}` | `sys.exit(1)` |
| `merge_paths_prerequisites.py:51-52` | Paths JSON error | `Error: {error_msg}` | `sys.exit(1)` |
| `merge_paths_prerequisites.py:64-65` | Prerequisites JSON error | `Error: {error_msg}` | `sys.exit(1)` |

---

## 9. Log Formatter Errors

### 9.1 Claude Code Formatter (log_formatters/claude_code.py)

| Location | Error | Message | Behavior |
|----------|-------|---------|----------|
| `claude_code.py:19` | Tool error | `[{tool_name}] {error_content}` | Printed with `❌` |

### 9.2 OpenCode Formatter (log_formatters/opencode.py)

| Location | Error | Message | Behavior |
|----------|-------|---------|----------|
| `opencode.py:67` | File not found | `Not found: {file}` | Printed with `❌` |
| `opencode.py:89` | JSON decode error | (silent) | Continues |
| `opencode.py:92` | General exception | `Error: {e}` | Printed |

---

## 10. Failure Info Tracking

### Current Implementation (worker.py:84-107)

```python
_workflow_failure_info = {
    "step_name": str,    # Name of failed step
    "step_num": int,     # Step number (1-indexed)
    "reason": str        # One of: "step_failure", "stop_action", "graceful_stop"
}
```

### Failure Reasons

| Reason | Trigger | Location |
|--------|---------|----------|
| `step_failure` | `action == "FAILED"` or `return_code == 1` | `worker.py:294-295` |
| `stop_action` | `action == "STOP"` | `worker.py:296-297` |
| `graceful_stop` | `action == "GRACEFUL_STOP"` or `return_code == 2` | `worker.py:298-299` |

---

## 11. Error Message Generation Gap

### Current State

When errors occur, messages are **printed to console** but **not captured** for reporting:

| Source | Has Error Message | Captured for API? |
|--------|-------------------|-------------------|
| Gate failure | Yes (`gate_failed: gate_name`) | Yes |
| PROGRAM command | Yes (exit code, stderr) | No |
| Claude Code | Yes (exit code) | No |
| OpenCode | Yes (exit code) | No |
| Dispatch fuzzing | Yes (HTTP error) | No |
| JSON parse error | Yes (exception) | No |

### Proposed Solution

Add `error_message` field to step_result and failure_info to capture actual error text for backend reporting.

---

## 12. Summary

### Error Count by Module

| Module | FAILURE Returns | Exceptions Raised | Error Prints |
|--------|-----------------|-------------------|--------------|
| main.py | 6 | 3 | 15+ |
| core/task.py | 6 | 0 | 8 |
| core/decision.py | 0 | 0 | 5 |
| worker.py | 0 | 0 | 20+ |
| server/* | 0 | 10+ | 15+ |
| tools/* | 0 | 15+ | 30+ |

### Key Observations

1. **No unified error message capture** - Errors are printed but not returned/stored
2. **Failure info only tracks location** - `step_name`, `step_num`, `reason` but no actual error message
3. **Backend receives minimal error data** - Only `failed: True` flag, no details
4. **Exception handling is defensive** - Most exceptions are caught and logged, not propagated
5. **Exit codes are consistent** - 0=success, 1=failure, 2=stopped used throughout
