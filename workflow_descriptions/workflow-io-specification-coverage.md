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
forge clean && forge build --build-info
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

## Step 12: Analyze Echidna Output

**Type:** Task (PROGRAM)

**Inputs:**
- File: `echidna-exit-code.txt` (exit code from Step 11)
- File: `echidna-output.log` (Echidna execution log)

**Command:**
```bash
EXIT_CODE=$(grep 'ECHIDNA_EXIT_CODE=' echidna-exit-code.txt | cut -d'=' -f2); analyze-echidna-output $EXIT_CODE --log-file echidna-output.log --return-json
```

**Outputs:**
- File: `magic/echidna-error-analysis.json`

**Output JSON Structure:**
```json
{
  "status": "success" | "error",
  "exit_code": 0,
  "workflow_action": "continue" | "stop",
  "message": "Description of result",
  "error_type": "compilation" | "unlinked_libraries" | "setup" | "rpc" | "contract_not_found" | "unknown",
  "error_details": {
    "error_lines": ["line1", "line2"],
    "context": "Error context",
    "suggested_action": "Action to take",
    "suggested_fix": "Fix instructions",
    "common_causes": ["cause1", "cause2"]
  },
  "description": "Human-readable description",
  "timestamp": "2025-12-30T11:26:23.871017"
}
```

**Description:**
This tool analyzes Echidna's execution output to categorize errors and determine the appropriate workflow action. It detects:
- **Compilation errors**: Triggers compilation fix agent
- **Unlinked libraries**: Provides library linking guidance
- **Setup failures**: Documents setUp() issues
- **RPC errors**: Missing RPC configuration
- **Contract not found**: Contract location issues
- **Unknown errors**: Unrecognized patterns

The tool returns exit code 0 in workflow mode (with `--return-json`), allowing the JSON content to communicate findings to decision steps rather than using exit codes.

---

## Step 13: Handle Echidna Results

**Type:** Decision (JSON_KEY_VALUE)

**Inputs:**
- File: `magic/echidna-error-analysis.json`

**Decision Logic:**
- Reads: `exit_code` key
- If value = 0: Jump to Step 16 (Echidna succeeded, continue workflow)
- If value ≠ 0: Jump to Step 14 (Echidna failed, check error type)

---


## Step 15: Fix Compilation Errors

**Type:** Task (OPENCODE - Agent)

**Inputs:**
- Agent: `./.opencode/agent/fix-compilation-errors.md`
- File: `magic/echidna-error-analysis.json` (error details)

**Outputs:**
- Fixed Solidity source files or configuration

**Next Step:** Step 11 (Retry Echidna after fixing compilation errors)

**Description:**
This agent analyzes compilation errors from the error analysis file and attempts to fix them automatically. After fixes are applied, the workflow jumps back to Step 11 to retry Echidna execution.

---

## Step 16: Generate Functions to Cover

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

## Step 17: Evaluate Coverage

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

## Step 18: Score and Sort by Complexity

**Type:** Task (PROGRAM)

**Inputs:**
- File: `magic/functions-missing-covg-{timestamp}.json` (from Step 17)
- File: `magic/cyclomatic-complexity.json` (auto-generated if missing)

**Command:**
```bash
covg-scoring --return-json
```

**Outputs:**
- File: `magic/functions-missing-covg-{timestamp}.json` (updated with complexity scores and sorted)

**Output JSON Structure:**
```json
[
  {
    "function": "complexFunction",
    "contract": "ContractName",
    "source_file": "src/ContractName.sol",
    "function_range": {"start": 100, "end": 150},
    "uncovered_code": {
      "line_range": "120-125",
      "last_covered_line": 118,
      "code": ["120: require(condition)", "121: someLogic()"]
    },
    "complexity": 8
  },
  {
    "function": "simpleFunction",
    "contract": "ContractName",
    "source_file": "src/ContractName.sol",
    "function_range": {"start": 50, "end": 60},
    "uncovered_code": {
      "line_range": "55",
      "last_covered_line": 53,
      "code": ["55: return value;"]
    },
    "complexity": 1
  },
  {
    "function": "unknownComplexity",
    "contract": "SomeContract",
    "source_file": "src/SomeContract.sol",
    "function_range": {"start": 200, "end": 220},
    "uncovered_code": {
      "line_range": "210",
      "last_covered_line": null,
      "code": ["210: revert();"]
    },
    "complexity": null
  }
]
```

