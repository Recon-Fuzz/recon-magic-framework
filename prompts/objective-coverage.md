# LCOV Coverage Analysis Guide for AI Agents

## Overview
This guide explains how to use the `lcov` tool to analyze line coverage for specific smart contracts from fuzzing campaigns (e.g., Echidna). The goal is to determine what percentage of a contract's code has been executed during testing.

## Understanding LCOV Files

### What is an LCOV File?
An LCOV file (typically `coverage.lcov` or `*.info`) is a standardized text format containing:
- **Line coverage**: Which lines were executed and how many times
- **Function coverage**: Which functions were called
- **Branch coverage**: Which conditional branches were taken

### LCOV File Structure
```
SF:/path/to/Contract.sol
FN:10,functionName
FNDA:5,functionName
FNF:3
FNH:2
DA:10,5
DA:11,5
DA:12,0
LF:100
LH:85
end_of_record
```

Key markers:
- `SF:` - Source file path
- `DA:line_number,hit_count` - Line execution data
- `LF:` - Lines found (total)
- `LH:` - Lines hit (covered)
- `FNF/FNH` - Functions found/hit
- `BRF/BRH` - Branches found/hit

## Core LCOV Commands

**All lcov files will be located in the `echidna/` directory and be in the format `coverage.<timestamp>.lcov`. The most recent lcov file will have the highest timestamp and should be used when running the `lcov` tool.**  

### 1. View Overall Coverage Summary
```bash
lcov --summary echidna/coverage.<timestamp>.lcov
```

**Output:**
```
Summary coverage rate:
  lines......: 85.5% (342 of 400 lines)
  functions..: 90.0% (36 of 40 functions)
  branches...: 75.0% (150 of 200 branches)
```

### 2. List All Files with Coverage
```bash
lcov --list echidna/coverage.<timestamp>.lcov
```

**Output:**
```
             |Lines       |Functions  |Branches    
Filename     |Rate     Num|Rate    Num|Rate     Num
=================================================
Contract1.sol|85.5%    200|90.0%    20|75.0%    100
Contract2.sol|92.3%    150|95.0%    15|80.0%     80
Contract3.sol|78.9%     50|85.0%     5|70.0%     20
=================================================
      Total: |85.5%    400|90.0%    40|75.0%    200
```

### 3. Extract Specific Contract Coverage

**Basic Pattern Matching:**
```bash
# Extract a single contract
lcov --extract echidna/coverage.<timestamp>.lcov '**/ContractName.sol' -o contract_coverage.info

# Then view its coverage
lcov --summary contract_coverage.info
```

**Multiple Contracts:**
```bash
# Extract multiple contracts at once
lcov --extract echidna/coverage.<timestamp>.lcov '**/Contract1.sol' '**/Contract2.sol' -o contracts_coverage.info
```

### 4. Remove Unwanted Files
```bash
# Remove test files and external libraries
lcov --remove coverage.lcov '*/test/*' '*/node_modules/*' '*/lib/*' -o filtered_coverage.info
```


## Advanced Usage

### Analyze Function-Level Coverage

For detailed analysis of coverage within specific functions, use the `function-coverage.sh` script:

```bash
# Basic usage
./scripts/function-coverage.sh echidna/coverage.<timestamp>.lcov ContractName.sol functionName

# With source file for accurate function end detection
./scripts/function-coverage.sh echidna/coverage.<timestamp>.lcov Morpho.sol borrow src/Morpho.sol
```

**Example Output:**
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

**Key Features:**
- Shows exact line-by-line coverage within the function
- Displays execution hit counts for each line
- Color-coded coverage percentage (green ≥80%, yellow ≥50%, red <50%)
- Identifies which specific lines are blocking coverage

**Use Cases:**
1. **Identify coverage blockages** - See exactly which lines within a function aren't covered
2. **Prioritize improvements** - Focus on functions with low coverage percentages
3. **Validate clamping** - Verify that handler changes improve specific function coverage
4. **Track progress** - Compare function coverage before and after making changes

### Compare Coverage Between Runs
```bash
# Run 1
lcov --extract echidna/coverage.<timestamp1>.lcov '**/Morpho.sol' -o morpho_run1.info

# Run 2
lcov --extract echidna/coverage.<timestamp2>.lcov '**/Morpho.sol' -o morpho_run2.info

# Compare
echo "Run 1:"
lcov --summary morpho_run1.info | grep lines

echo "Run 2:"
lcov --summary morpho_run2.info | grep lines
```

**Coverage should always increase as the timestamp increases.**

## Common Patterns and Wildcards

### Pattern Matching Rules
- `**/Contract.sol` - Matches Contract.sol in any directory
- `*/src/*.sol` - Matches any .sol file directly in src/
- `*/src/**/*.sol` - Matches any .sol file in src/ or subdirectories
- `/absolute/path/Contract.sol` - Exact path match

### Example Patterns
```bash
# All contracts in src directory
lcov --extract echidna/coverage.<timestamp>.lcov '*/src/*.sol' -o src_coverage.info

# Specific subdirectory
lcov --extract echidna/coverage.<timestamp>.lcov '*/src/core/*.sol' -o core_coverage.info

# Multiple specific files
lcov --extract echidna/coverage.<timestamp>.lcov \
    '**/Morpho.sol' \
    '**/Vault.sol' \
    '**/Oracle.sol' \
    -o key_contracts.info
```

## Troubleshooting

### Contract Not Found
**Problem:** Extract returns empty file
**Solutions:**
1. Check the exact path in the LCOV file:
   ```bash
   grep "SF:" coverage.lcov | grep "ContractName"
   ```
2. Try broader pattern:
   ```bash
   lcov --extract coverage.lcov '*Contract*' -o debug.info
   ```

## Best Practices for AI Agents

1. **Always validate extraction success** - Check output file is not empty
2. **Use absolute paths when possible** - More reliable than wildcards
3. **Handle missing contracts gracefully** - Some contracts may not be in coverage
4. **Cache extracted files** - Reuse for multiple analyses
5. **Clean up temporary files** - Remove intermediate .info files
6. **Log all coverage values** - Useful for tracking over time
7. **Set appropriate thresholds** - Different contracts may have different requirements
8. **Verify lcov installation** - Check version compatibility with your LCOV files

## Quick Reference Commands

```bash
# Install lcov
sudo apt-get install lcov

# View overall summary
lcov --summary echidna/coverage.<timestamp>.lcov

# List all files
lcov --list echidna/coverage.<timestamp>.lcov

# Extract specific contract
lcov --extract echidna/coverage.<timestamp>.lcov '**/Morpho.sol' -o morpho.info

# Get line coverage percentage
lcov --summary morpho.info 2>&1 | grep "lines" | awk '{print $2}'

# Analyze function-level coverage
./scripts/function-coverage.sh echidna/coverage.<timestamp>.lcov Morpho.sol borrow

```

## Summary

The `lcov` tool provides comprehensive coverage analysis capabilities for smart contracts:

- **Extract specific contracts** using `--extract` with wildcard patterns
- **View summaries** using `--summary` to see line/function/branch coverage
- **Analyze function-level coverage** using `function-coverage.sh` for detailed line-by-line analysis
- **Parse programmatically** using grep/awk or dedicated parsing libraries

For AI agents analyzing smart contract coverage, the typical workflow is:
1. Extract target contract(s) from the coverage file
2. Parse the line coverage percentage
3. **Drill down into specific functions** to identify exact lines blocking coverage
4. Compare against thresholds
5. Report results and identify gaps