#!/usr/bin/env python3
"""
Generate workflow JSON files from agent markdown files.

Usage:
    python generate_workflows.py <agents_dir> [output_dir]

Example:
    python generate_workflows.py ../ai-agent-primers/agents ../ai-agent-primers/workflows
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict
import yaml


def parse_frontmatter(content: str) -> Tuple[dict, str]:
    """
    Extract YAML frontmatter and markdown content.

    Returns:
        (metadata_dict, markdown_content)
    """
    # Match --- frontmatter ---
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', content, re.DOTALL)

    if not match:
        raise ValueError("No frontmatter found")

    frontmatter_text = match.group(1)
    markdown_content = match.group(2).strip()

    metadata = yaml.safe_load(frontmatter_text)

    return metadata, markdown_content


def markdown_to_step(md_path: Path) -> dict:
    """
    Convert a markdown agent file to a workflow step.

    Expected frontmatter:
        ---
        name: audit-naive-phase-0
        description: First phase description
        model: inherit  # or claude-sonnet-4, etc.
        color: red
        shouldCreateSummary: false  # optional
        shouldCommitChanges: true   # optional
        ---
    """
    content = md_path.read_text()
    metadata, prompt = parse_frontmatter(content)

    # Determine model type
    model_value = metadata.get('model', 'inherit')
    if model_value == 'inherit':
        model_type = "CLAUDE_CODE"
        model_name = "inherit"
    else:
        model_type = "CLAUDE_CODE"
        model_name = model_value

    return {
        "name": metadata['name'],
        "type": "task",
        "description": metadata.get('description', ''),
        "prompt": prompt,
        "model": {
            "type": model_type,
            "model": model_name
        },
        "shouldCreateSummary": metadata.get('shouldCreateSummary', False),
        "shouldCommitChanges": metadata.get('shouldCommitChanges', True)
    }


def group_agents_by_workflow(agents_dir: Path) -> Dict[str, List[Path]]:
    """
    Group agent markdown files by workflow prefix.

    Example:
        audit-naive-phase-0.md  -> "audit-naive"
        audit-naive-phase-1.md  -> "audit-naive"
        coverage-phase-0.md     -> "coverage"

    Returns:
        {
            "audit-naive": [phase-0.md, phase-1.md, ...],
            "coverage": [phase-0.md, phase-1.md, ...]
        }
    """
    workflows = defaultdict(list)

    for md_file in sorted(agents_dir.glob("*.md")):
        # Extract workflow name (everything before -phase-)
        match = re.match(r'^(.+?)-phase-(\d+)\.md$', md_file.name)

        if match:
            workflow_name = match.group(1)
            phase_num = int(match.group(2))
            workflows[workflow_name].append((phase_num, md_file))
        else:
            print(f"  ⚠️  Skipping {md_file.name} (doesn't match *-phase-N.md pattern)")

    # Sort phases numerically
    for workflow_name in workflows:
        workflows[workflow_name].sort(key=lambda x: x[0])
        workflows[workflow_name] = [path for _, path in workflows[workflow_name]]

    return dict(workflows)


def generate_workflow_json(workflow_name: str, agent_files: List[Path]) -> dict:
    """
    Generate a complete workflow JSON from a list of agent markdown files.
    """
    # Convert display name
    display_name = workflow_name.replace('-', ' ').title()

    steps = []
    for agent_file in agent_files:
        try:
            step = markdown_to_step(agent_file)
            steps.append(step)
        except Exception as e:
            print(f"    ❌ Error processing {agent_file.name}: {e}")
            continue

    return {
        "name": f"{display_name} Workflow",
        "steps": steps
    }


def main():
    """Generate all workflow JSON files from agent markdown files."""

    # Parse arguments
    if len(sys.argv) < 2:
        print("Usage: python generate_workflows.py <agents_dir> [output_dir]")
        print("\nExample:")
        print("  python generate_workflows.py ../ai-agent-primers/agents ../ai-agent-primers/workflows")
        sys.exit(1)

    agents_dir = Path(sys.argv[1]).resolve()

    if len(sys.argv) >= 3:
        workflows_dir = Path(sys.argv[2]).resolve()
    else:
        # Default: create workflows/ in parent of agents_dir
        workflows_dir = agents_dir.parent / "workflows"

    # Validate agents directory
    if not agents_dir.exists():
        print(f"❌ Error: Agents directory not found: {agents_dir}")
        sys.exit(1)

    # Create workflows directory
    workflows_dir.mkdir(exist_ok=True)

    print(f"🔍 Scanning for agent files in: {agents_dir}")
    workflows = group_agents_by_workflow(agents_dir)

    if not workflows:
        print("❌ No workflow files found matching pattern *-phase-N.md")
        sys.exit(1)

    print(f"\n📋 Found {len(workflows)} workflows:\n")

    generated_count = 0
    for workflow_name, agent_files in workflows.items():
        print(f"  • {workflow_name}: {len(agent_files)} phases")

        # Generate workflow JSON
        workflow_json = generate_workflow_json(workflow_name, agent_files)

        if not workflow_json['steps']:
            print(f"    ⚠️  No valid steps, skipping")
            continue

        # Write to file
        output_file = workflows_dir / f"{workflow_name}.json"
        with open(output_file, 'w') as f:
            json.dump(workflow_json, f, indent=2)

        print(f"    ✓ Generated: {output_file.name} ({len(workflow_json['steps'])} steps)")
        generated_count += 1

    print(f"\n✅ Generated {generated_count} workflow files in: {workflows_dir}")
    print("\nUsage:")
    print(f"  cd /path/to/target/repo")
    print(f"  recon {workflows_dir}/audit-naive.json")


if __name__ == "__main__":
    main()
