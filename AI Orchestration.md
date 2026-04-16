# AI Orchestration: Dynamic Workflows with Safety Constraints

## Overview

This document explores how to combine two powerful concepts:
1. **Foundry Root Discovery** - AI-assisted detection of repo structure
2. **On-the-fly Workflow Generation** - AI modifying workflows at runtime

The key insight: **AI should fill slots, not write raw commands** - similar to SQL prepared statements preventing injection.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    META-WORKFLOW (Phase 0)                   │
│  ┌─────────────────┐    ┌─────────────────┐                  │
│  │ Detect Context  │───▶│ Rewrite/Adapt   │                  │
│  │ (foundry root,  │    │ Workflow for    │                  │
│  │  repo structure)│    │ This Repo       │                  │
│  └─────────────────┘    └────────┬────────┘                  │
└──────────────────────────────────┼───────────────────────────┘
                                   ▼
┌──────────────────────────────────────────────────────────────┐
│                    ACTUAL WORKFLOW (Phase 1+)                │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐                   │
│  │ Step 0  │───▶│ Step 1  │───▶│ Step N  │ (can self-modify) │
│  └─────────┘    └─────────┘    └─────────┘                   │
└──────────────────────────────────────────────────────────────┘
```

---

## Core Concepts

### 1. Parameterized Workflows (Prepared Statements)

Instead of AI writing arbitrary commands:

```python
# BAD: AI has full control
workflow['steps'][5]['prompt'] = ai_generated_string  # Anything goes

# GOOD: Prepared statement with slots
ALLOWED_TEMPLATES = {
    'foundry_command': "cd {foundry_root} && {command}",
    'echidna_run': "echidna {foundry_root} --contract {contract} --config {config}",
}
```

### 2. Workflow File With Slots

```json
{
  "name": "Fuzzing Coverage Workflow",
  "params": {
    "foundry_root": { "detect": "foundry.toml", "required": true },
    "contract_name": { "default": "CryticTester" },
    "echidna_timeout": { "default": "1800", "type": "integer" }
  },
  "steps": [
    {
      "name": "Step 0: Build with Forge",
      "type": "task",
      "prompt": "cd ${foundry_root} && forge build",
      "model": { "type": "PROGRAM" },
      "locked": true
    },
    {
      "name": "Step 9: Run Echidna",
      "type": "task",
      "prompt": "cd ${foundry_root} && echidna . --contract ${contract_name} --timeout ${echidna_timeout}",
      "model": { "type": "PROGRAM" },
      "modifiable": ["echidna_timeout"]
    }
  ]
}
```

---

## Safety Model: Three Layers

### Layer 1: Immutable Skeleton

```
┌─────────────────────────────────────────────────────────────┐
│ IMMUTABLE SKELETON                                          │
│ - Step types (task, decision) cannot change                 │
│ - Model types are fixed per step                            │
│ - Safety-critical fields locked                             │
└─────────────────────────────────────────────────────────────┘
```

### Layer 2: Parameterized Slots

```
┌─────────────────────────────────────────────────────────────┐
│ PARAMETERIZED SLOTS                                         │
│ - AI can fill in {foundry_root}, {contract_name}            │
│ - Values validated against schema/whitelist                 │
│ - Path traversal blocked (no ../, absolute paths)           │
└─────────────────────────────────────────────────────────────┘
```

### Layer 3: Constrained Step Insertion

```
┌─────────────────────────────────────────────────────────────┐
│ CONSTRAINED STEP INSERTION                                  │
│ - AI can add steps, but only from approved templates        │
│ - Can't invent arbitrary PROGRAM commands                   │
│ - New steps inherit safety constraints                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation

### WorkflowTemplate Class

