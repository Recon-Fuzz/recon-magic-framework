# V2 Architecture: Scout V2 | Setup V2

## Summary

Clean separation between **analysis** (Scout) and **implementation** (Setup).

```
┌─────────────────────────────────────────────────────────────────┐
│                    SCOUT V2 (Zero Coding)                       │
├─────────────────────────────────────────────────────────────────┤
│ Phase 0: Contract discovery + FULL/MOCK/ABSORB/DISCARD          │
│          → magic/deployment-classification.json                 │
│                                                                 │
│ Phase 1: Generate scaffolding spec                              │
│          → magic/contracts-to-scaffold.json                     │
│                                                                 │
│ Phase 2: Deep parameter analysis (coverage classes)             │
│          → magic/setup-config-spec.json                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   SETUP V2 (All Coding)                         │
├─────────────────────────────────────────────────────────────────┤
│ Phase 0: Migrate Hardhat → Foundry                              │
│          → foundry.toml, forge build                            │
│                                                                 │
│ Phase 1: Run recon-generate + create mocks                      │
│          → test/recon/*, mocks/*.sol                            │
│                                                                 │
│ Phase 2: Implement Setup.sol from spec                          │
│          → test/recon/Setup.sol                                 │
│                                                                 │
│ Phase 3: Validate (compile + echidna)                           │
│          → Echidna runs without setup crash                     │
│                                                                 │
│ [CLI] Extract target functions                                  │
│          → magic/target-functions.json                          │
│                                                                 │
│ Phase 5: Identify prerequisite functions (OPENCODE)             │
│          → magic/function-sequences.json                        │
│                                                                 │
│ [CLI] Order prerequisites                                       │
│          → magic/function-sequences-sorted.json                 │
│                                                                 │
│ Phase 6: Move admin functions (OPENCODE)                        │
│          → magic/testing-order.json                             │
│          → magic/admin-functions.json                           │
│          → AdminTargets.sol updated                             │
│                                                                 │
│ Phase 7: Write unit tests for all handlers                      │
│          → CryticToFoundry.sol tests                            │
│          → magic/reverting-handlers.json (if any)               │
│          → FUZZING_SETUP_COMPLETE.md                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      COVERAGE PHASE                             │
│                      (Unchanged)                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## V2 Files

### Scout V2 Prompts

| File | Purpose |
|------|---------|
| `scout-v2-phase-0.md` | Contract discovery + classification |
| `scout-v2-phase-1.md` | Generate scaffolding spec |
| `scout-v2-phase-2.md` | Deep parameter analysis |

### Setup V2 Prompts

| File | Purpose |
|------|---------|
| `setup-v2-phase-0.md` | Hardhat → Foundry migration |
| `setup-v2-phase-1.md` | Run recon-generate + create mocks |
| `setup-v2-phase-2.md` | Implement Setup.sol |
| `setup-v2-phase-3.md` | Validate (compile + echidna) |
| *(CLI step)* | `extract-target-functions` → target-functions.json |
| `setup-v2-phase-5.md` | Identify prerequisite functions |
| *(CLI step)* | `order-prerequisite-func` → function-sequences-sorted.json |
| `setup-v2-phase-6.md` | Move admin functions + generate testing order |
| `setup-v2-phase-7.md` | Write unit tests for all handlers |

---

## Output Files

### Scout V2 Outputs (in `magic/`)

| File | Producer | Consumer |
|------|----------|----------|
| `deployment-classification.json` | Scout Phase 0 | Scout Phase 1, 2 |
| `contracts-to-scaffold.json` | Scout Phase 1 | Setup Phase 1 (recon-generate) |
| `setup-config-spec.json` | Scout Phase 2 | Setup Phase 2 |

### Setup V2 Outputs

| File | Producer | Consumer |
|------|----------|----------|
| `test/recon/Setup.sol` | Phase 2 | All subsequent phases |
| `test/recon/targets/*.sol` | Phase 1 | Coverage |
| `test/recon/mocks/*.sol` | Phase 1 | Phase 2 |
| `magic/target-functions.json` | Phase 4 | Phase 5, Coverage |
| `magic/function-sequences.json` | Phase 5 | Phase 6, Coverage |
| `magic/function-sequences-sorted.json` | Phase 6 | Phase 7 |
| `magic/testing-order.json` | Phase 6 | Phase 7 |
| `magic/admin-functions.json` | Phase 6 | Reference |
| `magic/reverting-handlers.json` | Phase 7 | Reference |
| `magic/setup-notes.md` | Phase 3 | Reference |
| `FUZZING_SETUP_COMPLETE.md` | Phase 7 | Workflow gate |

---

## V1 to V2 Mapping

| V1 Step | V2 Step | Notes |
|---------|---------|-------|
| scouting-phase-0 (migration) | setup-v2-phase-0 | Moved to Setup |
| scouting-phase-1 (analysis) | scout-v2-phase-0 + 1 | Split into classification + scaffolding spec |
| recon-generate (CLI) | setup-v2-phase-1 | Moved to Setup |
| setup-phase-0a (analysis) | scout-v2-phase-2 | Moved to Scout |
| setup-phase-0b (implement) | setup-v2-phase-2 | Same |
| recon-generate link2 | setup-v2-phase-3 | In validation phase |
| extract-target-functions | setup-v2-phase-4 | Same |
| setup-phase-1 (prerequisites) | setup-v2-phase-5 | Same |
| order-prerequisite-func | setup-v2-phase-6 | Combined with admin functions |
| setup-phase-2 (admin) | setup-v2-phase-6 | Combined with ordering |
| setup-phase-3 (tests) | setup-v2-phase-7 | Same |

---

## Key Design Decisions

### 1. Scout Does Zero Coding
Scout phases only read source files and output JSON specs.

### 2. Setup Does All Coding
All file creation/modification happens in Setup phases.

### 3. recon-generate in Setup
Scaffolding runs in Setup Phase 1, not Scout.

### 4. Full Handler Validation
Setup Phase 7 writes unit tests proving every handler works.

### 5. function-sequences in Both Workflows
- Setup generates it for unit test writing (Phase 5)
- Coverage regenerates it for shortcut generation
- This allows each workflow to run independently

---

## Workflow Files

The workflow JSON files are in `/workflows/`:
- `workflow-fuzzing-scouting-v2.json` - Scout V2 workflow
- `workflow-fuzzing-setup-v2.json` - Setup V2 workflow

---

## Workflow Execution

### Manual Execution

```bash
# Scout V2
claude --prompt agent/scout-v2-phase-0.md
claude --prompt agent/scout-v2-phase-1.md
claude --prompt agent/scout-v2-phase-2.md

# Setup V2
claude --prompt agent/setup-v2-phase-0.md
claude --prompt agent/setup-v2-phase-1.md
claude --prompt agent/setup-v2-phase-2.md
claude --prompt agent/setup-v2-phase-3.md
claude --prompt agent/setup-v2-phase-4.md
claude --prompt agent/setup-v2-phase-5.md
claude --prompt agent/setup-v2-phase-6.md
claude --prompt agent/setup-v2-phase-7.md
```

### Framework Execution

**workflow-fuzzing-scouting-v2.json:**
```json
{
  "steps": [
    { "type": "opencode", "prompt": "agent/scout-v2-phase-0.md" },
    { "type": "decision", "mode": "FILE_EXISTS", "file": "magic/deployment-classification.json" },
    { "type": "opencode", "prompt": "agent/scout-v2-phase-1.md" },
    { "type": "decision", "mode": "FILE_EXISTS", "file": "magic/contracts-to-scaffold.json" },
    { "type": "opencode", "prompt": "agent/scout-v2-phase-2.md" }
  ]
}
```

**workflow-fuzzing-setup-v2.json:**
```json
{
  "steps": [
    { "type": "opencode", "prompt": "agent/setup-v2-phase-0.md" },
    { "type": "opencode", "prompt": "agent/setup-v2-phase-1.md" },
    { "type": "opencode", "prompt": "agent/setup-v2-phase-2.md" },
    { "type": "opencode", "prompt": "agent/setup-v2-phase-3.md" },
    { "type": "program", "prompt": "extract-target-functions --return-json", "output": "magic/target-functions.json" },
    { "type": "opencode", "prompt": "agent/setup-v2-phase-5.md" },
    { "type": "program", "prompt": "order-prerequisite-func ./magic/function-sequences.json --return-json", "output": "magic/function-sequences-sorted.json" },
    { "type": "opencode", "prompt": "agent/setup-v2-phase-6.md" },
    { "type": "opencode", "prompt": "agent/setup-v2-phase-7.md" }
  ]
}
```

---

## Testing Checklist

### Scout V2
- [ ] Phase 0: Produces valid `deployment-classification.json`
- [ ] Phase 1: Produces valid `contracts-to-scaffold.json`
- [ ] Phase 2: Produces valid `setup-config-spec.json`

### Setup V2
- [ ] Phase 0: Foundry compiles
- [ ] Phase 1: recon-generate runs, mocks created
- [ ] Phase 2: Setup.sol compiles
- [ ] Phase 3: Echidna runs without crash
- [ ] Phase 4: `target-functions.json` extracted
- [ ] Phase 5: `function-sequences.json` created
- [ ] Phase 6: Admin functions moved, testing order created
- [ ] Phase 7: All unit tests pass

---

## Files to Archive (Old Architecture)

```
agent/scouting-phase-0.md        → Replaced by setup-v2-phase-0.md
agent/scouting-phase-1.md        → Replaced by scout-v2-phase-0.md + 1.md
agent/scouting-alternative.MD    → Merged into scout-v2-phase-0.md
agent/scouting-alternative-2.MD  → Merged into scout-v2-phase-2.md
agent/setup-phase-0.md           → Split across setup-v2 phases
agent/setup-phase-0a.md          → Replaced by scout-v2-phase-2.md
agent/setup-phase-0b.md          → Replaced by setup-v2-phase-2.md
agent/setup-phase-1.md           → Replaced by setup-v2-phase-5.md
agent/setup-phase-2.md           → Replaced by setup-v2-phase-6.md
agent/setup-phase-3.md           → Replaced by setup-v2-phase-7.md
Deployment Decision.MD           → Merged into scout-v2-phase-0.md
```
