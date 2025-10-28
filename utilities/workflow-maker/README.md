# Workflow Maker

Convert markdown agent files to workflow JSON for recon-magic-framework.

## Install

```bash
cd workflow-maker
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install pyyaml
```

## Usage

```bash
# Basic - generate workflows
uv run generate_workflows.py <agents_dir> [output_dir]

# Add no-op decision nodes after each step
uv run generate_workflows.py <agents_dir> --add-decisions
```

## Example

```bash
# Generate from ai-agent-primers
uv run generate_workflows.py ../ai-agent-primers/agents

# Output: ../ai-agent-primers/workflows/*.json
```

## Input Format

Markdown files: `<workflow-name>-phase-<N>.md`

```markdown
---
name: audit-phase-0
description: First phase
model: inherit
---

Your prompt here...
```

## Flags

- `--add-decisions` - Insert decision node after each task (always continues)
