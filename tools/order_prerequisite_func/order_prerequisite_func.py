#!/usr/bin/env python3
"""
Script to sort functions in testing-priority.json based on prerequisite count.
Sorts functions by number of prerequisites (ascending) and restructures the output.
"""

import json
import sys
from pathlib import Path


def sort_functions_by_prerequisites(input_path: str) -> None:
    """
    Sorts functions in the input file based on prerequisite count.

    Args:
        input_path: Path to the testing-priority.json file
    """
    file_path = Path(input_path)

    if not file_path.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Read the input file
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in file: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    # Convert to list of tuples (function_name, prerequisite_functions)
    functions = []
    for key, value in data.items():
        if isinstance(value, dict):
            function_name = value.get('function_name', key)
            prerequisites = value.get('prerequisite_functions', [])
            functions.append((function_name, prerequisites))
        else:
            print(f"Warning: Skipping invalid entry: {key}", file=sys.stderr)

    # Sort by number of prerequisites (ascending)
    functions.sort(key=lambda x: len(x[1]))

    # Restructure the output
    sorted_data = {}
    for idx, (function_name, prerequisites) in enumerate(functions, start=1):
        sorted_data[str(idx)] = {
            "function_name": function_name,
            "prerequisite_functions": prerequisites
        }

    # Write back to the same file
    try:
        with open(file_path, 'w') as f:
            json.dump(sorted_data, f, indent=2)
        print(f"Successfully sorted functions in {input_path}")
    except Exception as e:
        print(f"Error writing file: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main entry point for the script."""
    if len(sys.argv) != 2:
        print("Usage: python order_prerequisite_func.py <path_to_testing-priority.json>", file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]
    sort_functions_by_prerequisites(input_path)


if __name__ == "__main__":
    main()
