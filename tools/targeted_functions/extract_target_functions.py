#!/usr/bin/env python3
"""
Target Function Extraction Script

This script extracts targeted functions from a fuzzing suite by:
1. Parsing target function contracts to find function calls
2. Mapping state variables to their contract types from Setup.sol
3. Generating a JSON output file with contracts and their target functions
"""

import re
import json
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple


def remove_comments(content: str) -> str:
    """Remove single-line and multi-line comments from Solidity code."""
    # Remove multi-line comments
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    # Remove single-line comments
    content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
    return content


def parse_setup_contract(setup_file: Path) -> Dict[str, str]:
    """
    Parse the Setup contract to extract state variable to contract type mappings.

    Returns:
        Dict mapping state variable names to their contract types
        Example: {"morpho": "Morpho", "loanToken": "ERC20Mock"}
    """
    with open(setup_file, 'r') as f:
        content = f.read()

    # Remove comments to avoid false positives
    content = remove_comments(content)

    # Pattern to match state variable declarations
    # Matches: ContractType variableName;
    # Also handles visibility modifiers like public, private, internal
    pattern = r'^\s*([A-Z][a-zA-Z0-9_]*)\s+(?:public\s+|private\s+|internal\s+)?([a-z][a-zA-Z0-9_]*)\s*;'

    state_vars = {}
    for match in re.finditer(pattern, content, re.MULTILINE):
        contract_type = match.group(1)
        var_name = match.group(2)
        state_vars[var_name] = contract_type

    return state_vars


def extract_function_calls(content: str) -> List[Tuple[str, str]]:
    """
    Extract function calls from target function contracts.

    Returns:
        List of tuples (state_variable_name, function_name)
        Example: [("morpho", "accrueInterest"), ("morpho", "borrow")]
    """
    # Remove comments
    content = remove_comments(content)

    function_calls = []

    # Pattern to match: stateVar.functionName(
    # This looks for: variable.method( where variable starts with lowercase
    pattern = r'\b([a-z][a-zA-Z0-9_]*)\s*\.\s*([a-z][a-zA-Z0-9_]*)\s*\('

    for match in re.finditer(pattern, content):
        state_var = match.group(1)
        function_name = match.group(2)
        function_calls.append((state_var, function_name))

    return function_calls


def process_target_files(targets_dir: Path, state_var_mapping: Dict[str, str], quiet: bool = False) -> Dict[str, Set[str]]:
    """
    Process all target function files and extract functions grouped by contract.

    Args:
        targets_dir: Path to the directory containing target function files
        state_var_mapping: Mapping of state variables to contract types
        quiet: If True, output to stderr instead of stdout

    Returns:
        Dict mapping contract names to sets of target function names
    """
    import sys
    output = sys.stderr if quiet else sys.stdout

    # Contracts to ignore
    IGNORED_CONTRACTS = {"DoomsdayTargets", "ManagersTargets"}

    contract_functions = defaultdict(set)
    unmapped_vars = set()
    ignored_files = []

    # Find all .sol files in the targets directory and parent directory
    sol_files = []

    # Check for targets/ subdirectory
    targets_subdir = targets_dir / "targets"
    if targets_subdir.exists():
        sol_files.extend(targets_subdir.glob("*.sol"))

    # Also check for TargetFunctions.sol in the main directory
    target_functions_file = targets_dir / "TargetFunctions.sol"
    if target_functions_file.exists():
        sol_files.append(target_functions_file)

    # If no subdirectory, just get all .sol files in the main directory
    if not sol_files:
        sol_files = list(targets_dir.glob("*.sol"))

    for sol_file in sol_files:
        # Check if this file should be ignored based on filename
        file_stem = sol_file.stem  # Gets filename without extension
        if file_stem in IGNORED_CONTRACTS:
            print(f"Skipping: {sol_file.name} (ignored contract)", file=output)
            ignored_files.append(sol_file.name)
            continue

        print(f"Processing: {sol_file.name}", file=output)

        with open(sol_file, 'r') as f:
            content = f.read()

        function_calls = extract_function_calls(content)

        for state_var, function_name in function_calls:
            if state_var in state_var_mapping:
                contract_name = state_var_mapping[state_var]
                # Also filter out any contracts that match the ignored list
                if contract_name not in IGNORED_CONTRACTS:
                    contract_functions[contract_name].add(function_name)
            else:
                unmapped_vars.add(state_var)

    # Report ignored files
    if ignored_files:
        print(f"\nIgnored {len(ignored_files)} contract(s): {', '.join(ignored_files)}", file=output)

    # Report unmapped variables as warnings
    if unmapped_vars:
        print(f"\nWarning: The following state variables were not found in Setup contract:", file=output)
        for var in sorted(unmapped_vars):
            print(f"  - {var}", file=output)

    return contract_functions


