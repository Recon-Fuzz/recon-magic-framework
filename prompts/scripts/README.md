# Scripts Directory

This directory contains utility scripts for analyzing coverage and supporting the AI agent primer workflows.

## function-coverage.sh

A bash script that extracts and analyzes line coverage for specific functions within Solidity smart contracts from LCOV coverage files.

### Purpose

While `lcov` provides contract-level coverage statistics, this script provides function-level granularity, showing exactly which lines within a specific function are covered or uncovered. This is particularly useful for:

- Identifying coverage blockages at the function level
- Prioritizing which functions need improved test coverage
- Validating that handler clamping improves specific function coverage
- Tracking coverage improvements over time

### Usage

```bash
./scripts/function-coverage.sh <lcov_file> <contract_name> <function_name> [source_file]
```

**Arguments:**
- `lcov_file` - Path to the LCOV file (e.g., `echidna/coverage.1234567890.lcov`)
- `contract_name` - Name of the contract (e.g., `Morpho.sol`)
- `function_name` - Name of the function to analyze (e.g., `borrow`)
- `source_file` - (Optional) Path to the source .sol file for accurate function end line detection

### Examples

**Basic usage (function end estimated):**
```bash
./scripts/function-coverage.sh echidna/coverage.1234567890.lcov Morpho.sol borrow
```

**With source file (recommended for accurate results):**
```bash
./scripts/function-coverage.sh echidna/coverage.1234567890.lcov Morpho.sol borrow src/Morpho.sol
```

### Output

The script provides:

1. **Function Details**: Name, start line, times called, end line
2. **Coverage Summary**: Total lines, covered lines, uncovered lines, coverage percentage
3. **Detailed Line Coverage**: Line-by-line breakdown with hit counts and coverage status

**Example output:**
```
Analyzing coverage for function 'borrow' in Morpho.sol...

Function Details:
  Name: borrow
  Start Line: 200
  Times Called: 5
  End Line: 249

Line Coverage Analysis:
  Total Lines: 8
  Covered Lines: 5
  Uncovered Lines: 3
  Coverage: 62.50%

Detailed Line Coverage:
  Line | Hits | Status
  -----|------|--------
  200  | 5    | ✓ covered
  201  | 5    | ✓ covered
  202  | 0    | ✗ not covered
  203  | 5    | ✓ covered
  204  | 5    | ✓ covered
  205  | 0    | ✗ not covered
  206  | 0    | ✗ not covered
  207  | 5    | ✓ covered
```

### Color Coding

- **Green** (≥80%): Good coverage
- **Yellow** (≥50%): Moderate coverage
- **Red** (<50%): Poor coverage

### Error Handling

The script provides helpful error messages for common issues:

**Contract not found:**
```
Error: Contract 'NonExistent.sol' not found in LCOV file

Available contracts in LCOV file:
  /path/to/Morpho.sol
  /path/to/Vault.sol
```

**Function not found:**
```
Error: Function 'nonexistent' not found in Morpho.sol

Available functions in Morpho.sol:
  borrow
  liquidate
  repay
  supply
  withdraw
```

### Technical Details

**How it works:**

1. Extracts the contract section from the LCOV file (between `SF:` and `end_of_record`)
2. Finds the function start line from `FN:` entries
3. Determines function end line:
   - If source file provided: parses brace matching to find exact end
   - Otherwise: estimates using next function start or last coverage line
4. Extracts `DA:` (line data) entries for lines within the function range
5. Calculates coverage percentage: `(lines_hit / total_lines) * 100`
6. Displays results with color-coded output

**Dependencies:**
- Standard Unix tools: `bash`, `awk`, `grep`, `sed`
- No additional installations required

### Limitations

- Function end line estimation may be approximate if source file is not provided
- Assumes standard Solidity function formatting with braces
- Color output requires terminal with ANSI color support

### Testing

A sample test file is included for validation:

```bash
./scripts/function-coverage.sh scripts/test-coverage.lcov Morpho.sol borrow
```

This demonstrates the script's functionality with synthetic coverage data.

## See Also

- [objective-coverage.md](../objective-coverage.md) - Comprehensive guide to LCOV coverage analysis
- [improving-coverage.md](../improving-coverage.md) - Workflow for improving fuzzer coverage
