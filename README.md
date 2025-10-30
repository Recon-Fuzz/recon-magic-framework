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

Setup a .env with OPENAI_API_KEY

The Key can be from Openrouter!

## Usage

**CLI (recommended):**
```bash
recon --workflow ./workflows/audit.json
recon --workflow ./my-workflow.json --dangerous --cap 10 --logs ./logs
```

**Direct (simple):**
```bash
python main.py workflows/workflow.json
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

## Creating Workflows

### Method 1: Write JSON Manually

Create JSON files in the `workflows/` directory. See examples:

- `workflows/workflow_audit.json` - Multi-phase audit workflow
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
recon workflows/workflow_audit.json
```

This runs a multi-phase smart contract audit with decision points to stop early if critical issues are found.

### Echidna Fuzzing Workflow

```bash
recon workflows/workflow-echidna-example.json
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
├── cli.py                 # CLI entry point
├── main.py               # Workflow execution engine
├── core/                 # Core execution modules
│   ├── task.py          # Task step execution
│   ├── decision.py      # Decision step execution
│   └── git_commit.py    # Git utilities
├── workflows/           # Workflow JSON files
└── utilities/           # Helper tools
    ├── workflow-maker/  # Markdown to JSON converter
    └── looper/         # Prompt repetition tool
```

### Type Safety

The workflow schema is defined using Pydantic models in `main.py` and TypeScript types in `type.ts` for the visual editor.

## License

[Your License Here]