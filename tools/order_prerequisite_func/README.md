# Order Prerequisite Functions Tool

This tool sorts functions in a `function-sequences.json` file based on the number of prerequisite functions they have, ordering from fewest to most prerequisites.

## Usage

```bash
python3 tools/order_prerequisite_func/order_prerequisite_func.py <path_to_function-sequences.json>
```

## Input Format

The tool accepts the `function-sequences.json` format from setup-phase-1:

```json
{
  "function_name_1": {
    "prerequisite_functions": ["prereq1", "prereq2"]
  },
  "function_name_2": {
    "prerequisite_functions": []
  }
}
```

## Output Format

The script will modify the input file in-place and restructure it as:

```json
{
  "1": {
    "function_name": "function_name_2",
    "prerequisite_functions": []
  },
  "2": {
    "function_name": "function_name_1",
    "prerequisite_functions": ["prereq1", "prereq2"]
  }
}
```

Functions are sorted by the number of prerequisites (ascending order) and numbered sequentially starting from 1.

## Example

```bash
python3 tools/order_prerequisite_func/order_prerequisite_func.py ./function-sequences.json
```
