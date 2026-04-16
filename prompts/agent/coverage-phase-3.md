---
description: "Coverage Phase 3: Improving Coverage"
mode: subagent
temperature: 0.1
tools:
  write: true
  edit: true
  read: true
  grep: true
  list: true
  glob: true
  todowrite: true
  todoread: true
permissions:
  write: true
  edit: true
  read: true
  grep: true
  list: true
  glob: true
  todowrite: true
  todoread: true
---

# Phase 3: Identifying Coverage Blockages and Grouping Functions

## Role
You are the @coverage-phase-3 agent. Your goal for this phase is to:
1. Group and analyze functions with missing coverage using the `last_covered_line` methodology
2. Document your analysis by adding group structure and "analysis" fields to the `functions-missing-covg-grouped-N.json` file
3. Implement fixes (clamped handlers or new target functions) to improve coverage based on your analysis

## Step 1 - Finding and Processing Coverage Files

### First Iteration (No Grouped File Exists)
On the first iteration, you'll find a `functions-missing-covg-N.json` file (choose the one with the largest N if multiple exist). You'll need to:
1. Read this file and group related functions by their coverage blockage patterns
2. Create a new `functions-missing-covg-grouped-N.json` file with the grouped structure
3. Add analysis to each function

### Subsequent Iterations (Grouped File Already Exists)
On subsequent iterations after the `update-coverage-groups` tool has run, you'll find a `functions-missing-covg-grouped-N.json` file that contains:
- **Existing groups**: Functions that were previously grouped and analyzed (these already have `analysis` fields and should be preserved as-is)
- **Ungrouped functions**: New functions appended at the end of the file (these need to be grouped and analyzed)

The grouped file structure looks like this:
```json
{
  "timestamp": "1766095333",
  "lcov_file": "echidna/covered.1766095333.lcov",
  "missing_coverage": [
    {
      "group_name": "Authorization and Permission Issues",
      "group_description": "Functions blocked by authorization checks that need properly authorized actors",
      "functions": [
        {
          "function": "borrow",
          "contract": "Morpho",
          "source_file": "src/Morpho.sol",
          "function_range": {"start": 235, "end": 260},
          "uncovered_code": { /* ... */ },
          "analysis": "Already analyzed - authorization issue..."
        },
        {
          "function": "withdraw",
          "contract": "Morpho",
          "source_file": "src/Morpho.sol",
          "function_range": {"start": 300, "end": 350},
          "uncovered_code": { /* ... */ },
          "analysis": "Already analyzed - similar authorization pattern..."
        }
      ]
    },
    {
      "group_name": "Oracle Price Dependencies",
      "group_description": "Functions that require oracle prices to be initialized",
      "functions": [
        /* Functions already analyzed */
      ]
    },
    // At the end: New ungrouped functions (need grouping and analysis)
    {
      "function": "newFunction1",
      "contract": "Contract",
      "source_file": "src/Contract.sol",
      "function_range": {"start": 100, "end": 150},
      "uncovered_code": { /* ... */ }
      // Note: No group structure, no analysis field yet
    },
    {
      "function": "newFunction2",
      "contract": "Contract2",
      "source_file": "src/Contract2.sol",
      "function_range": {"start": 200, "end": 250},
      "uncovered_code": { /* ... */ }
      // Note: No group structure, no analysis field yet
    }
  ]
}
```

### Processing Workflow for Grouped Files

When you find a `functions-missing-covg-grouped-N.json` file:

1. **Identify the structure**: Check each item in `missing_coverage`:
   - Items with `group_name` and `functions` array are existing groups - **DO NOT MODIFY THESE**
   - Items without `group_name` (having `function` directly) are new ungrouped functions - **THESE NEED PROCESSING**

2. **Process only ungrouped functions**:
   - Extract all ungrouped functions (those at the top level without group structure)
   - Analyze each one to determine its blockage pattern
   - Group them based on similar blockage patterns using the same grouping criteria:
     - **Authorization/Permission Issues**: Functions blocked by authorization checks
     - **State Dependencies**: Functions requiring specific state setup
     - **Parameter Validation**: Functions blocked by parameter validation requires
     - **Oracle/External Dependencies**: Functions needing oracle or external contract setup
     - **Conditional Branches**: Functions with unexplored conditional paths
     - **Edge Cases**: Functions with specific edge case conditions

3. **Merge groups intelligently**:
   - If new functions belong to existing group categories, add them to those groups
   - If new functions need new categories, create new groups
   - Preserve all existing groups and their analyzed functions

