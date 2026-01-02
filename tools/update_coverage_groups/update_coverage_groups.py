#!/usr/bin/env python3
"""
Update Coverage Groups Tool

This tool compares the most recent functions-missing-coverage file with the
previously created functions-missing-coverage-grouped file to:
1. Remove functions that are now covered (exist in grouped but not in latest)
2. Append new uncovered functions to the end (exist in latest but not in grouped)

The main objective is to maintain an up-to-date grouped file by removing
previously uncovered functions that are now covered in the latest run.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any


def find_latest_files(magic_dir: Path) -> Tuple[Optional[Path], Optional[Path]]:
    """
    Find the most recent coverage and grouped coverage files.

    Returns:
        Tuple of (latest_coverage_file, latest_grouped_file)
    """
    # Pattern for coverage files (excluding -grouped- and -latest)
    coverage_pattern = re.compile(r"functions-missing-covg-(\d+)\.json$")
    grouped_pattern = re.compile(r"functions-missing-covg-grouped-(\d+)\.json$")

    coverage_files = []
    grouped_files = []

    for file in magic_dir.glob("functions-missing-covg-*.json"):
        filename = file.name

        # Skip -latest files
        if "-latest" in filename:
            continue

        # Check if it's a grouped file
        if "-grouped-" in filename:
            match = grouped_pattern.match(filename)
            if match:
                timestamp = int(match.group(1))
                grouped_files.append((timestamp, file))
        else:
            # Regular coverage file
            match = coverage_pattern.match(filename)
            if match:
                timestamp = int(match.group(1))
                coverage_files.append((timestamp, file))

    # Sort by timestamp (newest first)
    coverage_files.sort(reverse=True)
    grouped_files.sort(reverse=True)

    latest_coverage = coverage_files[0][1] if coverage_files else None

    # For grouped files, skip any that have the same timestamp as the latest coverage
    # This ensures we compare with the previous grouped file, not one just created
    latest_grouped = None
    if latest_coverage and grouped_files:
        latest_coverage_timestamp = coverage_files[0][0]
        for timestamp, file in grouped_files:
            if timestamp < latest_coverage_timestamp:
                latest_grouped = file
                break
    elif grouped_files:
        # If no latest coverage file, just take the most recent grouped
        latest_grouped = grouped_files[0][1]

    return latest_coverage, latest_grouped


def extract_function_key(func_data: Dict) -> str:
    """
    Create a unique identifier for a function based on its signature and uncovered code.

    The key combines:
    - function name
    - contract name
    - source file
    - uncovered line ranges (sorted for consistency)
    """
    parts = [
        func_data.get("function", ""),
        func_data.get("contract", ""),
        func_data.get("source_file", "")
    ]

    # Add uncovered line ranges as part of the key
    uncovered_ranges = []
    uncovered_code = func_data.get("uncovered_code")

    # Handle different formats of uncovered_code
    if uncovered_code:
        if isinstance(uncovered_code, dict):
            # Single uncovered code section (standard format)
            uncovered_ranges.append(uncovered_code.get("line_range", ""))
        elif isinstance(uncovered_code, list):
            # Multiple uncovered code sections (alternative format)
            for chunk in uncovered_code:
                if isinstance(chunk, dict):
                    uncovered_ranges.append(chunk.get("line_range", ""))

    # Sort ranges for consistent keys
    uncovered_ranges.sort()
    parts.append("|".join(uncovered_ranges))

    return "::".join(parts)


def extract_functions_from_grouped(grouped_data: Dict) -> List[Dict]:
    """
    Extract all functions from a grouped coverage file.
    Handles both flat and grouped structures.
    """
    functions = []

    for item in grouped_data.get("missing_coverage", []):
        if "functions" in item:
            # Grouped format with group_name, group_description, and functions array
            for func in item.get("functions", []):
                # Preserve the group information with the function
                func_with_group = func.copy()
                func_with_group["_group_name"] = item.get("group_name", "")
                func_with_group["_group_description"] = item.get("group_description", "")
                functions.append(func_with_group)
        else:
            # Flat format - function directly in missing_coverage
            functions.append(item)

    return functions


def compare_coverage(
    latest_data: Dict,
    grouped_data: Dict,
    verbose: bool = False
) -> Tuple[List[Dict], List[Dict], List[Dict], Dict]:
    """
    Compare latest coverage with grouped coverage to find differences.

    Returns:
        Tuple of (retained_functions, removed_functions, new_functions, groups_map)
    """
    # Create lookup sets based on function keys
    latest_keys = {}
    grouped_keys = {}
    groups_map = {}  # Track which functions belong to which groups

    # Build lookup for latest coverage
    for func in latest_data.get("missing_coverage", []):
        key = extract_function_key(func)
        latest_keys[key] = func
        if verbose:
            print(f"Latest key: {key}")

    # Build lookup for grouped coverage - extract functions from groups
    grouped_functions = extract_functions_from_grouped(grouped_data)
    for func in grouped_functions:
        key = extract_function_key(func)
        grouped_keys[key] = func
        # Track group membership
        if "_group_name" in func:
            groups_map[key] = {
                "group_name": func.get("_group_name"),
                "group_description": func.get("_group_description")
            }
        if verbose:
            print(f"Grouped key: {key}")

    # Find functions to keep (still uncovered)
    retained_functions = []
    for key, func in grouped_keys.items():
        if key in latest_keys:
            # Function is still uncovered, keep it with existing analysis
            # Remove temporary group markers
            func_copy = func.copy()
            func_copy.pop("_group_name", None)
            func_copy.pop("_group_description", None)
            retained_functions.append(func_copy)
            if verbose:
                print(f"Retaining: {func.get('function')} in {func.get('contract')}")

    # Find functions that are now covered (to be removed)
    removed_functions = []
    for key, func in grouped_keys.items():
        if key not in latest_keys:
            removed_functions.append(func)
            if verbose:
                print(f"Removing (now covered): {func.get('function')} in {func.get('contract')}")

    # Find new uncovered functions to append
    new_functions = []
    for key, func in latest_keys.items():
        if key not in grouped_keys:
            # New uncovered function - will be appended without analysis field
            # Make a copy to avoid modifying original
            new_func = json.loads(json.dumps(func))
            # Ensure no analysis field (will be added by coverage-phase-4 agent)
            if "analysis" in new_func:
                del new_func["analysis"]
            new_functions.append(new_func)
            if verbose:
                print(f"Adding new: {func.get('function')} in {func.get('contract')}")

    return retained_functions, removed_functions, new_functions, groups_map


def reconstruct_groups(
    retained_functions: List[Dict],
    new_functions: List[Dict],
    groups_map: Dict,
    grouped_data: Dict
) -> List[Dict]:
    """
    Reconstruct the grouped structure, preserving existing groups and adding ungrouped functions.
    """
    # Track which functions have been placed in groups
    placed_functions = set()
    result_groups = []

    # First, reconstruct existing groups with retained functions
    for group in grouped_data.get("missing_coverage", []):
        if "functions" in group:
            # This is a group structure
            group_functions = []
            for func in group.get("functions", []):
                func_key = extract_function_key(func)
                # Check if this function is in retained_functions
                for retained_func in retained_functions:
                    if extract_function_key(retained_func) == func_key:
                        group_functions.append(retained_func)
                        placed_functions.add(func_key)
                        break

            # Only include the group if it still has functions
            if group_functions:
                result_groups.append({
                    "group_name": group.get("group_name", ""),
                    "group_description": group.get("group_description", ""),
                    "functions": group_functions
                })

    # Add any retained functions that weren't in groups (shouldn't happen but handle it)
    ungrouped_retained = []
    for func in retained_functions:
        if extract_function_key(func) not in placed_functions:
            ungrouped_retained.append(func)

    # Combine ungrouped retained and new functions
    all_ungrouped = ungrouped_retained + new_functions

    # If there are ungrouped functions, add them directly (not in a group)
    # They will be grouped later by the coverage-phase-3 agent
    for func in all_ungrouped:
        result_groups.append(func)

    return result_groups


def update_grouped_file(
    grouped_data: Dict,
    retained_functions: List[Dict],
    new_functions: List[Dict],
    removed_functions: List[Dict],
    groups_map: Dict,
    latest_timestamp: str,
    latest_data: Dict
) -> Dict:
    """
    Create updated grouped file with retained and new functions.
    Preserves the group structure where applicable.
    """
    # Reconstruct the grouped structure
    missing_coverage = reconstruct_groups(
        retained_functions,
        new_functions,
        groups_map,
        grouped_data
    )

    # Start with the structure from grouped data
    updated_data = {
        "timestamp": latest_timestamp,
        "lcov_file": grouped_data.get("lcov_file", ""),
        "missing_coverage": missing_coverage,
        "summary": {}
    }

    # Count total functions (handling both grouped and ungrouped)
    total_functions = 0
    for item in missing_coverage:
        if "functions" in item:
            total_functions += len(item["functions"])
        else:
            total_functions += 1

    # Get the total functions analyzed from the latest coverage data
    functions_analyzed = latest_data.get("summary", {}).get("functions_analyzed", 0)

    updated_data["summary"] = {
        "functions_analyzed": functions_analyzed,
        "functions_missing_coverage": total_functions,
        "functions_removed_now_covered": len(removed_functions),
        "new_uncovered_functions": len(new_functions),
        "functions_retained_still_uncovered": len(retained_functions)
    }

    return updated_data


def main() -> int:
    """Main entry point for the update-coverage-groups tool."""
    parser = argparse.ArgumentParser(
        description="Update coverage groups by removing newly covered functions and appending new uncovered ones"
    )
    parser.add_argument(
        "--magic-dir",
        type=Path,
        default=Path("magic"),
        help="Directory containing coverage files (default: magic)"
    )
    parser.add_argument(
        "--return-json",
        action="store_true",
        help="Output result as JSON to stdout (for workflow integration)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    args = parser.parse_args()

    # Ensure magic directory exists
    if not args.magic_dir.exists():
        print(f"Error: Magic directory '{args.magic_dir}' does not exist", file=sys.stderr)
        return 1

    # Find the latest files
    latest_coverage_file, latest_grouped_file = find_latest_files(args.magic_dir)

    if not latest_coverage_file:
        print("Error: No functions-missing-covg-*.json files found", file=sys.stderr)
        return 1

    if not latest_grouped_file:
        print("Warning: No existing grouped file found. Nothing to update.", file=sys.stderr)
        # Return success but indicate no action taken
        if args.return_json:
            print(json.dumps({"status": "no_grouped_file", "message": "No existing grouped file to update"}))
        return 0

    if args.verbose:
        print(f"Latest coverage file: {latest_coverage_file}")
        print(f"Latest grouped file: {latest_grouped_file}")

    # Load the data
    try:
        with open(latest_coverage_file) as f:
            latest_data = json.load(f)
        with open(latest_grouped_file) as f:
            grouped_data = json.load(f)
    except Exception as e:
        print(f"Error loading files: {e}", file=sys.stderr)
        return 1

    # Extract timestamp from latest coverage file
    timestamp_match = re.search(r"-(\d+)\.json$", latest_coverage_file.name)
    if not timestamp_match:
        print(f"Error: Could not extract timestamp from {latest_coverage_file.name}", file=sys.stderr)
        return 1

    latest_timestamp = timestamp_match.group(1)

    # Compare coverage to find changes
    retained, removed, new, groups_map = compare_coverage(latest_data, grouped_data, args.verbose)

    if args.verbose:
        print(f"\nSummary:")
        print(f"  Functions retained (still uncovered): {len(retained)}")
        print(f"  Functions removed (now covered): {len(removed)}")
        print(f"  New uncovered functions: {len(new)}")

    # Create updated grouped data
    updated_data = update_grouped_file(grouped_data, retained, new, removed, groups_map, latest_timestamp, latest_data)

    # Determine output path
    output_path = args.magic_dir / f"functions-missing-covg-grouped-{latest_timestamp}.json"

    # Always write the grouped file to disk
    with open(output_path, 'w') as f:
        json.dump(updated_data, f, indent=2)

    # Output the result
    if args.return_json:
        # For workflow integration, output to stdout with the actual grouped data
        # The workflow should save this as the grouped file
        print(json.dumps(updated_data, indent=2))
    else:
        # For standalone usage, print summary
        print(f"Updated grouped file written to: {output_path}")
        print(f"  Functions retained: {len(retained)}")
        print(f"  Functions removed (now covered): {len(removed)}")
        print(f"  New functions added: {len(new)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())