**Description:**
This tool adds cyclomatic complexity scores to each function in the missing coverage file and sorts them by complexity (highest first). Functions without complexity data are placed at the end with `complexity: null`. This prioritization helps focus coverage efforts on the most complex functions first, as they often represent the most critical business logic.

---

## Step 19: Create Latest Coverage Link

**Type:** Task (PROGRAM)

**Inputs:**
- Directory: `magic/` (containing timestamped coverage files)

**Command:**
```bash
get-latest-coverage --return-json
```

**Outputs:**
- File: `magic/functions-missing-covg-latest.json`

**Output JSON Structure:**
Same structure as `functions-missing-covg-{timestamp}.json` from Step 14, containing the most recent coverage data.

**Description:**
This tool finds the most recent `functions-missing-covg-{timestamp}.json` file based on timestamp, reads its content, and outputs it to stdout. The workflow captures this output and saves it to `functions-missing-covg-latest.json`.

This creates a stable filename that decision steps can reference, while preserving all timestamped files for historical tracking. The tool:
1. Searches `magic/` for all `functions-missing-covg-{timestamp}.json` files
2. Filters out `-grouped-` and `-latest` files
3. Sorts by timestamp (newest first)
4. Outputs the content of the most recent file

**Why This Is Needed:**
Decision steps need to check a specific file, but the timestamped files have unpredictable names. This step creates a deterministic filename (`-latest.json`) that always points to the most current coverage data.

---

## Step 20: Initial Check of Coverage

**Type:** Decision (JSON_KEY_VALUE)

**Inputs:**
- File: `magic/functions-missing-covg-latest.json`

**Decision Logic:**
- Reads: `summary.functions_with_missing_coverage` key
- If value > 0: Jump to Step 21 (Function Grouping and Prioritization)
- If value = 0: Jump to Step 34 (Workflow Complete)

---

## Step 21: Function Grouping and Prioritization

**Type:** Task (OPENCODE - Agent)

**Inputs:**
- Agent: `./.opencode/agent/coverage-phase-3.md`
- File: `magic/functions-missing-covg-{timestamp}.json`

**Outputs:**
- File: `magic/functions-missing-covg-grouped-{timestamp}.json`

**Description:**
This agent groups uncovered functions by their state dependencies and prioritizes them for fixing.

---

## Step 22: Analyzing Coverage Gaps

**Type:** Task (OPENCODE - Agent)

**Inputs:**
- Agent: `./.opencode/agent/coverage-phase-4.md`
- File: `magic/functions-missing-covg-grouped-{timestamp}.json`

**Outputs:**
- Modified: `magic/functions-missing-covg-grouped-{timestamp}.json` with added `"analysis"` field

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

## Step 23: Implementing Coverage Fixes

**Type:** Task (OPENCODE - Agent)

**Inputs:**
- Agent: `./.opencode/agent/coverage-phase-5.md`
- File: `magic/functions-missing-covg-grouped-{timestamp}.json` (with analysis field)

**Outputs:**
- Modified or new handler functions in test contracts to address coverage gaps based on the analysis

**Implementation Types:**
1. **Clamped Handlers** - Constrain parameter values to guide the fuzzer
2. **Shortcut Functions** - Enable previously unreachable system states

---

## Step 24: Run Echidna Programmatically (Iteration)

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

## Step 25: Analyze Echidna Output (Iteration)

**Type:** Task (PROGRAM)