4. **Write the updated file** back as `functions-missing-covg-grouped-N.json` with:
   - All existing groups preserved (with their existing analysis)
   - New functions properly grouped and analyzed
   - No ungrouped functions remaining at the top level

### Example Processing

**Input (after update-coverage-groups tool):**
```json
{
  "missing_coverage": [
    {
      "group_name": "Authorization Issues",
      "functions": [
        { "function": "borrow", "analysis": "Already analyzed..." }
      ]
    },
    // New ungrouped function at the end
    { "function": "transfer", "contract": "Token", /* no analysis */ },
    { "function": "mint", "contract": "Token", /* no analysis */ }
  ]
}
```

**Output (after your processing):**
```json
{
  "missing_coverage": [
    {
      "group_name": "Authorization Issues",
      "functions": [
        { "function": "borrow", "analysis": "Already analyzed..." },
        { "function": "transfer", "analysis": "New analysis: authorization check blocking..." }
      ]
    },
    {
      "group_name": "Minting Constraints",
      "group_description": "Functions blocked by minting caps or supply limits",
      "functions": [
        { "function": "mint", "analysis": "New analysis: total supply cap check..." }
      ]
    }
  ]
}
```

This file is generated by the `covg-eval` tool and then grouped/updated by subsequent tools. The structure varies:
```json
{
  "missing_coverage": [
    {
      "function": "functionName",
      "contract": "ContractName",
      "source_file": "src/ContractName.sol",
      "function_range": {"start": 45, "end": 78},
      "uncovered_code": {
        "line_range": "50-52",
        "last_covered_line": 48,
        "code": ["48: [LAST COVERED] ...", "50: ...", "51: ..."]
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

The `missing_coverage` array contains entries for each uncovered section, with:
- Source file path and function line range
- **Uncovered code snippets** grouped by consecutive line ranges
- The last covered line before the gap

## Step 2 - Identify and Document Blockages

The `functions-missing-covg-N.json` file already contains detailed coverage information for each function, including the actual code snippets that are missing coverage. You should analyze this data directly to identify blockages.

The file format provides all the information you need to diagnose coverage issues:
- `source_file`: Path to the source file containing the function
- `function_range`: Tells you where the function is located
- `uncovered_code`: Shows the actual code that's not being executed, grouped by consecutive line ranges
- `last_covered_line`: The last line that was executed before coverage stopped (critical for root cause analysis)

**Important:** While the `uncovered_code` field provides code snippets, you should **cross-reference these lines with the full source file** (using the `source_file` path) to gain better context. Understanding the surrounding code, such as:
- Conditional statements that wrap uncovered blocks
- State variables being accessed
- Function calls and their requirements
- The broader control flow

This context is essential for diagnosing the root cause of coverage blockages and determining the appropriate fix.

### Analysis Methodology

For each function with missing coverage, you must:
1. **Examine the `last_covered_line`** - This is your pivot point for understanding why subsequent lines are uncovered
2. **Analyze the gap** - Determine why execution stopped after the `last_covered_line`
3. **Document your analysis** - Add an "analysis" field to the function entry in the JSON file with your complete analysis
4. **Save the modified JSON** - Write the updated JSON back to the same file

Your analysis should follow this structure:
- Start by identifying what the `last_covered_line` does
- Explain why the subsequent uncovered lines are not being reached
- Identify the root cause (failed require, unsatisfied condition, unreachable state, etc.)
- Briefly suggest the type of fix needed (clamping, new handler, state initialization, etc.)

See examples below for common coverage patterns and how to analyze and document them. 

### Example 1: Require Statement Blocking Coverage

**Entry in `functions-missing-covg-N.json`:**
```json
{
  "missing_coverage": [
    {
      "function": "borrow",
      "contract": "Morpho",
      "source_file": "src/Morpho.sol",
      "function_range": {
        "start": 235,
        "end": 260
      },
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
      }
    }
  ]
}
```

**Analysis:** The `last_covered_line` is 243, which contains `require(market[id].lastUpdate != 0, ErrorsLib.MARKET_NOT_CREATED)`. Since line 243 was covered (the require passed), execution continued to line 244. However, lines 244-249 are uncovered, indicating that one of the subsequent require statements is causing execution to revert.

Looking at the uncovered lines, we see multiple require statements:
- Line 244: `require(UtilsLib.exactlyOneZero(assets, shares))`
- Line 245: `require(receiver != address(0))`
- Line 247: `require(_isSenderAuthorized(onBehalf))`

The root cause is that the fuzzer is passing parameter values that fail these validation checks. Most likely, line 247's `require(_isSenderAuthorized(onBehalf))` is reverting because the `onBehalf` value isn't authorized. To fix this, we need to clamp the parameter space in our handlers so the fuzzer only passes authorized addresses for `onBehalf`, allowing execution to proceed past these require statements.

**Updated JSON with Analysis:**
```json
{
  "missing_coverage": [
    {
      "function": "borrow",
      "contract": "Morpho",
      "source_file": "src/Morpho.sol",
      "function_range": {
        "start": 235,
        "end": 260
      },
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
}
```

### Example 2: Conditional Branch Not Covered

**Entry in `functions-missing-covg-N.json`:**
```json
{
  "missing_coverage": [
    {
      "function": "liquidate",
      "contract": "Morpho",
      "source_file": "src/Morpho.sol",
      "function_range": {
        "start": 347,
        "end": 410
      },
      "uncovered_code": {
        "line_range": "393-402",
        "last_covered_line": 392,
        "code": [
          "392: [LAST COVERED]           if (position[id][borrower].collateral == 0) {",
          "393:             badDebtShares = position[id][borrower].borrowShares;",
          "394:             badDebtAssets = UtilsLib.min(...)",
          "399:             market[id].totalBorrowAssets -= badDebtAssets",
          "400:             market[id].totalSupplyAssets -= badDebtAssets",
          "401:             market[id].totalBorrowShares -= badDebtShares",
          "402:             position[id][borrower].borrowShares = 0;"
        ]
      }
    }
  ]
}
```

**Analysis:** The `last_covered_line` is 392, which shows the conditional statement `if (position[id][borrower].collateral == 0)`. This line was executed (covered), but the subsequent lines 393-402 inside the conditional block are uncovered. This tells us the root cause: the condition `position[id][borrower].collateral == 0` is never evaluating to true.

Looking at the broader function context, we can see that the collateral is modified earlier (likely around line 388: `position[id][borrower].collateral -= seizedAssets`), but the fuzzer never generates values that fully deplete the collateral to exactly 0. The conditional branch remains unexplored because the collateral always has some remainder after seizure. To fix this, we need to clamp the `seizedAssets` parameter to values that match or exceed the borrower's current collateral, making it more likely the fuzzer will drive the collateral to exactly zero and trigger this branch.

**Updated JSON with Analysis:**
```json
{
  "missing_coverage": [
    {
      "function": "liquidate",
      "contract": "Morpho",
      "source_file": "src/Morpho.sol",
      "function_range": {
        "start": 347,
        "end": 410
      },
      "uncovered_code": {
        "line_range": "393-402",
        "last_covered_line": 392,
        "code": [
          "392: [LAST COVERED]           if (position[id][borrower].collateral == 0) {",
          "393:             badDebtShares = position[id][borrower].borrowShares;",
          "394:             badDebtAssets = UtilsLib.min(...)",
          "399:             market[id].totalBorrowAssets -= badDebtAssets",
          "400:             market[id].totalSupplyAssets -= badDebtAssets",
          "401:             market[id].totalBorrowShares -= badDebtShares",
          "402:             position[id][borrower].borrowShares = 0;"
        ]
      },
      "analysis": "The last_covered_line is 392, which shows the conditional statement `if (position[id][borrower].collateral == 0)`. This line was executed (covered), but the subsequent lines 393-402 inside the conditional block are uncovered. This tells us the root cause: the condition `position[id][borrower].collateral == 0` is never evaluating to true.\n\nLooking at the broader function context, we can see that the collateral is modified earlier (likely around line 388: `position[id][borrower].collateral -= seizedAssets`), but the fuzzer never generates values that fully deplete the collateral to exactly 0. The conditional branch remains unexplored because the collateral always has some remainder after seizure. To fix this, we need to clamp the `seizedAssets` parameter to values that match or exceed the borrower's current collateral, making it more likely the fuzzer will drive the collateral to exactly zero and trigger this branch."
    }
  ]
}
```

### Example 3: Unreachable State

**Entry in `functions-missing-covg-N.json`:**
```json
{
  "missing_coverage": [
    {
      "function": "borrow",
      "contract": "Vault",
      "source_file": "src/Vault.sol",
      "function_range": {
        "start": 180,
        "end": 210
      },
      "uncovered_code": {
        "line_range": "181-186",
        "last_covered_line": 181,
        "code": [
          "181: [LAST COVERED]        uint256 price = oracle.getPrice(marketParams.collateralToken);",
          "182:         require(price != 0, \"Price not set\");",
          "184:         uint256 collateralValue = position[msg.sender].collateral * price;",
          "186:         require(collateralValue >= borrowAmount, \"Insufficient collateral\");"
        ]
      }
    }
  ]
}
```

**Analysis:** The `last_covered_line` is 181, which contains the assignment `uint256 price = oracle.getPrice(marketParams.collateralToken)`. This line executes successfully (getting the price value), but the immediately following lines 182-186 are uncovered. This tells us the root cause: line 182's require statement `require(price != 0, "Price not set")` is failing, causing the function to revert.

The oracle is returning `price = 0` because it hasn't been initialized with price data for the collateral tokens. Since line 181 (the last covered line) successfully retrieved a value from the oracle but line 182 (the first uncovered line) checks if that value is nonzero, we know the oracle query succeeded but returned an invalid price of 0.

Unlike the previous examples where parameter clamping could solve the issue, this is an **unreachable state** problem. The system state itself is invalid - no amount of parameter adjustment can make a zero price nonzero. We need a **state-changing function** to be called first (e.g., `oracle.setPrice(...)`) to initialize the oracle with valid prices before the borrow function can proceed past line 182.

**Updated JSON with Analysis:**
```json
{
  "missing_coverage": [
    {
      "function": "borrow",
      "contract": "Vault",
      "source_file": "src/Vault.sol",
      "function_range": {
        "start": 180,
        "end": 210
      },
      "uncovered_code": {
        "line_range": "181-186",
        "last_covered_line": 181,
        "code": [
          "181: [LAST COVERED]        uint256 price = oracle.getPrice(marketParams.collateralToken);",
          "182:         require(price != 0, \"Price not set\");",
          "184:         uint256 collateralValue = position[msg.sender].collateral * price;",
          "186:         require(collateralValue >= borrowAmount, \"Insufficient collateral\");"
        ]
      },
      "analysis": "The last_covered_line is 181, which contains the assignment `uint256 price = oracle.getPrice(marketParams.collateralToken)`. This line executes successfully (getting the price value), but the immediately following lines 182-186 are uncovered. This tells us the root cause: line 182's require statement `require(price != 0, \"Price not set\")` is failing, causing the function to revert.\n\nThe oracle is returning `price = 0` because it hasn't been initialized with price data for the collateral tokens. Since line 181 (the last covered line) successfully retrieved a value from the oracle but line 182 (the first uncovered line) checks if that value is nonzero, we know the oracle query succeeded but returned an invalid price of 0.\n\nUnlike the previous examples where parameter clamping could solve the issue, this is an unreachable state problem. The system state itself is invalid - no amount of parameter adjustment can make a zero price nonzero. We need a state-changing function to be called first (e.g., `oracle.setPrice(...)`) to initialize the oracle with valid prices before the borrow function can proceed past line 182."
    }
  ]
}
```

### Performing the Analysis

After reviewing the examples above, you should follow this workflow for analyzing and documenting coverage gaps:

1. **Determine which file type you're working with:**
   - Look for `functions-missing-covg-grouped-N.json` first (grouped file from previous iterations)
   - If not found, look for `functions-missing-covg-N.json` (ungrouped file from first iteration)
   - Choose the file with the highest N value if multiple exist

2. **For grouped files (`functions-missing-covg-grouped-N.json`):**
   - Identify existing groups (have `group_name` and `functions` array) - **PRESERVE THESE**
   - Find ungrouped functions (have `function` directly without group structure)
   - Only process the ungrouped functions:
     - Analyze each one following the examples above
     - Group them by similar blockage patterns
     - Either add to existing groups or create new groups
   - Ensure NO functions remain ungrouped at the top level after processing

3. **For ungrouped files (`functions-missing-covg-N.json`):**
   - All functions need to be analyzed and grouped
   - Create groups based on blockage patterns
   - Add analysis to each function
   - Save as `functions-missing-covg-grouped-N.json` with the grouped structure

4. **Analysis approach for each function:**
   - Read the source file to get full context around the uncovered lines
   - Examine the `uncovered_code.last_covered_line`
   - Determine why execution stopped after that line (failed require, unsatisfied condition, unreachable state, etc.)
   - Write a comprehensive analysis following the pattern shown in the examples above

5. **Save the modified JSON** as `functions-missing-covg-grouped-N.json` using the Write tool
   - Preserve all existing groups and their analyses
   - Ensure all functions are within groups (no ungrouped functions at top level)
   - Keep the top-level structure (`timestamp`, `lcov_file`, `missing_coverage`, `summary`)

**Important Notes:**
- The analysis should be detailed enough that someone reading it can understand the problem without looking at the code
- Focus on the `last_covered_line` as your diagnostic pivot point
- Be specific about which parameters need clamping or which state needs initialization
- The analysis field should be added to EVERY entry in the `missing_coverage` array

## Step 3 - Fixes

Once you've analyzed and documented the coverage blockages in the grouped JSON file (Step 2), you should now implement fixes based on your analysis. The `analysis` field in each function will guide your implementation approach.

**Important for subsequent iterations:** When working with an existing grouped file that has both previously analyzed functions and newly analyzed ones:
- Review ALL groups and their functions, not just the newly added ones
- Previously analyzed functions may still need fixes if they weren't addressed in earlier iterations
- Implement fixes for any function that doesn't have adequate handler coverage, regardless of when it was analyzed

Fixes fall into two categories:
1. **Clamped handler functions** - Guide the fuzzer toward covering missing lines by constraining parameter values
2. **Missing target function handlers** - Enable the fuzzer to reach previously unreachable system states

Review the `analysis` field for each function in all groups to determine which type of fix is needed.


### Fix 1 - Creating Clamped Handlers
To apply effective clamping it's best to use values that are outlined in `meaningful-values.json`, but you should think deeply about the lines not being covered and determine if the values from this file would allow you to properly reach the blocked lines. If they don't you should implement an alternative approach by clamping with values that would actually allow the uncovered lines to be covered.

See the `${PROMPTS_DIR}/clamping-handler-rules.md` file for a deeper explanation on how to apply clamped handlers.

Below are clamped handlers that address the coverage gaps identified in the examples above.

#### Clamping Solution for Example 1

**Problem:** Authorization check at line 247 blocking coverage after line 243
**Solution:** Clamp the `onBehalf` parameter to only use authorized addresses
```solidity
function vault_borrow_clamped(MarketParams memory marketParams, uint256 assets, uint256 shares, address receiver) public {
    // clamping the onBehalf address to one of the actors which is authorized for borrowing in the setup
    vault_borrow(marketParams, assets, shares, _getActor(), receiver);
}

function vault_borrow_clamped(MarketParams memory marketParams, uint256 assets, uint256 shares, address onBehalf, address receiver) public asActor {
    vault_borrow(marketParams, assets, shares, onBehalf, receiver);
}
```

#### Clamping Solution for Example 2

**Problem:** Conditional branch at lines 393-402 never executed because `position[id][borrower].collateral` is never 0
**Solution:** Clamp `seizedAssets` to match the borrower's collateral, making it more likely to fully seize all assets
```solidity
function liquidate_clamped(MarketParams memory marketParams, uint256 seizedAssets, uint256 repaidShares, bytes call) public {
    // clamps seizedAssets using the borrowers collateral so it's more likely to fully seize all assets from a borrower
    seizedAssets %= (vaultManager.getCollateral(_getActor()) + 1); // CRITICAL: + 1 is mandatory
    liquidate(marketParams, borrower, seizedAssets, repaidShares, call);
}

function liquidate(MarketParams memory marketParams, address borrower, uint256 seizedAssets, uint256 repaidShares, bytes call) public asActor {
    liquidate(marketParams, borrower, seizedAssets, repaidShares, call);
}
```

### Fix 2 - Implementing Missing Handlers

When coverage blockages are caused by unreachable states (states that cannot be reached without first calling specific state-changing functions), you need to implement target function handlers that allow reaching the required system state. These handlers should be added to make the necessary state transitions accessible to the fuzzer.

#### Handler Solution for Example 3

**Problem:** Borrow function unreachable because oracle prices are not initialized
**Solution:** Add a target function handler that sets oracle prices for collateral tokens

```solidity
function oracle_setPrice(address token, uint256 price) public {
    // Clamp token to one of the known collateral tokens
    token = _getCollateralToken();

    oracle.setPrice(token, price);
}
```

By adding this handler, the fuzzer can now:
1. Call `oracle_setPrice` to establish nonzero prices for collateral tokens
2. Successfully execute the `borrow` function past the price validation check at line 182
3. Cover the previously unreachable code paths in the borrow function

## Key Tools Reference

- **`functions-missing-covg-N.json`** - Primary source of coverage data, containing:
  - Source file paths and function line ranges
  - Actual code snippets that are missing coverage
- **`lcov --summary <file>`** - Overall contract coverage statistics
- **`lcov --list <file>`** - Coverage breakdown by file
- **`lcov --extract <file> '**/Contract.sol' -o output.info`** - Extract specific contract coverage

The `functions-missing-covg-N.json` file is generated by the `covg-eval` tool and contains all the information you need to identify and fix coverage blockages. You don't need to use additional scripts to analyze coverage.

See `${PROMPTS_DIR}/objective-coverage.md` for complete documentation on all coverage analysis tools and techniques.