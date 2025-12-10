# Fuzzing Setup Workflow - Input/Output Specification

## Step 1: Phase 0a - Analyze Setup Decisions

**Type:** Task (OPENCODE - Agent)

**Inputs:**
- Agent: `./.opencode/agent/setup-phase-0a.md`
- Files: `test/recon/Setup.sol`, `test/recon/TargetFunctions.sol`, `test/recon/targets/*.sol`, `src/**/*.sol`

**Outputs:**
- File: `magic/setup-decisions.json`

**Output JSON Structure:**
```json
{
  "version": "2.0.0",
  "architecture_reasoning": {
    "pattern_identified": "Description of architecture pattern",
    "complexity_choice": "moderate",
    "instance_counts": {
      "description": "What to deploy in setup vs via helper functions",
      "choices": [
        {
          "contract": "ContractName",
          "deploy_in_setup": 1,
          "has_helper_deploy": true,
          "config_variations": ["different fees", "different caps"],
          "audit_reason": "@audit Specific reasoning"
        }
      ]
    },
    "scenarios_covered": ["scenario1"],
    "scenarios_NOT_covered": ["scenario2 - reason"],
    "trade_off_summary": "Summary of trade-offs"
  },
  "decisions": {
    "dynamic_deployments": [
      {
        "name": "plural_name",
        "contract": "ContractName",
        "deploy_in_setup": 1,
        "helper_function": "helper_deployThing(uint256 fee, uint256 cap)",
        "helper_params": ["fee", "cap"],
        "needs_registration": true,
        "registration_call": "parent.registerThing(address)",
        "reason": "Why fuzzer should control deployment"
      }
    ],
    "custom_mocks_needed": [{"name": "dependency_name", "mock_contract": "MockContractName", "reason": "Why standard mock won't work"}],
    "tokens": [{"name": "token_var_name", "role": "role_in_system", "use_asset_manager": true, "custom_mock": null, "reason": "Why this token is needed"}],
    "time_sensitive": {"needs_warp": true, "reason": "Why time manipulation is needed"},
    "multi_user": {"additional_actors_count": 1, "needs_private_key": false, "reason": "Why additional actors are needed"},
    "proxy_deployment": {"needs_proxy": true, "deploy_method": "governance.deployUserProxy()", "proxy_variable": "userProxy", "reason": "Users must stake through their proxy contract"},
    "struct_params": [{"struct_type": "StructTypeName", "variable_name": "variableName", "mode": "single", "reason": "All functions operate on the same configuration"}],
    "post_deploy_actions": ["register_initial_thing", "set_initial_approvals"]
  },
  "helper_functions_needed": [{"type": "dynamic_getter", "name": "_getDeployedThing", "reason": "For dynamic deployments"}],
  "audit_notes": ["@audit chose moderate setup because reasoning", "@audit NOT TESTING: scenario because why"]
}
```

---

## Step 2: Validate Decisions File

**Type:** Decision (FILE_EXISTS)

**Inputs:**
- Pattern: `magic/setup-decisions.json`

**Decision Logic:**
- If file exists (value = 1): Continue to Step 3
- If file does not exist (value = 0): Jump to Step 1

---

## Step 3: Phase 0b - Implement Setup.sol

**Type:** Task (OPENCODE - Agent)

**Inputs:**
- Agent: `./.opencode/agent/setup-phase-0b.md`
- File: `magic/setup-decisions.json`

**Outputs:**
- File: `test/recon/Setup.sol` (modified/implemented)

---

## Step 4: Phase 1 - Run Echidna

**Type:** Task (PROGRAM)

**Inputs:**
- Files: Implemented Setup.sol and test contracts
- Config: `echidna.yaml`

**Command:**
```bash
echidna . --contract CryticTester --config echidna.yaml --format text --test-limit 50000 --disable-slither --test-mode exploration
```

**Outputs:**
- Directory: `echidna/`

---

## Step 5: Phase 1.5 - Save Echidna Logs