def generate_output(contract_functions: Dict[str, Set[str]], output_file: Path, return_json: bool = False):
    """Generate the JSON output file or return JSON to stdout.

    Args:
        contract_functions: Dictionary mapping contract names to sets of functions
        output_file: Path to write the output file
        return_json: If True, print JSON to stdout instead of writing to file
    """
    # Convert to the required format
    output_data = []

    for contract_name in sorted(contract_functions.keys()):
        functions = sorted(contract_functions[contract_name])
        output_data.append({
            "contract": contract_name,
            "target_functions": functions
        })

    if return_json:
        # Return JSON to stdout with metadata
        output_with_metadata = {
            "data": output_data,
            "summary": {
                "total_contracts": len(output_data),
                "total_unique_functions": sum(len(item['target_functions']) for item in output_data)
            }
        }
        print(json.dumps(output_with_metadata, indent=2))
    else:
        # Create output directory if it doesn't exist
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Write JSON file with pretty formatting
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)

        print(f"\nOutput written to: {output_file}")
        print(f"Total contracts: {len(output_data)}")
        print(f"Total unique functions: {sum(len(item['target_functions']) for item in output_data)}")


def find_recon_directory(quiet: bool = False) -> Path:
    """
    Find the recon/ directory by searching in common locations.
    Searches in the following order:
    1. ./recon (root level)
    2. */recon (one level deep)
    3. **/recon (recursively, up to 3 levels deep)

    Args:
        quiet: If True, suppress informational output

    Returns:
        Path to the recon directory

    Raises:
        FileNotFoundError if recon directory is not found
    """
    import sys
    current_dir = Path.cwd()

    # Search patterns in priority order
    search_patterns = [
        "recon",           # Root level: ./recon
        "*/recon",         # One level deep: ./test/recon, ./src/recon, etc.
        "**/recon",        # Recursive search (up to reasonable depth)
    ]

    for pattern in search_patterns:
        matches = list(current_dir.glob(pattern))

        # Filter to only directories and limit recursive search depth
        valid_matches = [
            m for m in matches
            if m.is_dir() and len(m.relative_to(current_dir).parts) <= 3
        ]

        if valid_matches:
            # If multiple matches, prefer shallower paths
            recon_dir = min(valid_matches, key=lambda p: len(p.relative_to(current_dir).parts))
            if not quiet:
                print(f"  📁 Found recon directory at: {recon_dir.relative_to(current_dir)}", file=sys.stderr)
            return recon_dir

    # No recon directory found
    raise FileNotFoundError(
        f"Error: 'recon/' directory not found in current working directory: {current_dir}\n"
        f"Searched patterns: {', '.join(search_patterns)}\n"
        f"Please ensure a 'recon/' folder exists in your project."
    )


def main():
    parser = argparse.ArgumentParser(
        description="Extract target functions from fuzzing suite contracts. "
                    "This tool automatically searches for the 'recon/' directory in the current working directory."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file path (default: magic/target-functions.json in current directory)"
    )
    parser.add_argument(
        "--return-json",
        action="store_true",
        help="Return JSON output to stdout instead of writing to file"
    )

    args = parser.parse_args()

    import sys

    # Automatically find the recon directory (quiet mode when returning JSON)
    try:
        targets_dir = find_recon_directory(quiet=args.return_json)
    except (FileNotFoundError, NotADirectoryError) as e:
        print(str(e), file=sys.stderr)
        return 1

    # Set default output to current working directory if not specified
    if args.output is None:
        args.output = Path.cwd() / "magic" / "target-functions.json"

    # Derive setup file path from targets directory
    setup_file = targets_dir / "Setup.sol"

    # Validate inputs
    if not targets_dir.exists():
        print(f"Error: Targets directory not found: {targets_dir}", file=sys.stderr)
        return 1

    if not setup_file.exists():
        print(f"Error: Setup file not found: {setup_file}", file=sys.stderr)
        return 1

    if not args.return_json:
        print("=" * 60)
        print("Target Function Extraction Script")
        print("=" * 60)
        print(f"Targets directory: {targets_dir}")
        print(f"Setup file: {setup_file}")
        print(f"Output file: {args.output}")
        print("=" * 60)
        print()

    # Step 1: Parse Setup contract
    if not args.return_json:
        print("Step 1: Parsing Setup contract...")
    state_var_mapping = parse_setup_contract(setup_file)
    if not args.return_json:
        print(f"Found {len(state_var_mapping)} state variables")

    # Step 2: Process target files
    if not args.return_json:
        print("\nStep 2: Processing target function files...")
    contract_functions = process_target_files(targets_dir, state_var_mapping, quiet=args.return_json)

    # Step 3: Generate output
    if not args.return_json:
        print("\nStep 3: Generating output...")
    generate_output(contract_functions, args.output, args.return_json)

    if not args.return_json:
        print("\nDone!")
    return 0


if __name__ == "__main__":
    exit(main())
