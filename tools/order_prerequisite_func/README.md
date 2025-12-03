# Order Prerequisite Functions Tool

This tool sorts functions in a `testing-priority.json` file based on the number of prerequisite functions they have, ordering from fewest to most prerequisites.

## Usage

```bash
python3 tools/order_prerequisite_func/order_prerequisite_func.py <path_to_testing-priority.json>
```

## Input Format

The input file should be a JSON file with the following structure:

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
python3 tools/order_prerequisite_func/order_prerequisite_func.py ./testing-priority.json
```
