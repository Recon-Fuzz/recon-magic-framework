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

## Step 5: Identifying Touched Functions

**Type:** Task (PROGRAM)

**Inputs:**
- Directory: `context_output/`
- File: `magic/target-functions.json`

**Command:**
```bash
touched-function-identifier --sol-expand-dir context_output --target-functions magic/target-functions.json --return-json
```

**Outputs:**
- File: `magic/functions-to-cover.json`

**Output JSON Structure:**
```json
{
  "ContractName": {
    "functions_to_cover": ["functionName1", "functionName2"]
  }
}
```

**When using `--return-json` flag:**
```json
{
  "data": {"ContractName": {"functions_to_cover": ["functionName1"]}},
  "summary": {"contracts_found": 1, "total_functions": 1}
}
```

---

## Step 6: Identifying Meaningful Values

**Type:** Task (OPENCODE - Agent)

**Inputs:**
- Agent: `./.opencode/agent/coverage-phase-0.md`
- File: `magic/functions-to-cover.json`

**Outputs:**
- Identified meaningful values for clamping handlers

---

## Step 7: Creating Clamped Handlers

**Type:** Task (OPENCODE - Agent)

**Inputs:**
- Agent: `./.opencode/agent/coverage-phase-1.md`
- File: `magic/functions-to-cover.json`

**Outputs:**
- Modified or new handler functions in test contracts

---

## Step 8: Creating Shortcut Handlers

**Type:** Task (OPENCODE - Agent)

**Inputs:**
- Agent: `./.opencode/agent/coverage-phase-2.md`
- File: `magic/functions-to-cover.json`

**Outputs:**
- Modified or new shortcut handler functions in test contracts

---

## Step 9: Run Echidna Programmatically

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

## Step 10: Echidna Output Check

**Type:** Decision (FILE_EXISTS)

**Inputs:**
- Pattern: `echidna/*.txt`

**Decision Logic:**
- If file does not exist (value = 0): STOP workflow (Echidna failed)
- If file exists (value = 1): Continue to Step 11

---

## Step 11: Evaluate Coverage

**Type:** Task (PROGRAM)

**Inputs:**
- Directory: `magic/`
- Directory: `echidna/`

**Command:**
```bash
covg-eval magic/ echidna/ --return-json
```

**Outputs:**
- File: `magic/functions-missing-covg-{timestamp}.json`

**Output JSON Structure (when not using `--return-json`):**
```json
[
  {
    "function": "functionName1",
    "contract": "ContractName",
    "source_file": "src/ContractName.sol",
    "function_range": {"start": 45, "end": 78},
    "uncovered_code": {
      "line_range": "50-52",
      "last_covered_line": 48,
      "code": [
        "48: [LAST COVERED]     uint256 value = getValue();",
        "50:         if (condition) {",
        "51:             revert CustomError();",
        "52:         }"
      ]
    }
  },
  {
    "function": "functionName1",
    "contract": "ContractName",
    "source_file": "src/ContractName.sol",
    "function_range": {"start": 45, "end": 78},
    "uncovered_code": {
      "line_range": "65",
      "last_covered_line": 63,
      "code": [
        "63: [LAST COVERED]     balance = newBalance;",
        "65:         emit BalanceUpdated(balance);"
      ]
    }
  }
]
```

**When using `--return-json` flag:**
```json
{
  "timestamp": "1733845200",
  "lcov_file": "echidna/covered.1733845200.lcov",
  "missing_coverage": [
    {
      "function": "functionName1",
      "contract": "ContractName",
      "source_file": "src/ContractName.sol",
      "function_range": {"start": 45, "end": 78},
      "uncovered_code": {
        "line_range": "50-52",
        "last_covered_line": 48,
        "code": ["48: [LAST COVERED]     uint256 value = getValue();", "50:         if (condition) {", "51:             revert CustomError();", "52:         }"]
      }
    }
  ],
  "summary": {
    "functions_analyzed": 15,
    "functions_with_missing_coverage": 2,
    "uncovered_sections": 3,
    "full_coverage": false
  }
}
```

---

## Step 12: Initial Check of Coverage

**Type:** Decision (FILE_EXISTS)

**Inputs:**
- Pattern: `functions-missing-covg-*.json` in magic directory

**Decision Logic:**
- If file exists (value = 1): Jump to Step 13 (Analyzing Coverage Gaps)
- If file does not exist (value = 0): Jump to Step 19 (Workflow Complete)