**Type:** Task (PROGRAM)

**Inputs:**
- Directory: `echidna/`

**Command:**
```bash
mkdir -p magic/logs && (find . -name '*.txt' -path '*/echidna/*' -exec cp {} magic/logs/ \; 2>/dev/null || true) && echo 'Echidna logs saved (if any exist)'
```

**Outputs:**
- Directory: `magic/logs/`

---

## Step 6: Echidna Output Check

**Type:** Decision (FILE_EXISTS)

**Inputs:**
- Pattern: `echidna/*.txt`

**Decision Logic:**
- If files exist (value = 1): Jump to Step 9
- If files do not exist (value = 0): Continue to Step 7

---

## Step 7: Fix Echidna Failure

**Type:** Task (OPENCODE - Agent)

**Inputs:**
- Agent: `./.opencode/agent/fix-echidna-failures.md`
- Directory: `magic/logs/`

**Outputs:**
- Modified Setup.sol and/or test contracts
- File: `magic/fix-echidna-running.md`

---

## Step 8: Retry Echidna After Fix

**Type:** Decision (FILE_EXISTS)

**Inputs:**
- Pattern: `magic/fix-echidna-running.md`

**Decision Logic:**
- If file exists (value = 1): Jump to Step 4
- If file does not exist (value = 0): Jump to Step 4

---

## Step 9: Phase 2 - Extract Target Functions

**Type:** Task (PROGRAM)

**Inputs:**
- Directory: Automatically finds `recon/` directory

**Command:**
```bash
extract-target-functions --return-json
```

**Outputs:**
- File: `magic/target-functions.json`

**Output JSON Structure:**
```json
[
  {
    "contract": "ContractName",
    "target_functions": ["functionName1", "functionName2"]
  }
]
```

**When using `--return-json` flag:**
```json
{
  "data": [{"contract": "ContractName", "target_functions": ["functionName1"]}],
  "summary": {"total_contracts": 1, "total_unique_functions": 1}
}
```

---

## Step 10: Phase 3 - Order Prerequisite Functions

**Type:** Task (PROGRAM)

**Inputs:**
- File: `magic/testing-priority.json`

**Command:**
```bash
order-prerequisite-func ./magic/testing-priority.json --return-json
```

**Outputs:**
- File: `magic/testing-priority.json` (modified in-place)

**Output JSON Structure:**
```json
{
  "1": {"function_name": "functionWithNoPrereqs", "prerequisite_functions": []},
  "2": {"function_name": "functionWithOnePrereq", "prerequisite_functions": ["functionWithNoPrereqs"]}
}
```

**When using `--return-json` flag:**
```json
{
  "data": {"1": {"function_name": "functionWithNoPrereqs", "prerequisite_functions": []}},
  "summary": {"total_functions": 1, "file_path": "magic/testing-priority.json"}
}
```

---

## Step 11: Phase 1 Agent - Setup Phase 1

**Type:** Task (OPENCODE - Agent)

**Inputs:**
- Agent: `./.opencode/agent/setup-phase-1.md`
- Files: `magic/target-functions.json`, `magic/testing-priority.json`

**Outputs:**
- Contract scaffolding and target function infrastructure

---

## Step 12: Phase 2 Agent - Setup Phase 2

**Type:** Task (OPENCODE - Agent)

**Inputs:**
- Agent: `./.opencode/agent/setup-phase-2.md`

**Outputs:**
- Modified Setup.sol with deployment and configuration logic

---

## Step 13: Phase 3 Agent - Setup Phase 3

**Type:** Task (OPENCODE - Agent)

**Inputs:**
- Agent: `./.opencode/agent/setup-phase-3.md`

**Outputs:**
- Final adjustments to fuzzing infrastructure

---

## Step 14: Workflow Completion Summary

**Type:** Task (OPENCODE - Agent)

**Inputs:**
- All artifacts created during workflow

**Outputs:**
- File: `FUZZING_SETUP_COMPLETE.md`
