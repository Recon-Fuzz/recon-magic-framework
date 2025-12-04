#!/usr/bin/env python3
"""
Script to sort functions in testing-priority.json based on prerequisite count.
Sorts functions by number of prerequisites (ascending) and restructures the output.
"""

import json
import sys
from pathlib import Path


def sort_functions_by_prerequisites(input_path: str, return_json: bool = False) -> dict | None:
    """
    Sorts functions in the input file based on prerequisite count.

    Args:
        input_path: Path to the testing-priority.json file
        return_json: If True, return sorted data as dict instead of writing to file

    Returns:
        Sorted data dict if return_json is True, None otherwise
    """
    file_path = Path(input_path)

    if not file_path.exists():
        error_msg = f"Error: File not found: {input_path}"
        if return_json:
            return {"error": error_msg, "success": False}
        else:
            print(error_msg, file=sys.stderr)
            sys.exit(1)

    # Read the input file
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON in file: {e}"
        if return_json:
            return {"error": error_msg, "success": False}
        else:
            print(f"Error: {error_msg}", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        error_msg = f"Error reading file: {e}"
        if return_json:
            return {"error": error_msg, "success": False}
        else:
            print(f"Error: {error_msg}", file=sys.stderr)
            sys.exit(1)

    # Convert to list of tuples (function_name, prerequisite_functions)
    functions = []
    for key, value in data.items():
        if isinstance(value, dict):
            function_name = value.get('function_name', key)
            prerequisites = value.get('prerequisite_functions', [])
            functions.append((function_name, prerequisites))
        else:
            if not return_json:
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

    # Return JSON or write to file
    if return_json:
        return {
            "data": sorted_data,
            "summary": {
                "total_functions": len(sorted_data),
                "file_path": str(file_path)
            }
        }
    else:
        # Write back to the same file
        try:
            with open(file_path, 'w') as f:
                json.dump(sorted_data, f, indent=2)
            print(f"Successfully sorted functions in {input_path}")
        except Exception as e:
            print(f"Error writing file: {e}", file=sys.stderr)
            sys.exit(1)
        return None


def main():
    """Main entry point for the script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Sort functions in testing-priority.json by prerequisite count"
    )
    parser.add_argument(
        "input_path",
        help="Path to the testing-priority.json file"
    )
    parser.add_argument(
        "--return-json",
        action="store_true",
        help="Return JSON output to stdout instead of writing to file"
    )

    args = parser.parse_args()

    result = sort_functions_by_prerequisites(args.input_path, args.return_json)

    if args.return_json and result:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
