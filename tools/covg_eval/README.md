# covg-eval

Evaluate function coverage from Echidna LCOV reports.

## Installation

```bash
uv tool install -e .
```

## Usage

```bash
covg-eval <magic_dir> <echidna_dir>
```

- `magic_dir` - Directory containing `recon-coverage.json`
- `echidna_dir` - Directory containing Echidna LCOV files (`covered.*.lcov`)

The tool automatically selects the most recent LCOV file based on timestamp.

### Example

```bash
covg-eval magic/ echidna/
```

### Verbose Output

```bash
covg-eval -v magic/ echidna/
```

## Input Format

`recon-coverage.json`:

```json
{
  "src/hub/Hub.sol": ["66-130", "133-173", "176-185"],
  "src/hub/libraries/AssetLogic.sol": ["26-31", "42-47"]
}
```

The tool parses the source files to identify which functions fall within the specified line ranges.

## Output

Generates `functions-missing-covg-{timestamp}.json` in the magic directory:

```json
{
  "function_name": {
    "contract": "ContractName",
    "source_file": "src/ContractName.sol",
    "function_range": {
      "start": 235,
      "end": 260
    },
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
}
```

### Output Fields

- **contract**: Name of the contract containing the function
- **source_file**: Full path to the source file
- **function_range**: Start and end line numbers of the function
- **uncovered_code**: Array of code chunks, where each chunk contains:
  - `line_range`: Line range string (e.g., "244-247" or "249" for single lines)
  - `code`: Array of code lines formatted as "lineNum: code content"
    - Empty/whitespace-only lines are skipped
    - Consecutive uncovered lines are grouped together

Only functions with < 100% coverage are included. Empty `{}` if all functions are fully covered.
