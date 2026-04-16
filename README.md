# Recon Magic Framework

A workflow automation framework for running LLM-powered tasks on code repositories. Designed for security analysis, smart contract auditing, and automated code review workflows.

## Features

- Execute multi-step workflows with LLMs (Claude Code, OpenCode, etc.)
- Conditional branching with decision nodes
- Automatic git commit tracking after each step
- Loop and jump control flow
- Generate workflows from markdown agent definitions
- Visual workflow editor

## Installation

### Prerequisites

- Python 3.12 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- Git

### Install the CLI

```bash
# Clone the repository
git clone <repository-url>
cd recon-magic-framework

# Install globally using uv
uv tool install --editable .
```

## Setup

### Environment Variables

Create a `.env` file in the framework root (see `.env.example`). The main variables:

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes (for `CLAUDE_CODE` model) | Anthropic API key for Claude Code tasks |
| `OPENROUTER_API_KEY` / `OPENAI_API_KEY` | Yes (for `OPENCODE` model) | Key for OpenRouter or OpenAI-compatible provider |
| `RUNNER_ENV` | No | Set to `production` to enable `--dangerously-skip-permissions` for Claude Code |
| `RECON_REPO_PATH` | Auto | Set automatically by the CLI to the target repository path |
| `RECON_FOUNDRY_ROOT` | Auto | Auto-detected for monorepos (directory containing `foundry.toml`) |
| `RECON_FRAMEWORK_ROOT` | Auto | Set automatically by the CLI to the framework installation path |

## Usage

**CLI (recommended):**
```bash
recon-magic-framework --workflow audit
recon-magic-framework --workflow workflow-loop --dangerous --cap 10 --logs ./logs
```

**Direct (simple):**
```bash
python main.py workflows/audit.json
```

**Important**: The command must be run from the root of a git repository.

### Environment Configuration

Create a `.env` file in the framework root directory for any required environment variables:

```bash
# Example .env file
ANTHROPIC_API_KEY=your_api_key_here
```

## Workflow Structure

Workflows are JSON files that define a sequence of steps to execute. Each step can be a task (execute a prompt) or a decision (conditional branching).

### Basic Workflow Example

```json
{
  "name": "My Workflow",
  "steps": [
    {
      "type": "task",
      "name": "Step 1: Analyze Code",
      "description": "Perform initial code analysis",
      "prompt": "Analyze the codebase and identify potential security issues",
      "model": {
        "type": "CLAUDE_CODE",
        "model": "inherit"
      },
      "output": {
        "capture": true,
        "save_to": "analysis-results-{timestamp}.json"
      },
      "shouldCreateSummary": false,
      "shouldCommitChanges": true
    },
    {
      "type": "decision",
      "name": "Step 2: Check for Critical Issues",
      "description": "Stop if critical issues found",
      "mode": "READ_FILE",
      "modeInfo": {
        "fileName": "CRITICAL_ISSUES.md"
      },
      "decision": [
        {
          "operator": "eq",
          "value": 1,
          "action": "STOP"
        },
        {
          "operator": "eq",
          "value": 0,
          "action": "CONTINUE"
        }
      ],
      "shouldCreateSummary": false,
      "shouldCommitChanges": false
    }
  ]
}
```

### Model Types

- **CLAUDE_CODE**: Uses Claude Code for interactive coding tasks
- **PROGRAM**: Executes shell commands directly
- **OPENCODE**: Uses alternative code assistant
- **INHERIT**: Inherits model configuration from parent

### Decision Modes

Decision steps support several modes that determine how the condition value is obtained:

| Mode | Description | `modeInfo` fields |
|---|---|---|
| `FILE_EXISTS` | Check if a file (or glob pattern) exists. Returns `1` if found, `0` if not. | `fileName` |
| `FILE_CONTAINS` | Check if a file contains a specific string. Returns `1` if found, `0` if not. | `fileName`, `searchString` |
| `READ_FILE` | Read file contents and parse as a number for comparison. | `fileName` |
| `JSON_KEY_VALUE` | Read a specific key path from a JSON file (e.g. `summary.count`). | `fileName`, `keyPath` |
| `GREP` | Run a grep pattern on files matching a glob. Returns the total match count. | `pattern`, `file` |
| `SHELL` | Run a shell command. Returns the exit code for comparison. | `command` |
| `USE_MODEL` | Use an LLM to evaluate a prompt and select a decision value. | `prompt` (+ `model` on step) |
| `READ_FILE_WITH_MODEL_DIGEST` | Read a file, then pass its contents to an LLM to digest and decide. | `fileName`, `prompt` (+ `model` on step) |

