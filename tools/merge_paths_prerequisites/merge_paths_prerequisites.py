#!/usr/bin/env python3
"""
Script to merge paths and prerequisites for target functions.
Combines output from recon-generate paths and setup-phase-1 agent.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any


def merge_paths_and_prerequisites(
    paths_file: str,
    prerequisites_file: str,
    output_file: str = None,
    return_json: bool = False
) -> None:
    """
    Merges paths and prerequisites into a unified structure.

    Args:
        paths_file: Path to the recon-paths.json file
        prerequisites_file: Path to the function-sequences.json file
        output_file: Optional path to write merged output
        return_json: If True, print merged data to stdout instead of writing to file

    Returns:
        None
    """
    paths_path = Path(paths_file)
    prereqs_path = Path(prerequisites_file)

    # Validate input files exist
    if not paths_path.exists():
        error_msg = f"Error: Paths file not found: {paths_file}"
        print(error_msg, file=sys.stderr)
        sys.exit(1)

    if not prereqs_path.exists():
        error_msg = f"Error: Prerequisites file not found: {prerequisites_file}"
        print(error_msg, file=sys.stderr)
        sys.exit(1)

    # Read paths file
    try:
        with open(paths_path, 'r') as f:
            paths_data = json.load(f)
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON in paths file: {e}"
        print(f"Error: {error_msg}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        error_msg = f"Error reading paths file: {e}"
        print(f"Error: {error_msg}", file=sys.stderr)
        sys.exit(1)

    # Read prerequisites file
    try:
        with open(prereqs_path, 'r') as f:
            prereqs_data = json.load(f)
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON in prerequisites file: {e}"
        print(f"Error: {error_msg}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        error_msg = f"Error reading prerequisites file: {e}"
        print(f"Error: {error_msg}", file=sys.stderr)
        sys.exit(1)

    # Merge the data
    merged_data = {}

    # Get all unique function names from both sources
    all_functions = set()

    # Extract function names from paths data
    if isinstance(paths_data, dict):
        all_functions.update(paths_data.keys())

    # Extract function names from prerequisites data
    if isinstance(prereqs_data, dict):
        for key, value in prereqs_data.items():
            if isinstance(value, dict) and 'function_name' in value:
                all_functions.add(value['function_name'])
            elif isinstance(value, dict) and 'prerequisite_functions' in value:
                # Handle case where key is the function name
                all_functions.add(key)

    # Build merged structure
    for func_name in all_functions:
        merged_data[func_name] = {}

        # Add prerequisite_functions
        prereq_list = []
        for key, value in prereqs_data.items():
            if isinstance(value, dict):
                # Check if this entry is for our function
                if value.get('function_name') == func_name:
                    prereq_list = value.get('prerequisite_functions', [])
                    break
                elif key == func_name and 'prerequisite_functions' in value:
                    prereq_list = value.get('prerequisite_functions', [])
                    break

        merged_data[func_name]['prerequisite_functions'] = prereq_list

        # Add paths
        if func_name in paths_data:
            if isinstance(paths_data[func_name], list):
                merged_data[func_name]['paths'] = paths_data[func_name]
            elif isinstance(paths_data[func_name], dict) and 'paths' in paths_data[func_name]:
                merged_data[func_name]['paths'] = paths_data[func_name]['paths']
            else:
                merged_data[func_name]['paths'] = []
        else:
            merged_data[func_name]['paths'] = []

    # Return JSON or write to file
    if return_json:
        print(json.dumps(merged_data, indent=2))
    else:
        # Determine output path
        if output_file:
            output_path = Path(output_file)
        else:
            # Default to magic/merged-paths-prerequisites.json
            output_path = Path("magic/merged-paths-prerequisites.json")

        # Write merged data
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(merged_data, f, indent=2)
            print(f"Successfully merged paths and prerequisites to {output_path}")
        except Exception as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
            sys.exit(1)


def main():
    """Main entry point for the script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Merge paths and prerequisites for target functions"
    )
    parser.add_argument(
        "--paths-file",
        default="magic/recon-paths.json",
        help="Path to the recon-paths.json file (default: magic/recon-paths.json)"
    )
    parser.add_argument(
        "--prerequisites-file",
        default="magic/function-sequences.json",
        help="Path to the function-sequences.json file (default: magic/function-sequences.json)"
    )
    parser.add_argument(
        "--output-file",
        help="Path to write merged output (default: magic/merged-paths-prerequisites.json)"
    )
    parser.add_argument(
        "--return-json",
        action="store_true",
        help="Return JSON output to stdout instead of writing to file"
    )

    args = parser.parse_args()

    merge_paths_and_prerequisites(
        args.paths_file,
        args.prerequisites_file,
        args.output_file,
        args.return_json
    )


if __name__ == "__main__":
    main()
