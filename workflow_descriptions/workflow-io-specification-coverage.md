# Fuzzing Coverage Workflow - Input/Output Specification

## Step 0: Build with Forge

**Type:** Task (PROGRAM)

**Inputs:**
- Source: Solidity contracts in the project

**Command:**
```bash
forge build
```

**Outputs:**
- Compiled contracts in `out/` directory

---

## Step 1: Extract Target Functions

**Type:** Task (PROGRAM)

**Inputs:**
- Directory: `test/recon` (fuzzing suite directory)

**Command:**
```bash
extract-target-functions --targets test/recon --return-json
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

## Step 2: Build Artifacts

**Type:** Task (PROGRAM)

**Inputs:**
- Source: Solidity contracts in the project

**Command:**
```bash
forge clean && forge build --build-info --skip */test/** */tests/** */script/** */scripts/** */contracts/test/**
```

**Outputs:**
- Directory: `out/build-info/`

---

## Step 3: Filter Build Artifacts

**Type:** Task (PROGRAM)

**Inputs:**
- File: First non-filtered JSON file in `out/build-info` directory

**Command:**
```bash
filter-build-info $(find out/build-info -name '*.json' -not -name '*.filtered.json' | head -1)
```

**Outputs:**
- File: `out/build-info/*.filtered.json`

---

## Step 4: Extract Context with sol-expand

**Type:** Task (PROGRAM)

**Inputs:**
- File: Filtered JSON file in `out/build-info` directory

**Command:**
```bash
npx -y sol-context@latest
```

**Outputs:**
- Directory: `context_output/`

---

## Step 5: Identifying Meaningful Values

**Type:** Task (OPENCODE - Agent)

**Inputs:**
- Agent: `./.opencode/agent/coverage-phase-0.md`

**Outputs:**
- Identified meaningful values for clamping handlers

---

## Step 6: Creating Clamped Handlers

**Type:** Task (OPENCODE - Agent)

**Inputs:**
- Agent: `./.opencode/agent/coverage-phase-1.md`

**Outputs:**
- Modified or new handler functions in test contracts

---

## Step 7: Generate Non-Reverting Paths

**Type:** Task (PROGRAM)

**Inputs:**
- Files: Source contracts and build artifacts
- File: `magic/target-functions.json`

**Command:**
```bash
npx -y recon-generate@latest paths && mkdir -p magic && mv recon-paths.json magic/
```

**Outputs:**
- File: `magic/recon-paths.json`

**Output JSON Structure:**
```json
{
  "vault_liquidate": [
    "seizedAssets > 0 && position[id][borrower].collateral == 0 && data.length > 0 && marketParams.oracle.price() && marketParams.collateralToken.safeTransfer(msg.sender, seizedAssets)",
    "seizedAssets > 0 && position[id][borrower].collateral != 0 && data.length == 0 && marketParams.oracle.price()"
  ],
  "vault_borrow": [
    "assets > 0 && position[id][onBehalf].collateral > 0 && market[id].totalSupplyAssets > 0"
  ]
}
```

**Description:**
This tool extracts non-reverting execution paths through target functions. Each path is a boolean expression joined by `&&` representing conditions that must be satisfied for that execution flow. These paths are later combined with prerequisite functions to create shortcut handlers.

---

## Step 8: Identifying Function Call Sequences

**Type:** Task (OPENCODE - Agent)

**Inputs:**
- Agent: `./.opencode/agent/setup-phase-1.md`

**Outputs:**
- File: `magic/function-sequences.json`

**Output JSON Structure:**
```json
{
  "vault_liquidate": {
    "prerequisite_functions": [
      "vault_supply",
      "vault_supplyCollateral",
      "vault_borrow",
      "oracle_setPrice"
    ]
  },
  "vault_borrow": {
    "prerequisite_functions": [
      "vault_supply",
      "vault_supplyCollateral"
    ]
  }
}
```

**Description:**
This step identifies the necessary call sequences for target functions. It analyzes the implementation contracts to determine which functions must be called before others to avoid reverts. For example, if a `borrow` function requires a user to have deposited collateral first, the `deposit` function would be listed as a prerequisite.

The agent also identifies **implicit prerequisites** - state changes needed to satisfy execution conditions. For example, `liquidate` requires an unhealthy position, which may require calling `oracle_setPrice` to change the collateral price.

**Important Notes:**
- Does NOT include initialization functions
- Does NOT include role management functions (e.g., `grantRole`, `revokeRole`)
- Does NOT include basic admin configuration functions
- DOES include runtime prerequisite functions necessary for successful execution
- DOES include implicit prerequisites (e.g., oracle price changes, state modifications)

---

## Step 9: Merge Paths and Prerequisites

**Type:** Task (PROGRAM)

**Inputs:**
- File: `magic/recon-paths.json` (from Step 7)
- File: `magic/function-sequences.json` (from Step 8)

**Command:**
```bash
merge-paths-prerequisites --return-json
```

**Outputs:**
- File: `magic/merged-paths-prerequisites.json`

**Output JSON Structure:**
```json
{
  "vault_liquidate": {
    "prerequisite_functions": [
      "vault_supply",
      "vault_supplyCollateral",
      "vault_borrow",
      "oracle_setPrice"
    ],
    "paths": [
      "seizedAssets > 0 && position[id][borrower].collateral == 0 && data.length > 0 && marketParams.oracle.price()",
      "seizedAssets > 0 && position[id][borrower].collateral != 0 && data.length == 0"
    ]
  },
  "vault_borrow": {
    "prerequisite_functions": [
      "vault_supply",
      "vault_supplyCollateral"
    ],
    "paths": [
      "assets > 0 && position[id][onBehalf].collateral > 0 && market[id].totalSupplyAssets > 0"
    ]
  }
}
```

**Description:**
This tool merges the paths and prerequisites into a unified structure for each target function. Each entry contains:
- `prerequisite_functions`: Array of handler functions that must be called before the target
- `paths`: Array of execution path conditions (from recon-generate paths)

This merged structure is used by the coverage-phase-2 agent to create shortcut handlers that combine prerequisites with specific path conditions.

---

## Step 10: Creating Shortcut Handlers

**Type:** Task (OPENCODE - Agent)

**Inputs:**
- Agent: `./.opencode/agent/coverage-phase-2.md`
- File: `magic/merged-paths-prerequisites.json`

**Outputs:**
- Modified or new shortcut handler functions in test contracts

**Description:**
This agent implements shortcut functions that help the fuzzer reach full path coverage by:
1. Calling all prerequisite functions (using clamped handlers)
2. Reading exact values from system state to satisfy path conditions
3. Calling the target function with parameters that trigger specific execution paths

Each path in the merged data structure results in one shortcut function with a descriptive name based on the path conditions (e.g., `shortcut_liquidate_bySeizedAssets_badDebt_withCallback`).

---

## Step 11: Run Echidna Programmatically

**Type:** Task (PROGRAM)

**Inputs:**
- Files: All test contracts with handlers
- Config: `echidna.yaml`

**Command:**
```bash
echidna . --contract CryticTester --config echidna.yaml --format text --timeout 1800 --test-limit 99999999999999999999 --disable-slither --test-mode exploration
```

**Outputs:**
- Directory: `echidna/`

---

## Step 12: Echidna Output Check

**Type:** Decision (FILE_EXISTS)

**Inputs:**
- Pattern: `echidna/*.txt`

**Decision Logic:**
- If file does not exist (value = 0): STOP workflow (Echidna failed)
- If file exists (value = 1): Continue to Step 13

---

## Step 13: Generate Functions to Cover

**Type:** Task (PROGRAM)

**Inputs:**
- Directory: `echidna/` (containing LCOV files)
- Files: Source contracts and build artifacts

**Command:**
```bash
npx -y recon-generate@latest coverage && mkdir -p magic && mv recon-coverage.json magic/
```

**Outputs:**
- File: `magic/recon-coverage.json`

**Output JSON Structure:**
```json
{
  "src/hub/Hub.sol": ["66-130", "133-173", "176-185"],
  "src/hub/libraries/AssetLogic.sol": ["26-31", "42-47"]
}
```

**Description:**
This tool generates a JSON file containing line ranges per source file that need coverage analysis. The line ranges represent code sections that should be analyzed for function coverage.

---

## Step 14: Evaluate Coverage

**Type:** Task (PROGRAM)

**Inputs:**
- File: `magic/recon-coverage.json` (line ranges per source file)
- Directory: `echidna/` (containing LCOV files)

**Command:**
```bash
covg-eval magic/ echidna/ --return-json
```

**Outputs:**
- File: `magic/functions-missing-covg-{timestamp}.json`

**Output JSON Structure:**
```json
{
  "timestamp": "1733845200",
  "lcov_file": "echidna/covered.1733845200.lcov",
  "missing_coverage": [
    {
      "function": "functionName",
      "contract": "ContractName",
      "source_file": "src/ContractName.sol",
      "function_range": {"start": 235, "end": 260},
      "uncovered_code": [
        {
          "line_range": "244-247",
          "code": [
            "244: require(UtilsLib.exactlyOneZero(assets, shares))",
            "245: require(receiver != address(0))",
            "247: require(_isSenderAuthorized(onBehalf))"
          ]
        },
        {
          "line_range": "249",
          "code": [
            "249: _accrueInterest(marketParams, id)"
          ]
        }
      ]
    }
  ],
  "summary": {
    "total_functions": 15,
    "functions_missing_coverage": 2,
    "total_uncovered_chunks": 3
  }
}
```

**Description:**
This tool parses the `recon-coverage.json` line ranges, identifies which functions fall within those ranges by analyzing source files, then evaluates LCOV coverage data to determine which functions have missing coverage. Only functions with < 100% coverage are included in the output.

---

## Step 15: Initial Check of Coverage

**Type:** Decision (FILE_EXISTS)

**Inputs:**
- Pattern: `magic/functions-missing-covg-*.json`

**Decision Logic:**
- If file exists (value = 1): Jump to Step 16 (Analyzing Coverage Gaps)
- If file does not exist (value = 0): Jump to Step 22 (Workflow Complete)

---

## Step 16: Analyzing Coverage Gaps

**Type:** Task (OPENCODE - Agent)

**Inputs:**
- Agent: `./.opencode/agent/coverage-phase-3.md`
- File: `magic/functions-missing-covg-{timestamp}.json`

**Outputs:**
- Modified: `magic/functions-missing-covg-{timestamp}.json` with added `"analysis"` field

**Output Structure:**
Each entry in the `missing_coverage` array will have a new `"analysis"` field added:

```json
{
  "timestamp": "1733845200",
  "lcov_file": "echidna/covered.1733845200.lcov",
  "missing_coverage": [
    {
      "function": "borrow",
      "contract": "Morpho",
      "source_file": "src/Morpho.sol",
      "function_range": {"start": 235, "end": 260},
      "uncovered_code": [
        {
          "line_range": "244-247",
          "code": [
            "244: require(UtilsLib.exactlyOneZero(assets, shares))",
            "245: require(receiver != address(0))",
            "247: require(_isSenderAuthorized(onBehalf))"
          ]
        },
        {
          "line_range": "249",
          "code": [
            "249: _accrueInterest(marketParams, id)"
          ]
        }
      ],
      "analysis": "The uncovered code starts at line 244 with multiple require statements. The root cause is that the fuzzer is passing parameter values that fail these validation checks. Most likely, line 247's `require(_isSenderAuthorized(onBehalf))` is reverting because the `onBehalf` value isn't authorized. To fix this, we need to clamp the parameter space in our handlers so the fuzzer only passes authorized addresses for `onBehalf`, allowing execution to proceed past these require statements."
    }
  ],
  "summary": {
    "total_functions": 15,
    "functions_missing_coverage": 2,
    "total_uncovered_chunks": 3
  }
}
```

**Analysis Field Structure:**
The `"analysis"` field is a string containing:
1. What the uncovered code does and why it's not being reached
2. The root cause of the blockage (failed require, unsatisfied condition, unreachable state, etc.)
3. The type of fix needed (clamped handler, new target function, state initialization, etc.)

---

## Step 17: Implementing Coverage Fixes

**Type:** Task (OPENCODE - Agent)

**Inputs:**
- Agent: `./.opencode/agent/coverage-phase-4.md`
- File: `magic/functions-missing-covg-{timestamp}.json` (with analysis field)

**Outputs:**
- Modified or new handler functions in test contracts to address coverage gaps based on the analysis

**Implementation Types:**
1. **Clamped Handlers** - Constrain parameter values to guide the fuzzer
2. **New Target Functions** - Enable previously unreachable system states

---

## Step 18: Run Echidna Programmatically (Iteration)

**Type:** Task (PROGRAM)

**Inputs:**
- Files: Updated test contracts with improved handlers
- Config: `echidna.yaml`

**Command:**
```bash
echidna . --contract CryticTester --config echidna.yaml --format text --timeout 1800 --test-limit 99999999999999999999 --disable-slither --test-mode exploration
```

**Outputs:**
- Directory: `echidna/`

---

## Step 19: Echidna Output Check (Iteration)

**Type:** Decision (FILE_EXISTS)

**Inputs:**
- Pattern: `echidna/*.txt`

**Decision Logic:**
- If file does not exist (value = 0): STOP workflow (Echidna failed)
- If file exists (value = 1): Continue to Step 20

---

## Step 20: Evaluate Coverage (Iteration)

**Type:** Task (PROGRAM)

**Inputs:**
- File: `magic/recon-coverage.json` (line ranges per source file)
- Directory: `echidna/` (containing LCOV files)

**Command:**
```bash
covg-eval magic/ echidna/ --return-json
```

**Outputs:**
- File: `magic/functions-missing-covg-{timestamp}.json`
- Structure: Same as Step 14 output

---

## Step 21: Coverage Improvement Decision Check

**Type:** Decision (FILE_EXISTS)

**Inputs:**
- Pattern: `magic/functions-missing-covg-*.json`

**Decision Logic:**
- If file exists (value = 1): Jump to Step 16 (Analyzing Coverage Gaps - loop)
- If file does not exist (value = 0): Continue to Step 22

---

## Step 22: Workflow Complete

**Type:** Task (PROGRAM)

**Command:**
```bash
echo 'Fuzzing coverage workflow completed successfully'
```

**Outputs:**
- Console: Success message
