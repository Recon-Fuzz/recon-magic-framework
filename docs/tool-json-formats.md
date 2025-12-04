# Tool JSON Input/Output Formats

This document shows example JSON formats for all tools when using `--return-json`.

## Table of Contents
1. [extract-target-functions](#1-extract-target-functions)
2. [touched-function-identifier](#2-touched-function-identifier)
3. [covg-eval](#3-covg-eval)
4. [save-echidna-logs](#4-save-echidna-logs)
5. [order-prerequisite-func](#5-order-prerequisite-func)

---

## 1. extract-target-functions

**Command:**
```bash
extract-target-functions --targets test/recon --return-json
```

### Input Files
The tool reads from `test/recon/Setup.sol` to extract state variables.

**Example `Setup.sol` structure:**
```solidity
contract Setup {
    Morpho public morpho;
    ERC20Mock public loanToken;
    ERC20Mock public collateralToken;
}
```

### Output Format (stdout)
```json
{
  "data": [
    {
      "contract": "Morpho",
      "target_functions": [
        "accrueInterest",
        "borrow",
        "repay",
        "supply",
        "withdraw"
      ]
    },
    {
      "contract": "ERC20Mock",
      "target_functions": [
        "approve",
        "transfer",
        "transferFrom"
      ]
    }
  ],
  "summary": {
    "total_contracts": 2,
    "total_unique_functions": 8
  }
}
```

### Saved Output (when used in workflow)
When the workflow saves this with `save_to: "magic/target-functions.json"`, only the `data` array is written:

```json
[
  {
    "contract": "Morpho",
    "target_functions": [
      "accrueInterest",
      "borrow",
      "repay",
      "supply",
      "withdraw"
    ]
  },
  {
    "contract": "ERC20Mock",
    "target_functions": [
      "approve",
      "transfer",
      "transferFrom"
    ]
  }
]
```

---

## 2. touched-function-identifier

**Command:**
```bash
touched-function-identifier \
  --sol-expand-dir context_output \
  --target-functions magic/target-functions.json \
  --return-json
```

### Input: target-functions.json
```json
[
  {
    "contract": "Morpho",
    "target_functions": ["supply", "borrow"]
  }
]
```

### Output Format (stdout)
```json
{
  "data": {
    "Morpho": {
      "functions_to_cover": [
        "_accrueInterest",
        "_supply",
        "_updateState"
      ]
    },
    "MarketLib": {
      "functions_to_cover": [
        "calculateInterest",
        "totalBorrowAssets"
      ]
    },
    "SafeTransferLib": {
      "functions_to_cover": [
        "safeTransfer",
        "safeTransferFrom"
      ]
    }
  },
  "summary": {
    "contracts_found": 3,
    "total_functions": 7
  }
}
```

### Saved Output
When saved to `magic/functions-to-cover.json`, only the `data` object is written:

```json
{
  "Morpho": {
    "functions_to_cover": [
      "_accrueInterest",
      "_supply",
      "_updateState"
    ]
  },
  "MarketLib": {
    "functions_to_cover": [
      "calculateInterest",
      "totalBorrowAssets"
    ]
  },
  "SafeTransferLib": {
    "functions_to_cover": [
      "safeTransfer",
      "safeTransferFrom"
    ]
  }
}
```

---

## 3. covg-eval

**Command:**
```bash
covg-eval magic/ echidna/ --return-json
```

### Input: functions-to-cover.json
```json
{
  "Morpho": {
    "functions_to_cover": ["supply", "borrow", "_accrueInterest"]
  },
  "MarketLib": {
    "functions_to_cover": ["calculateInterest"]
  }
}
```

### Input: LCOV File
The tool reads from `echidna/covered.1234567890.lcov` (automatically finds most recent).

**LCOV format snippet:**
```
SF:src/Morpho.sol
DA:45,10
DA:46,10
DA:47,0
DA:48,0
end_of_record
```

### Output Format (stdout)
```json
{
  "timestamp": "1234567890",
  "lcov_file": "echidna/covered.1234567890.lcov",
  "missing_coverage": {
    "supply": {
      "contract": "Morpho",
      "source_file": "src/Morpho.sol",
      "function_range": {
        "start": 45,
        "end": 60
      },
      "coverage_stats": {
        "total_lines": 12,
        "covered_lines": 8,
        "uncovered_lines": 4,
        "percentage": 66.67
      },
      "uncovered_code": [
        {
          "line_range": "52-54",
          "code": [
            "52:         if (assets == 0) revert ZeroAssets();",
            "53:         if (receiver == address(0)) revert ZeroAddress();",
            "54:         _mint(receiver, shares);"
          ]
        }
      ]
    },
    "_accrueInterest": {
      "contract": "Morpho",
      "source_file": "src/Morpho.sol",
      "function_range": {
        "start": 120,
        "end": 135
      },
      "coverage_stats": {
        "total_lines": 8,
        "covered_lines": 6,
        "uncovered_lines": 2,
        "percentage": 75.0
      },
      "uncovered_code": [
        {
          "line_range": "128",
          "code": [
            "128:             emit InterestAccrued(id, newInterest);"
          ]
        }
      ]
    }
  },
  "summary": {
    "functions_analyzed": 3,
    "functions_with_missing_coverage": 2,
    "full_coverage": false
  }
}
```

### Saved Output
When saved to `magic/functions-missing-covg-{timestamp}.json`, only `missing_coverage` is written:

```json
{
  "supply": {
    "contract": "Morpho",
    "source_file": "src/Morpho.sol",
    "function_range": {
      "start": 45,
      "end": 60
    },
    "coverage_stats": {
      "total_lines": 12,
      "covered_lines": 8,
      "uncovered_lines": 4,
      "percentage": 66.67
    },
    "uncovered_code": [
      {
        "line_range": "52-54",
        "code": [
          "52:         if (assets == 0) revert ZeroAssets();",
          "53:         if (receiver == address(0)) revert ZeroAddress();",
          "54:         _mint(receiver, shares);"
        ]
      }
    ]
  },
  "_accrueInterest": {
    "contract": "Morpho",
    "source_file": "src/Morpho.sol",
    "function_range": {
      "start": 120,
      "end": 135
    },
    "coverage_stats": {
      "total_lines": 8,
      "covered_lines": 6,
      "uncovered_lines": 2,
      "percentage": 75.0
    },
    "uncovered_code": [
      {
        "line_range": "128",
        "code": [
          "128:             emit InterestAccrued(id, newInterest);"
        ]
      }
    ]
  }
}
```

**Note:** The filename uses `{timestamp}` placeholder which resolves to `1234567890` from the tool output, creating:
```
magic/functions-missing-covg-1234567890.json
```

---

## 4. save-echidna-logs

**Command:**
```bash
save-echidna-logs --return-json
```

### Input
Reads from most recent file in `logs/` matching pattern `*echidna*.log`.

**Example log file content:**
```
Analyzing contract at: ./src/MyContract.sol
echidna_test_1: passed! 🎉
echidna_test_2: failed!💥
  Call sequence:
    1. transfer(0x123, 100)
    2. approve(0x456, 50)

Coverage: 85%
```

### Output Format (stdout)
```json
{
  "log_file": "logs/20240115_143022_echidna.log",
  "parsed_data": {
    "raw_output": "Analyzing contract at: ./src/MyContract.sol\nechidna_test_1: passed! 🎉\nechidna_test_2: failed!💥\n  Call sequence:\n    1. transfer(0x123, 100)\n    2. approve(0x456, 50)\n\nCoverage: 85%",
    "success": false,
    "failed_tests": [
      "echidna_test_2: failed!💥"
    ],
    "errors": [],
    "coverage_info": null
  },
  "files_written": {}
}
```

### Saved Output
When the workflow saves this, the entire output is written (no `data` field extraction):

```json
{
  "log_file": "logs/20240115_143022_echidna.log",
  "parsed_data": {
    "raw_output": "Analyzing contract at: ./src/MyContract.sol\nechidna_test_1: passed! 🎉\nechidna_test_2: failed!💥\n  Call sequence:\n    1. transfer(0x123, 100)\n    2. approve(0x456, 50)\n\nCoverage: 85%",
    "success": false,
    "failed_tests": [
      "echidna_test_2: failed!💥"
    ],
    "errors": [],
    "coverage_info": null
  },
  "files_written": {}
}
```

---

## 5. order-prerequisite-func

**Command:**
```bash
order-prerequisite-func magic/testing-priority.json --return-json
```

### Input: testing-priority.json (unsorted)
```json
{
  "1": {
    "function_name": "supply",
    "prerequisite_functions": ["approve", "mint", "initialize"]
  },
  "2": {
    "function_name": "initialize",
    "prerequisite_functions": []
  },
  "3": {
    "function_name": "borrow",
    "prerequisite_functions": ["supply", "accrueInterest"]
  },
  "4": {
    "function_name": "approve",
    "prerequisite_functions": []
  }
}
```

### Output Format (stdout)
```json
{
  "data": {
    "1": {
      "function_name": "initialize",
      "prerequisite_functions": []
    },
    "2": {
      "function_name": "approve",
      "prerequisite_functions": []
    },
    "3": {
      "function_name": "supply",
      "prerequisite_functions": ["approve", "mint", "initialize"]
    },
    "4": {
      "function_name": "borrow",
      "prerequisite_functions": ["supply", "accrueInterest"]
    }
  },
  "summary": {
    "total_functions": 4,
    "file_path": "magic/testing-priority.json"
  }
}
```

### Saved Output
When saved, only the `data` object is written (sorted by prerequisite count):

```json
{
  "1": {
    "function_name": "initialize",
    "prerequisite_functions": []
  },
  "2": {
    "function_name": "approve",
    "prerequisite_functions": []
  },
  "3": {
    "function_name": "supply",
    "prerequisite_functions": ["approve", "mint", "initialize"]
  },
  "4": {
    "function_name": "borrow",
    "prerequisite_functions": ["supply", "accrueInterest"]
  }
}
```

---

## Common Patterns

### 1. Output Structure
All tools follow this pattern when using `--return-json`:

```json
{
  "data": <actual_output>,
  "summary": <metadata>,
  "timestamp": <optional_timestamp>
}
```

### 2. Workflow Saves Only `data`
When workflows capture and save output, they extract the `data` field:

```python
if isinstance(output_data, dict) and 'data' in output_data:
    json.dump(output_data['data'], f, indent=2)
else:
    json.dump(output_data, f, indent=2)
```

### 3. Path Template Resolution
Tools can provide fields for path templates:

```json
"save_to": "results/{timestamp}-{summary.total_functions}.json"
```

Resolves to:
```
results/1234567890-42.json
```

### 4. Error Handling
If a tool encounters an error with `--return-json`:

```json
{
  "error": "Error message describing what went wrong",
  "success": false
}
```

---

## Complete Workflow Example

Here's how data flows through the workflow:

```
Step 1: extract-target-functions --return-json
  ↓ (outputs JSON to stdout)
  ↓ (framework captures and saves 'data' field)
  ↓ magic/target-functions.json

Step 4: touched-function-identifier --return-json
  ↓ (reads magic/target-functions.json as input)
  ↓ (outputs JSON to stdout)
  ↓ (framework captures and saves 'data' field)
  ↓ magic/functions-to-cover.json

Step 9: covg-eval magic/ echidna/ --return-json
  ↓ (reads magic/functions-to-cover.json as input)
  ↓ (reads echidna/covered.*.lcov files)
  ↓ (outputs JSON with timestamp to stdout)
  ↓ (framework uses timestamp in filename)
  ↓ magic/functions-missing-covg-1234567890.json
```

Each step's output becomes the next step's input, with the workflow controlling where files are saved!
