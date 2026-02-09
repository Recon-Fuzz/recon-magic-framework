# Echidna Coverage Report Parsing Guide
**File Format**: `covered.*.txt` (Echidna plain-text coverage output)
**Purpose**: Instruct an LLM agent on how to read and interpret Echidna's human-readable coverage report.

---

## File Overview

Echidna generates a `covered.<timestamp>.txt` file when `corpusDir` is enabled in the config. This file shows **line-by-line execution coverage** with **termination status** for each covered line.

**Example**:
```text
*r  |  function set0(int val) public returns (bool){
*   |    if (val % 100 == 0)
*   |      flag0 = false;
  }

*r  |  function set1(int val) public returns (bool){
*   |    if (val % 10 == 0 && !flag0)
*   |      flag1 = false;
  }
```

## Coverage Prefix Annotations

The following table specifies the different type of annotations that may show up at the start of each line and what they mean:

| Prefix | Meaning |
|--------|---------|
| `* `   | **Executed and ended with `STOP`** – Normal successful return |
| `r `   | **Executed and ended with `REVERT`** – Transaction reverted |
| `o `   | **Executed and ran out of gas** – Out-of-gas error |
| `e `   | **Executed and hit an error** – Assertion failure, invalid opcode, etc. |
| `   `  | **Never executed** – Not covered by any fuzzing campaign |

## Critical Interpretation Rules

### 1. **Absence of Coverage Marker = Uncovered Code**
Lines that have **no prefix marker** (or only whitespace before the `|`) are **NOT COVERED**. This is true regardless of:
- Whether the line is nested inside a conditional statement (if/else/while/for)
- Whether the line is inside a function that was partially executed
- The indentation level of the code

**Example of Uncovered Nested Code**:
```text
392 | *   |         if (position[id][borrower].collateral == 0) {
393 |     |           badDebtShares = position[id][borrower].borrowShares;
394 |     |           badDebtAssets = UtilsLib.min(
395 |     |             market[id].totalBorrowAssets,
396 |     |             badDebtShares.toAssetsUp(market[id].totalBorrowAssets, market[id].totalBorrowShares)
397 |     |           );
398 |     |
399 |     |           market[id].totalBorrowAssets -= badDebtAssets.toUint128();
400 |     |           market[id].totalSupplyAssets -= badDebtAssets.toUint128();
401 |     |           market[id].totalBorrowShares -= badDebtShares.toUint128();
402 |     |           position[id][borrower].borrowShares = 0;
403 |     |         }
```

In this example:
- Line 392: **COVERED** (marked with `*`) - The conditional check `if (position[id][borrower].collateral == 0)` was executed
- Lines 393-402: **UNCOVERED** (no prefix markers) - The body of the if statement was never executed, meaning the condition was never true during fuzzing

### 2. **Conditional Branches Require Explicit Coverage**
When you see a conditional statement (if/while/for) that is covered, **do not assume** the body is also covered. You must check each line independently:

- If the condition line has a marker (`*`, `r`, etc.) → The condition was **evaluated**
- If the body lines have no marker → The branch was **not taken**

### 3. **Whitespace-Only Prefix = Uncovered**
Lines with only spaces before the `|` separator are uncovered. The pipe character `|` is the visual separator between coverage status and code content.