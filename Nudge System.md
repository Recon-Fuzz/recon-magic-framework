# Nudge System

A mechanism for injecting additional context or guidance into workflow prompts without modifying individual workflow files.

## Problem

When starting a workflow, you may want to add an extra prompt/nudge that all agent calls should be mindful of. Without a centralized solution, you'd need to customize each workflow JSON file individually.

## Solution Options

### Option 1: Workflow-Level Nudge Field

Add a top-level `nudge` field to workflow JSON:

```json
{
  "name": "My Workflow",
  "nudge": "Always consider gas optimization and reentrancy in your analysis",
  "steps": [...]
}
```

The nudge gets injected at execution time in `core/task.py` before building the command.

### Option 2: Environment Variable

Set `RECON_WORKFLOW_NUDGE` at runtime:

```bash
RECON_WORKFLOW_NUDGE="Focus on edge cases" python main.py workflow.json
```

This requires zero changes to workflow files and can be set per-run.

## Implementation

The injection happens in `execute_task_step()` where prompts are already being processed (agent file loading, path resolution). Before building the command for AI steps (CLAUDE_CODE, OPENCODE), prepend/append the nudge:

```python
if workflow.nudge or os.environ.get('RECON_WORKFLOW_NUDGE'):
    nudge = workflow.nudge or os.environ.get('RECON_WORKFLOW_NUDGE')
    prompt = f"{step.prompt}\n\n---\nReminder: {nudge}"
```

Note: Only inject for AI model steps, not PROGRAM steps.

## Risk Considerations

Injecting a nudge changes the prompt structure, which can have unintended effects:

1. **Attention shift** - Model might over-index on the nudge and lose focus on the actual task
2. **Instruction conflict** - Step says "focus only on X" but nudge says "always consider Y"
3. **Output format disruption** - Steps expecting structured output could be derailed
4. **Signal dilution** - Carefully tuned agent prompts may lose specificity

## Mitigation Strategies

### 1. Opt-in/Opt-out Per Step

Add a `useNudge` field on each step. Default to true, but allow steps to opt out:

```json
{
  "name": "Step 1",
  "prompt": "...",
  "useNudge": false
}
```

### 2. Position at End

Put nudge at the end as a "reminder" rather than at the start as a "directive". Models weight early content more heavily. A trailing nudge is a softer constraint:

```
[actual task prompt]

---
Reminder: {nudge}
```

### 3. Semantic Framing

Frame the nudge as context, not instruction:

- Bad: "Always check for reentrancy"
- Better: "Context: This audit prioritizes reentrancy concerns"

### 4. A/B Testing

Run the same workflow with and without nudge, compare outputs. This is the only reliable way to measure impact.

### 5. Keep It Short

A 10-word nudge is safer than a 100-word one. The nudge should be a gentle steering, not a hard override.

## Summary

The nudge system provides a meta-solution for adding workflow-wide guidance without modifying individual step prompts. The key architectural insight is that prompts are already being transformed at execution time, so nudge injection fits naturally into that pattern. Use the opt-out mechanism for sensitive steps where the nudge might interfere.
