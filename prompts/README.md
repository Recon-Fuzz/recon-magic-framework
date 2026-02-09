# Prompts

Agent prompts and reference documents used by the Recon Magic Framework to guide AI agents through fuzzing, coverage, auditing, and property specification workflows.

## Structure

```
prompts/
├── agent/              # Agent definitions (injected into AI prompts by the framework)
├── templates/          # Templates copied into target repos (e.g., scope.md)
├── styleguide.md       # Echidna configuration and fix patterns
├── clamping-handler-rules.md  # Rules for implementing clamped handlers
├── invariant-workshop.md      # Property specification guide
├── objective-coverage.md      # Coverage analysis tools and techniques
└── audit-template.md          # Bug report template
```

## Usage

### With the Framework

When running through `cli.py`, `worker.py`, or `main.py`, the framework automatically sets the `PROMPTS_DIR` environment variable pointing to this directory. Agent prompts reference documents using `${PROMPTS_DIR}/styleguide.md`, etc., and the AI resolves the path at runtime.

No setup required — it just works.

### Local Testing (without the Framework)

To use these prompts directly with Claude Code outside the framework:

```bash
# Set PROMPTS_DIR to wherever this directory lives
export PROMPTS_DIR=/path/to/recon-magic-framework/prompts

# Run Claude Code with a prompt that references an agent
claude -p "$(cat $PROMPTS_DIR/agent/setup-v2-phase-3.md)"
```

The `${PROMPTS_DIR}` variable in the prompts will resolve correctly as long as the env var is set before invoking the AI.

## Reference Documents

Agent prompts tell the AI to read these files for domain-specific guidance:

| Document | Used By | Purpose |
|----------|---------|---------|
| `styleguide.md` | setup-v2-phase-3, fix-echidna-failures, coverage | Echidna config patterns and common fixes |
| `clamping-handler-rules.md` | coverage-phase-1 through -5, coverage | Rules for writing clamped fuzzer handlers |
| `invariant-workshop.md` | properties-phase-1, -2, -3 | Guide for specifying invariant properties |
| `objective-coverage.md` | coverage-phase-3, -4, -5 | Coverage analysis tools and techniques |
| `audit-template.md` | audit-naive-phase-1 through -5 | Template for bug reports |