```python
class WorkflowTemplate:
    """A workflow with parameterized slots that AI can fill"""

    SAFE_PARAM_PATTERNS = {
        'foundry_root': r'^[a-zA-Z0-9_\-/]+$',  # No .., no absolute
        'contract_name': r'^[A-Z][a-zA-Z0-9]+$',  # PascalCase
        'timeout': r'^\d{1,5}$',  # 1-99999
    }

    def __init__(self, workflow_json):
        self.skeleton = workflow_json
        self.params = {}
        self.locked_fields = ['type', 'model', 'allowFailure']

    def bind_param(self, name, value):
        """Safely bind a parameter value"""
        if name not in self.SAFE_PARAM_PATTERNS:
            raise UnknownParameterError(name)

        pattern = self.SAFE_PARAM_PATTERNS[name]
        if not re.match(pattern, str(value)):
            raise UnsafeParameterError(f"{name}={value} doesn't match {pattern}")

        # Block path traversal
        if '..' in str(value) or value.startswith('/'):
            raise PathTraversalError(value)

        self.params[name] = value

    def render(self):
        """Produce the final workflow with all params substituted"""
        rendered = json.dumps(self.skeleton)
        for name, value in self.params.items():
            rendered = rendered.replace(f"${{{name}}}", value)

        # Verify no unbound params remain
        if '${' in rendered:
            unbound = re.findall(r'\$\{(\w+)\}', rendered)
            raise UnboundParameterError(unbound)

        return json.loads(rendered)
```

### Phase 0 Orchestrator

```python
class Phase0Orchestrator:
    """Runs before main workflow to detect context and bind params"""

    def __init__(self, repo_path):
        self.repo_path = repo_path
        self.config = {}

    def detect_foundry_root(self):
        """Deterministic detection first"""
        foundry_files = []
        for root, dirs, files in os.walk(self.repo_path):
            # Skip node_modules, .git, etc
            dirs[:] = [d for d in dirs if d not in ['.git', 'node_modules', 'lib']]
            if 'foundry.toml' in files:
                foundry_files.append(os.path.relpath(root, self.repo_path))

        if len(foundry_files) == 1:
            return foundry_files[0]
        elif len(foundry_files) == 0:
            return None  # Trigger AI fallback
        else:
            return foundry_files  # Ambiguous, AI decides

    async def run(self, workflow_template: WorkflowTemplate):
        """Phase 0: Detect and bind all params before workflow runs"""

        # 1. Deterministic detection
        foundry_root = self.detect_foundry_root()

        # 2. AI fallback if needed
        if foundry_root is None:
            foundry_root = await self.ai_find_foundry_root()
        elif isinstance(foundry_root, list):
            foundry_root = await self.ai_choose_foundry_root(foundry_root)

        # 3. Bind to template (validates!)
        workflow_template.bind_param('foundry_root', foundry_root)

        # 4. Cache for future steps
        self.config['foundry_root'] = foundry_root
        with open(f'{self.repo_path}/.recon-config.json', 'w') as f:
            json.dump(self.config, f)

        # 5. Set env var for PROGRAM steps
        os.environ['RECON_FOUNDRY_ROOT'] = foundry_root

        return workflow_template.render()
```

---

## Dynamic Workflow Execution

### Runtime Modification Loop

```python
async def run_dynamic_workflow(initial_workflow_path, job_id):
    loop_detector = LoopDetector(max_visits=3)
    current_step = 0

    while True:
        # FRESH READ every iteration
        workflow = load_workflow(initial_workflow_path)
        validate_workflow_schema(workflow)

        if current_step >= len(workflow['steps']):
            break  # Done

        step = workflow['steps'][current_step]
        loop_detector.record_visit(step['name'])

        # Execute step
        result = await execute_step(step)

        # If AI step, check if workflow was modified
        if step['model']['type'] in ['CLAUDE_CODE', 'OPENCODE']:
            new_workflow = load_workflow(initial_workflow_path)
            if new_workflow != workflow:
                validate_workflow_modification(workflow, new_workflow, current_step)
                log_workflow_modification(job_id, current_step,
                    hash_workflow(workflow), hash_workflow(new_workflow))
                sync_workflow_state(new_workflow, current_step)

        current_step += 1
```

### Safety Validators

```python
def validate_workflow_modification(old_workflow, new_workflow, current_step_index):
    """Steps 0 to current_step_index must be identical"""
    for i in range(current_step_index + 1):
        if old_workflow['steps'][i] != new_workflow['steps'][i]:
            raise WorkflowTamperingError(f"Cannot modify already-executed step {i}")

MAX_TOTAL_STEPS = 50
MAX_STEPS_PER_MODIFICATION = 10

def validate_step_growth(old_count, new_count):
    if new_count > MAX_TOTAL_STEPS:
        raise WorkflowLimitError(f"Workflow exceeds {MAX_TOTAL_STEPS} steps")
    if new_count - old_count > MAX_STEPS_PER_MODIFICATION:
        raise WorkflowLimitError("Too many steps added in single modification")

class LoopDetector:
    def __init__(self, max_visits=3):
        self.step_visits = defaultdict(int)
        self.max_visits = max_visits

    def record_visit(self, step_name):
        self.step_visits[step_name] += 1
        if self.step_visits[step_name] > self.max_visits:
            raise InfiniteLoopError(f"Step '{step_name}' visited {self.max_visits}+ times")
```

