# Recon Magic Framework

LLM-powered workflow automation for security analysis and smart contract auditing.

## Architecture

Three entry points, one engine:
- `cli.py` — Local CLI (`recon-magic-framework` binary via pyproject.toml)
- `worker.py` — Cloud job listener (polls API, clones repos, runs workflows, pushes results)
- `main.py` — Core workflow engine (used by both CLI and worker as a library)

### Core modules (`core/`)
- `task.py` — Task step execution (CLAUDE_CODE, OPENCODE, PROGRAM, DISPATCH_FUZZING_JOB model types)
- `decision.py` — Decision step evaluation (8 modes: FILE_EXISTS, FILE_CONTAINS, READ_FILE, USE_MODEL, READ_FILE_WITH_MODEL_DIGEST, JSON_KEY_VALUE, GREP, SHELL)
- `model_decision.py` — LLM-based decisions via LangChain + OpenRouter structured outputs
- `git_commit.py` — Git utilities (init, commit, status)
- `path_utils.py` — Base path resolution (RECON_FOUNDRY_ROOT > RECON_REPO_PATH > cwd)

### Server modules (`server/`)
- `jobs.py` — Backend API for job status, stop requests
- `setup.py` — Workspace setup, repo cloning, config cloning
- `github.py` — GitHub repo creation, collaborator invites, app installation
- `postprocess.py` — Summary generation with Claude after workflow completion
- `utils.py` — URL parsing utility

### Other
- `tools/` — 11 Python CLI tools for coverage, fuzzing, function extraction (each registered in pyproject.toml)
- `workflows/` — JSON workflow definitions (30+ files)
- `prompts/` — Markdown agent definitions loaded by task.py at runtime
- `studio/` — Browser-based visual workflow editor
- `type.ts` — TypeScript schema for studio editor (must stay in sync with Python models)
- `log_formatters/` — Stream parsers for Claude Code and OpenCode output

## Build & Run

```bash
# Install
uv tool install --editable .

# Run a workflow locally
recon-magic-framework --workflow audit --repo /path/to/repo
recon-magic-framework --prompt "analyze this" --dangerous

# Run worker (cloud)
python worker.py <api_url> <bearer_token> [true]
```

No test suite exists. Validate changes by running a workflow end-to-end.

## Key Environment Variables

| Variable | Set by | Purpose |
|---|---|---|
| `RECON_FRAMEWORK_ROOT` | CLI/worker automatically | Path to this repo (for resolving tools, prompts, log formatters) |
| `RECON_REPO_PATH` | CLI `--repo` flag / worker | Target repository root |
| `RECON_FOUNDRY_ROOT` | Auto-detected | Directory containing foundry.toml (monorepo support) |
| `PROMPTS_DIR` | CLI/worker automatically | Where agent .md files live (default: `{framework_root}/prompts`) |
| `RUNNER_ENV` | `--dangerous` flag | Set to `production` to skip Claude permissions |
| `OPENAI_API_KEY` | User `.env` | OpenRouter API key for model decisions |
| `ANTHROPIC_API_KEY` | User `.env` | For Claude Code model type |
| `WORKER_API_URL`, `WORKER_BEARER_TOKEN`, `WORKER_JOB_ID` | Worker only | Backend API credentials for cloud jobs |

## Conventions

- Workflows are JSON files following the schema in `type.ts` / Pydantic models in `main.py`
- Workflow steps are either `task` (execute something) or `decision` (branch logic)
- `workflow` type steps reference other workflow files (composition) — flattened at load time
- Gates (preconditions) are defined in `workflow-gates.json` and referenced by step `preconditions` field
- Agent prompts can reference `.md` files in prompts/ — task.py auto-loads and injects content
- The `_resolve_agent_prompt()` helper in task.py handles agent file resolution for both CLAUDE_CODE and OPENCODE
- Path resolution always goes through `core/path_utils.py` — prefer RECON_FOUNDRY_ROOT over RECON_REPO_PATH
- All subprocess commands for PROGRAM steps run with `cwd=RECON_FOUNDRY_ROOT`
- Loop hardcap (default 5) prevents infinite decision loops — configurable via `--cap`
- Worker creates a GitHub repo per job, pushes per-step, and generates summaries on completion

## Common Patterns

### Adding a new decision mode
1. Add to `DecisionMode` enum in `core/decision.py`
2. Add handler in `execute_decision_step()` following the existing if-chain pattern
3. Add TypeScript interface in `type.ts` and update the `DecisionStep` union type
4. Document in README under Decision Modes

### Adding a new model type
1. Add constant to `ModelType` class in `core/task.py`
2. Add execution branch in `execute_task_step()`
3. Add model mappings in `resolve_model_string()` if it uses shorthand names
4. Update `type.ts` enum

### Adding a new CLI tool
1. Create directory under `tools/` with a Python module containing `main()`
2. Register in `pyproject.toml` under `[project.scripts]`
3. Tools are invoked from workflow PROGRAM steps via their CLI name
