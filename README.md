# Workflow Reader

## Installation

```bash
uv pip install pydantic
```

## Setup

Setup a .env with OPENAI_API_KEY

The Key can be from Openrouter!

## Usage

**CLI (recommended):**
```bash
recon --workflow ./workflows/audit.json
recon --workflow ./my-workflow.json --dangerous --cap 10 --logs ./logs --repo ./target
```

**Direct (simple):**
```bash
python main.py workflows/workflow.json
```


## Automated Workflow Generation

Convert markdown agent files to workflow JSON:

```bash
cd utilities/workflow-maker
uv run generate_workflows.py ../../ai-agent-primers/agents
```

This reads markdown files from ai-agent-primers and generates workflow JSON files that can be used with the recon CLI.

## Studio

Visual workflow editor at `http://localhost:8000/studio/` - auto-syncs with type.ts.

Paste a workflow or create a new one and download it.

**Run:**
```bash
uv run python -m http.server 8000
```

Then open http://localhost:8000/studio/ in your browser.

## Looper

Repeat a Claude Code prompt X times.

**Install:**
```bash
cd looper && uv tool install --editable .
```

**Usage:**
```bash
looper "your prompt" --times 5 [--dangerous]
```

Streams raw JSON logs. Use `--dangerous` to skip permissions.