---

## Step Template Library

AI can only insert steps from approved templates:

```python
STEP_TEMPLATES = {
    'forge_build': {
        'type': 'task',
        'prompt': 'cd ${foundry_root} && forge build',
        'model': {'type': 'PROGRAM'},
    },
    'forge_test': {
        'type': 'task',
        'prompt': 'cd ${foundry_root} && forge test',
        'model': {'type': 'PROGRAM'},
    },
    'echidna_run': {
        'type': 'task',
        'prompt': 'cd ${foundry_root} && echidna . --contract ${contract_name} --config ${echidna_config} --timeout ${echidna_timeout}',
        'model': {'type': 'PROGRAM'},
        'allowFailure': True,
    },
    'ai_analysis': {
        'type': 'task',
        'prompt': '${analysis_prompt}',
        'model': {'type': 'OPENCODE'},
    },
    'coverage_eval': {
        'type': 'task',
        'prompt': 'covg-eval magic/ echidna/ --return-json',
        'model': {'type': 'PROGRAM'},
    },
}

def ai_can_insert_step(step_template_name, params, after_step_index):
    if step_template_name not in STEP_TEMPLATES:
        raise UnknownTemplateError(step_template_name)

    template = copy.deepcopy(STEP_TEMPLATES[step_template_name])
    # Bind and validate params against template
    # Return hydrated step
```

---

## Modification Permissions Matrix

| Field | Modifiable? | Constraint |
|-------|-------------|------------|
| `step.prompt` | Only params in `${}` | Must use templates |
| `step.type` | No | Locked |
| `step.model.type` | No | Locked |
| Add new steps | Yes | From template library only |
| `step.description` | Yes | Free text, no execution |
| `params.*` | Yes | Validated against patterns |
| Executed steps | No | Immutable history |

---

## Real-Time Visibility

### Option A: Git-based State Sync

```python
def sync_workflow_state(workflow, current_step):
    state = {
        'workflow': workflow,
        'current_step': current_step,
        'last_updated': datetime.utcnow().isoformat()
    }
    with open('magic/workflow-state.json', 'w') as f:
        json.dump(state, f, indent=2)

    subprocess.run(['git', 'add', 'magic/workflow-state.json'])
    subprocess.run(['git', 'commit', '-m', f'Workflow state: step {current_step}'])
    subprocess.run(['git', 'push'])
```

### Option B: Server Webhook

```python
async def notify_workflow_update(job_id, workflow, current_step):
    await http_client.post(f'{API_URL}/jobs/{job_id}/workflow-update', json={
        'workflow': workflow,
        'current_step': current_step,
        'timestamp': datetime.utcnow().isoformat()
    })
```

### Modification Audit Trail

```python
def log_workflow_modification(job_id, step_index, old_hash, new_hash, diff):
    modification = {
        'timestamp': datetime.utcnow().isoformat(),
        'job_id': job_id,
        'modified_at_step': step_index,
        'old_workflow_hash': old_hash,
        'new_workflow_hash': new_hash,
        'steps_added': diff['added'],
        'steps_modified': diff['modified']
    }
    # Write to magic/workflow-history.json
    # Upload to server
```

---

## Risk Mitigations

| Risk | Mitigation |
|------|------------|
| AI generates infinite steps | Hard cap (50 steps) |
| AI creates loop via JUMP_TO_STEP | Loop detector + max visits |
| Malformed JSON breaks execution | Schema validation before accept |
| AI removes safety checks | Immutable history guard |
| Runaway token costs | Step limit + execution time cap |
| Path traversal attacks | Regex validation, block `..` and absolute paths |
| Arbitrary command injection | Prepared templates only |

---

## Summary

The combination of **Phase 0 detection** + **parameterized workflows** + **constrained runtime modification** gives us:

1. **Flexibility**: AI can adapt workflows to repo structure
2. **Safety**: Prepared statements prevent injection attacks
3. **Visibility**: Real-time state sync to git/server
4. **Auditability**: Full modification history
5. **Bounds**: Hard limits on steps, loops, and modifications

The key principle: **AI fills slots, doesn't write raw commands**.