### Decision Actions

Decision steps can trigger different actions based on conditions:

- **CONTINUE**: Proceed to the next step (default)
- **STOP**: Halt workflow execution
- **JUMP_TO_STEP**: Jump to a named step (forward or backward)
- **REPEAT_PREVIOUS_STEP**: Loop back one step

### Step Configuration

Each step supports these options:

- `shouldCreateSummary`: Create a summary after step completion (future feature)
- `shouldCommitChanges`: Automatically commit git changes after the step
- `output`: Optional configuration to capture and save step output
  - `capture`: Set to `true` to capture the step's output (stdout/stderr for PROGRAM steps, response content for LLM steps)
  - `save_to`: File path where the output should be saved
    - Supports `{timestamp}` placeholder which is replaced with the timestamp value from the tool's output data
    - Captured output is automatically written to the specified file path
    - For PROGRAM model types, captures command execution output
    - For LLM model types (CLAUDE_CODE, OPENCODE), captures the agent's response

## Creating Workflows

### Method 1: Write JSON Manually

Create JSON files in the `workflows/` directory. See examples:

- `workflows/audit.json` - Multi-phase audit workflow
- `workflows/workflow-jump-example.json` - Conditional branching
- `workflows/workflow-loop.json` - Looping example

### Method 2: Generate from Markdown

Convert markdown agent definitions to workflow JSON:

```bash
cd utilities/workflow-maker
uv run generate_workflows.py ../../ai-agent-primers/agents
```

#### Markdown Format

```markdown
---
name: audit-phase-0
description: Initial scoping phase
model: inherit
---

Your prompt instructions here...
```

Files should follow the pattern: `<workflow-name>-phase-<N>.md`

### Method 3: Visual Editor (Studio)

Launch the visual workflow editor:

```bash
uv run python -m http.server 8000
```

Then open http://localhost:8000/studio/ in your browser. The editor auto-syncs with `type.ts` for type safety.

## Example Workflows

### Security Audit Workflow

```bash
recon-magic-framework --workflow audit
```

This runs a multi-phase smart contract audit with decision points to stop early if critical issues are found.

### Echidna Fuzzing Workflow

```bash
recon-magic-framework --workflow workflow-echidna-example
```

Automated fuzzing setup and execution workflow.

## Utilities

### Workflow Maker

Generate workflows from markdown agent files:

```bash
cd utilities/workflow-maker
uv run generate_workflows.py <agents_dir> [output_dir]

# Add decision nodes after each step
uv run generate_workflows.py <agents_dir> --add-decisions
```

### Looper

Repeat a Claude Code prompt multiple times:

```bash
cd looper
uv tool install --editable .

# Run a prompt 5 times
looper "your prompt" --times 5 [--dangerous]
```

Streams raw JSON logs. Use `--dangerous` to skip permission prompts.

## Advanced Features

### Loop Protection

Decision steps have a hardcap of 5 executions to prevent infinite loops. After 5 executions, the step automatically continues.

### Git Integration

The framework automatically:
- Checks for git repository
- Initializes git if needed
- Commits changes after steps (when `shouldCommitChanges: true`)
- Generates descriptive commit messages from step metadata

## Development

### Project Structure

```
.
├── cli.py                  # CLI entry point (recon-magic-framework binary)
├── main.py                 # Workflow execution engine
├── worker.py               # Server/cloud worker for remote execution
├── type.ts                 # TypeScript type definitions (used by studio editor)
├── core/                   # Core execution modules
│   ├── task.py             # Task step execution (CLAUDE_CODE, OPENCODE, PROGRAM)
│   ├── decision.py         # Decision step execution (8 modes)
│   ├── model_decision.py   # LLM-based decision helper
│   ├── git_commit.py       # Git utilities
│   └── path_utils.py       # Path resolution (RECON_FOUNDRY_ROOT / RECON_REPO_PATH)
├── workflows/              # Workflow JSON files
├── prompts/                # Agent reference documents and prompt templates
├── tools/                  # Installable CLI tools (coverage eval, function extraction, etc.)
├── server/                 # Server components (jobs, postprocessing, GitHub integration)
├── studio/                 # Visual workflow editor (browser-based)
├── programs/               # Shell scripts and helper programs
├── log_formatters/         # Log formatting utilities
└── utilities/              # Helper tools
    ├── workflow-maker/     # Markdown to JSON converter
    └── looper/             # Prompt repetition tool
```

### Type Safety

The workflow schema is defined using Pydantic models in `main.py` and TypeScript types in `type.ts` for the visual editor.

## License

GPL-2.0