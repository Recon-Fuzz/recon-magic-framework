# Workflow Reader

## Installation

```bash
uv pip install pydantic
```

## Usage

```bash
uv run workflow_reader.py
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