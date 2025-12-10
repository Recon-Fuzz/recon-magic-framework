# Fuzzing Coverage Workflow - Input/Output Specification

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

## Step 3a: Filter Build Artifacts

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

## Step 3b: Extract Context with sol-expand

**Type:** Task (PROGRAM)

**Inputs:**
- File: Filtered JSON file in `out/build-info` directory

**Command:**
```bash
sol-expand --extract-context $(find out/build-info -name '*.filtered.json' | head -1)
```

**Outputs:**
- Directory: `context_output/`

---

## Step 4: Identifying Touched Functions

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

## Step 5: Identifying Meaningful Values

**Type:** Task (OPENCODE - Agent)

**Inputs:**
- Agent: `./.opencode/agent/coverage-phase-1.md`
- File: `magic/functions-to-cover.json`

**Outputs:**
- Identified meaningful values for clamping handlers

---

## Step 6: Creating Clamped Handlers

**Type:** Task (OPENCODE - Agent)

**Inputs:**
- Agent: `./.opencode/agent/coverage-phase-2.md`
- File: `magic/functions-to-cover.json`

**Outputs:**
- Modified or new handler functions in test contracts

---

## Step 7: Creating Shortcut Handlers

**Type:** Task (OPENCODE - Agent)

**Inputs:**
- Agent: `./.opencode/agent/coverage-phase-3.md`
- File: `magic/functions-to-cover.json`

**Outputs:**
- Modified or new shortcut handler functions in test contracts

---

## Step 8: Run Echidna Programmatically

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

## Step 9: Evaluate Coverage

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

**Output JSON Structure:**
```json
{
  "functionName1": {
    "contract": "ContractName",
    "source_file": "src/ContractName.sol",
    "function_range": {"start": 45, "end": 78},
    "coverage_stats": {"total_lines": 25, "covered_lines": 20, "uncovered_lines": 5, "percentage": 80.0},
    "uncovered_code": [
      {"line_range": "50-52", "code": ["50:         if (condition) {", "51:             revert CustomError();", "52:         }"]}
    ]
  }
}
```

**When using `--return-json` flag:**
```json
{
  "timestamp": "1733845200",
  "lcov_file": "echidna/covered.1733845200.lcov",
  "missing_coverage": {...},
  "summary": {"functions_analyzed": 15, "functions_with_missing_coverage": 2, "full_coverage": false}
}
```

---

## Step 10: Initial Check of Coverage

**Type:** Decision (FILE_EXISTS)

**Inputs:**
- Pattern: `functions-missing-covg-*.json` in magic directory

**Decision Logic:**
- If file exists (value = 1): Jump to Step 11
- If file does not exist (value = 0): Jump to Step 15

---

## Step 11: Improving Coverage

**Type:** Task (OPENCODE - Agent)

**Inputs:**
- Agent: `./.opencode/agent/coverage-phase-5.md`
- File: Latest `magic/functions-missing-covg-{timestamp}.json`

**Outputs:**
- Modified or new handler functions to address coverage gaps

---

## Step 12: Run Echidna Programmatically (Iteration)

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

## Step 13: Evaluate Coverage (Iteration)

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
- Structure: Same as Step 9 output

---

## Step 14: Coverage Improvement Decision Check

**Type:** Decision (FILE_EXISTS)

**Inputs:**
- Pattern: `functions-missing-covg-*.json` in magic directory

**Decision Logic:**
- If file exists (value = 1): Jump to Step 11 (loop)
- If file does not exist (value = 0): Continue to Step 15

---

## Step 15: Workflow Complete

**Type:** Task (PROGRAM)

**Command:**
```bash
echo 'Fuzzing coverage workflow completed successfully'
```

**Outputs:**
- Console: Success message
