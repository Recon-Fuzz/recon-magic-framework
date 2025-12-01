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


def process_target_files(targets_dir: Path, state_var_mapping: Dict[str, str]) -> Dict[str, Set[str]]:
    """
    Process all target function files and extract functions grouped by contract.

    Returns:
        Dict mapping contract names to sets of target function names
    """
    contract_functions = defaultdict(set)
    unmapped_vars = set()

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
        print(f"Processing: {sol_file.name}")

        with open(sol_file, 'r') as f:
            content = f.read()

        function_calls = extract_function_calls(content)

        for state_var, function_name in function_calls:
            if state_var in state_var_mapping:
                contract_name = state_var_mapping[state_var]
                contract_functions[contract_name].add(function_name)
            else:
                unmapped_vars.add(state_var)

    # Report unmapped variables as warnings
    if unmapped_vars:
        print(f"\nWarning: The following state variables were not found in Setup contract:")
        for var in sorted(unmapped_vars):
            print(f"  - {var}")

    return contract_functions


def generate_output(contract_functions: Dict[str, Set[str]], output_file: Path):
    """Generate the JSON output file."""
    # Convert to the required format
    output_data = []

    for contract_name in sorted(contract_functions.keys()):
        functions = sorted(contract_functions[contract_name])
        output_data.append({
            "contract": contract_name,
            "target_functions": functions
        })

    # Create output directory if it doesn't exist
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Write JSON file with pretty formatting
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"\nOutput written to: {output_file}")
    print(f"Total contracts: {len(output_data)}")
    print(f"Total unique functions: {sum(len(item['target_functions']) for item in output_data)}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract target functions from fuzzing suite contracts"
    )
    parser.add_argument(
        "--targets",
        type=Path,
        required=True,
        help="Path to directory containing target function files and Setup.sol"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file path (default: magic/target-functions.json in current directory)"
    )

    args = parser.parse_args()

    # Set default output to current working directory if not specified
    if args.output is None:
        args.output = Path.cwd() / "magic" / "target-functions.json"

    # Derive setup file path from targets directory
    setup_file = args.targets / "Setup.sol"

    # Validate inputs
    if not args.targets.exists():
        print(f"Error: Targets directory not found: {args.targets}")
        return 1

    if not setup_file.exists():
        print(f"Error: Setup file not found: {setup_file}")
        return 1

    print("=" * 60)
    print("Target Function Extraction Script")
    print("=" * 60)
    print(f"Targets directory: {args.targets}")
    print(f"Setup file: {setup_file}")
    print(f"Output file: {args.output}")
    print("=" * 60)
    print()

    # Step 1: Parse Setup contract
    print("Step 1: Parsing Setup contract...")
    state_var_mapping = parse_setup_contract(setup_file)
    print(f"Found {len(state_var_mapping)} state variables")

    # Step 2: Process target files
    print("\nStep 2: Processing target function files...")
    contract_functions = process_target_files(args.targets, state_var_mapping)

    # Step 3: Generate output
    print("\nStep 3: Generating output...")
    generate_output(contract_functions, args.output)

    print("\nDone!")
    return 0


if __name__ == "__main__":
    exit(main())