**Inputs:**
- File: `echidna-exit-code.txt` (exit code from Step 24)
- File: `echidna-output.log` (Echidna execution log)

**Command:**
```bash
EXIT_CODE=$(grep 'ECHIDNA_EXIT_CODE=' echidna-exit-code.txt | cut -d'=' -f2); analyze-echidna-output $EXIT_CODE --log-file echidna-output.log --return-json
```

**Outputs:**
- File: `magic/echidna-error-analysis.json`
- Structure: Same as Step 12 output

---

## Step 26: Handle Echidna Results (Iteration)

**Type:** Decision (JSON_KEY_VALUE)

**Inputs:**
- File: `magic/echidna-error-analysis.json`

**Decision Logic:**
- Reads: `exit_code` key
- If value = 0: Jump to Step 29 (Echidna succeeded, continue workflow)
- If value ≠ 0: Jump to Step 27 (Echidna failed, check error type)

---


## Step 28: Fix Compilation Errors (Iteration)

**Type:** Task (OPENCODE - Agent)

**Inputs:**
- Agent: `./.opencode/agent/fix-compilation-errors.md`
- File: `magic/echidna-error-analysis.json` (error details)

**Outputs:**
- Fixed Solidity source files or configuration

**Next Step:** Step 24 (Retry Echidna after fixing compilation errors)

---

## Step 29: Evaluate Coverage (Iteration)

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
- Structure: Same as Step 17 output

---

## Step 30: Score and Sort by Complexity (Iteration)

**Type:** Task (PROGRAM)

**Inputs:**
- File: `magic/functions-missing-covg-{timestamp}.json` (from Step 29)
- File: `magic/cyclomatic-complexity.json` (auto-generated if missing)

**Command:**
```bash
covg-scoring --return-json
```

**Outputs:**
- File: `magic/functions-missing-covg-{timestamp}.json` (updated with complexity scores and sorted)
- Structure: Same as Step 18 output

**Description:**
Adds cyclomatic complexity scores to the updated missing coverage functions and re-sorts by complexity to prioritize the next iteration of coverage fixes.

---

## Step 31: Create Latest Coverage Link (Iteration)

**Type:** Task (PROGRAM)

**Inputs:**
- Directory: `magic/` (containing timestamped coverage files)

**Command:**
```bash
get-latest-coverage --return-json
```

**Outputs:**
- File: `magic/functions-missing-covg-latest.json`

**Description:**
Same as Step 19 - creates an up-to-date `functions-missing-covg-latest.json` file with the latest coverage data after the iteration, so Step 32 can check the current status.

---

## Step 32: Coverage Improvement Decision Check

**Type:** Decision (JSON_KEY_VALUE)

**Inputs:**
- File: `magic/functions-missing-covg-latest.json`

**Decision Logic:**
- Reads: `summary.functions_with_missing_coverage` key
- If value > 0: Jump to Step 21 (Function Grouping and Prioritization - loop)
- If value = 0: Continue to Step 33

---

## Step 33: Dispatch Fuzzing Job

**Type:** Task (DISPATCH_FUZZING_JOB)

**Inputs:**
- All test contracts with implemented handlers
- Coverage data and analysis results

**Model Type:** DISPATCH_FUZZING_JOB

**Description:**
This step dispatches a long-running fuzzing job (100 million test limit) to the backend fuzzing infrastructure. After the workflow has completed local coverage optimization, this step queues the project for extended fuzzing to discover deeper bugs and edge cases.

The backend will run:
- Extended Echidna fuzzing campaign with 100 million tests
- Property-based testing using all implemented handlers
- Results will be collected and reported separately

**Outputs:**
- Job dispatched to backend queue
- Job ID (if applicable)

---

## Step 34: Workflow Complete

**Type:** Task (PROGRAM)

**Command:**
```bash
echo 'Fuzzing coverage workflow completed successfully'
```

**Outputs:**
- Console: Success message