---

## Step 13: Analyzing Coverage Gaps

**Type:** Task (OPENCODE - Agent)

**Inputs:**
- Agent: `./.opencode/agent/coverage-phase-3.md`
- File: Latest `magic/functions-missing-covg-{timestamp}.json`

**Outputs:**
- Modified: `magic/functions-missing-covg-{timestamp}.json` with added `"analysis"` field

**Output Structure:**
Each entry in the `missing_coverage` array will have a new `"analysis"` field added:

```json
[
  {
    "function": "borrow",
    "contract": "Morpho",
    "source_file": "src/Morpho.sol",
    "function_range": {"start": 235, "end": 260},
    "uncovered_code": {
      "line_range": "244-249",
      "last_covered_line": 243,
      "code": [
        "243: [LAST COVERED]     require(market[id].lastUpdate != 0, ErrorsLib.MARKET_NOT_CREATED)",
        "244:         require(UtilsLib.exactlyOneZero(assets, shares))",
        "245:         require(receiver != address(0))",
        "247:         require(_isSenderAuthorized(onBehalf))",
        "249:         _accrueInterest(marketParams, id)"
      ]
    },
    "analysis": "The last_covered_line is 243, which contains `require(market[id].lastUpdate != 0, ErrorsLib.MARKET_NOT_CREATED)`. Since line 243 was covered (the require passed), execution continued to line 244. However, lines 244-249 are uncovered, indicating that one of the subsequent require statements is causing execution to revert.\n\nLooking at the uncovered lines, we see multiple require statements:\n- Line 244: `require(UtilsLib.exactlyOneZero(assets, shares))`\n- Line 245: `require(receiver != address(0))`\n- Line 247: `require(_isSenderAuthorized(onBehalf))`\n\nThe root cause is that the fuzzer is passing parameter values that fail these validation checks. Most likely, line 247's `require(_isSenderAuthorized(onBehalf))` is reverting because the `onBehalf` value isn't authorized. To fix this, we need to clamp the parameter space in our handlers so the fuzzer only passes authorized addresses for `onBehalf`, allowing execution to proceed past these require statements."
  }
]
```

**Analysis Field Structure:**
The `"analysis"` field is a string containing:
1. What the `last_covered_line` does and why it succeeded
2. Why the subsequent lines are uncovered
3. The root cause of the blockage (failed require, unsatisfied condition, unreachable state, etc.)
4. The type of fix needed (clamped handler, new target function, state initialization, etc.)

---

## Step 14: Implementing Coverage Fixes

**Type:** Task (OPENCODE - Agent)

**Inputs:**
- Agent: `./.opencode/agent/coverage-phase-4.md`
- File: Latest `magic/functions-missing-covg-{timestamp}.json` (with analysis field)

**Outputs:**
- Modified or new handler functions in test contracts to address coverage gaps based on the analysis

**Implementation Types:**
1. **Clamped Handlers** - Constrain parameter values to guide the fuzzer
2. **New Target Functions** - Enable previously unreachable system states

---

## Step 15: Run Echidna Programmatically (Iteration)

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

## Step 16: Echidna Output Check (Iteration)

**Type:** Decision (FILE_EXISTS)

**Inputs:**
- Pattern: `echidna/*.txt`

**Decision Logic:**
- If file does not exist (value = 0): STOP workflow (Echidna failed)
- If file exists (value = 1): Continue to Step 17

---

## Step 17: Evaluate Coverage (Iteration)

**Type:** Task (PROGRAM)

**Inputs:**
- Directory: `magic/`
- Directory: `echidna/`

**Command:**
```bash
covg-eval magic/ echidna/ --return-json
```

**Outputs:**
- File: `magic/functions-missing-covg-{timestamp}.json`
- Structure: Same as Step 11 output

---

## Step 18: Coverage Improvement Decision Check

**Type:** Decision (FILE_EXISTS)

**Inputs:**
- Pattern: `functions-missing-covg-*.json` in magic directory

**Decision Logic:**
- If file exists (value = 1): Jump to Step 13 (Analyzing Coverage Gaps - loop)
- If file does not exist (value = 0): Continue to Step 19

---

## Step 19: Workflow Complete

**Type:** Task (PROGRAM)

**Command:**
```bash
echo 'Fuzzing coverage workflow completed successfully'
```

**Outputs:**
- Console: Success message
