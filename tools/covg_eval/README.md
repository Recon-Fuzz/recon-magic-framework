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

- `magic_dir` - Directory containing `functions-to-cover.json`
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

`functions-to-cover.json`:

```json
{
  "ContractName": {
    "functions_to_cover": ["function1", "function2"]
  }
}
```

## Output

Generates `functions-missing-covg-{timestamp}.json` in the magic directory:

```json
{
  "function_name": {
    "contract": "ContractName",
    "lines_missing_covg": ["10-15", "20"]
  }
}
```

Only functions with < 100% coverage are included. Empty `{}` if all functions are fully covered.
