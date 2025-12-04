#!/usr/bin/env python3
"""
Touched Function Identifier

A CLI tool to analyze sol-expand output and generate a functions-to-cover.json file
that lists all functions touched by target functions in a smart contract project.
"""

import argparse
import json
import re
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict


class TouchedFunctionIdentifier:
    """Main class to identify touched functions from sol-expand output."""

    # Contracts to exclude (proxies, reentrancy guards, authorization)
    EXCLUDED_CONTRACTS = {
        # OpenZeppelin
        'ERC1967Proxy', 'TransparentUpgradeableProxy', 'UUPSUpgradeable',
        'BeaconProxy', 'Proxy', 'ERC1967Upgrade', 'Initializable',
        'ProxyAdmin', 'UpgradeableBeacon', 'ReentrancyGuard',
        'ReentrancyGuardUpgradeable', 'Ownable', 'Ownable2Step',
        'OwnableUpgradeable', 'AccessControl', 'AccessControlEnumerable',
        'AccessControlDefaultAdminRules', 'AccessControlUpgradeable',
        'AccessManaged', 'Authority',
        # Solmate
        'Auth', 'Owned', 'RolesAuthority', 'MultiRolesAuthority',
        # Solady
        'OwnableRoles', 'ReentrancyGuardTransient'
    }

    def __init__(self, sol_expand_dir: Path, target_functions_file: Path, output_file: Path):
        """Initialize the identifier with paths."""
        self.sol_expand_dir = sol_expand_dir
        self.target_functions_file = target_functions_file
        self.output_file = output_file
        self.project_root = sol_expand_dir.parent

        # Data structures
        self.target_functions: List[Dict] = []
        self.functions_to_cover: Dict[str, Set[str]] = defaultdict(set)
        self.contract_type_cache: Dict[str, str] = {}

    def load_target_functions(self) -> None:
        """Load the target-functions.json file."""
        with open(self.target_functions_file, 'r') as f:
            self.target_functions = json.load(f)
        print(f"✓ Loaded {len(self.target_functions)} contract(s) from target-functions.json")

    def find_function_file(self, contract_name: str, function_name: str) -> Optional[Path]:
        """Find the markdown file for a specific function in sol-expand output."""
        # Search pattern: context_output/*/ContractName.sol/function_functionName*.md
        search_pattern = f"**/{contract_name}.sol/function_{function_name}_*.md"

        matches = list(self.sol_expand_dir.glob(search_pattern))
        if not matches:
            # Try without parameters (for functions with no args)
            search_pattern = f"**/{contract_name}.sol/function_{function_name}.md"
            matches = list(self.sol_expand_dir.glob(search_pattern))

        if matches:
            return matches[0]  # Return first match
        return None

    def parse_call_tree(self, function_file: Path) -> List[Tuple[str, str]]:
        """
        Parse the call tree from a function markdown file.
        Returns list of (contract_name, function_name) tuples.
        """
        with open(function_file, 'r') as f:
            content = f.read()

        # Find the Call Tree section
        call_tree_match = re.search(r'## Call Tree\s*```(.*?)```', content, re.DOTALL)
        if not call_tree_match:
            return []

        call_tree = call_tree_match.group(1)

        # Pattern to match function calls: ContractName.functionName(...)
        # Example: MathLib.wMulDown(uint256,uint256)
        pattern = r'FUNCTION:\s+([A-Za-z_][A-Za-z0-9_]*?)\.([A-Za-z_][A-Za-z0-9_]*)\('

        matches = re.findall(pattern, call_tree)
        return matches

    def get_contract_type(self, contract_name: str) -> str:
        """
        Determine if a contract is an interface, library, or regular contract.
        Returns: 'interface', 'library', or 'contract'
        """
        # Check cache first
        if contract_name in self.contract_type_cache:
            return self.contract_type_cache[contract_name]

        # Search for the contract file in the project (prioritize src/ directory)
        search_patterns = [
            f"src/**/{contract_name}.sol",
            f"contracts/**/{contract_name}.sol",
            f"**/{contract_name}.sol"
        ]

        contract_file = None
        for pattern in search_patterns:
            matches = list(self.project_root.glob(pattern))
            # Filter out directories and files in build/out directories
            matches = [m for m in matches if m.is_file() and
                      not any(part in ['out', 'build', 'artifacts', 'cache']
                             for part in m.parts)]
            if matches:
                contract_file = matches[0]
                break

        if not contract_file or not contract_file.exists():
            # If we can't find the file, assume it's a contract (safest default)
            self.contract_type_cache[contract_name] = 'contract'
            return 'contract'

        # Read the file and check the declaration
        try:
            with open(contract_file, 'r') as f:
                content = f.read()

            # Look for interface/library/contract declarations
            if re.search(rf'\binterface\s+{contract_name}\s*{{', content):
                contract_type = 'interface'
            elif re.search(rf'\blibrary\s+{contract_name}\s*{{', content):
                contract_type = 'library'
            else:
                contract_type = 'contract'

            self.contract_type_cache[contract_name] = contract_type
            return contract_type
        except Exception as e:
            print(f"⚠ Warning: Could not read {contract_file}: {e}")
            self.contract_type_cache[contract_name] = 'contract'
            return 'contract'

    def should_include_contract(self, contract_name: str) -> bool:
        """Determine if a contract should be included in the output."""
        # Check if it's in the excluded list
        if contract_name in self.EXCLUDED_CONTRACTS:
            return False

        # Check if it's an interface or library
        contract_type = self.get_contract_type(contract_name)
        if contract_type in ['interface', 'library']:
            return False

        return True

    def process_target_function(self, contract_name: str, function_name: str) -> None:
        """Process a single target function and collect all touched functions."""
        # Find the function file
        function_file = self.find_function_file(contract_name, function_name)
        if not function_file:
            print(f"⚠ Warning: Could not find function file for {contract_name}.{function_name}")
            return

        print(f"  Processing {contract_name}.{function_name}")

        # Parse the call tree
        touched_functions = self.parse_call_tree(function_file)

        # Process each touched function
        for touched_contract, touched_function in touched_functions:
            if self.should_include_contract(touched_contract):
                self.functions_to_cover[touched_contract].add(touched_function)

    def process_all_targets(self) -> None:
        """Process all target functions from target-functions.json."""
        for contract_info in self.target_functions:
            contract_name = contract_info['contract']
            target_funcs = contract_info['target_functions']

            print(f"\nProcessing contract: {contract_name}")
            print(f"Target functions: {len(target_funcs)}")

            for func_name in target_funcs:
                self.process_target_function(contract_name, func_name)

    def get_output_data(self) -> dict:
        """Get the output data as a dictionary."""
        # Convert sets to sorted lists for consistent output
        output = {
            contract: {
                "functions_to_cover": sorted(list(functions))
            }
            for contract, functions in sorted(self.functions_to_cover.items())
        }
        return output

    def write_output(self, return_json: bool = False) -> None:
        """Write the functions-to-cover.json file or return JSON to stdout.

        Args:
            return_json: If True, print JSON to stdout instead of writing to file
        """
        output = self.get_output_data()

        if return_json:
            # Return JSON to stdout
            output_with_metadata = {
                "data": output,
                "summary": {
                    "contracts_found": len(output),
                    "total_functions": sum(len(v['functions_to_cover']) for v in output.values())
                }
            }
            print(json.dumps(output_with_metadata, indent=2))
        else:
            # Ensure output directory exists
            self.output_file.parent.mkdir(parents=True, exist_ok=True)

            # Write the JSON file
            with open(self.output_file, 'w') as f:
                json.dump(output, f, indent=2)

            print(f"\n✓ Successfully wrote output to {self.output_file}")
            print(f"  Found {len(output)} contracts with {sum(len(v['functions_to_cover']) for v in output.values())} total functions")

    def run(self, return_json: bool = False) -> None:
        """Main execution flow.

        Args:
            return_json: If True, print JSON to stdout instead of writing to file
        """
        if not return_json:
            print("=" * 60)
            print("Touched Function Identifier")
            print("=" * 60)

        self.load_target_functions()
        self.process_all_targets()
        self.write_output(return_json)

        if not return_json:
            print("\n" + "=" * 60)
            print("Done!")
            print("=" * 60)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Identify touched functions from sol-expand output',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  python touched_function_identifier.py \\
    --sol-expand-dir morpho-blue/context_output \\
    --target-functions magic/target-functions.json

  python touched_function_identifier.py \\
    --sol-expand-dir morpho-blue/context_output \\
    --target-functions magic/target-functions.json \\
    --output custom/output.json
        """
    )

    parser.add_argument(
        '--sol-expand-dir',
        type=Path,
        required=True,
        help='Directory containing the sol-expand output (e.g., morpho-blue/context_output)'
    )

    parser.add_argument(
        '--target-functions',
        type=Path,
        required=True,
        help='Path to the target-functions.json file'
    )

    parser.add_argument(
        '--output',
        type=Path,
        default=Path('magic/functions-to-cover.json'),
        help='Output file path (default: ./magic/functions-to-cover.json)'
    )

    parser.add_argument(
        '--return-json',
        action='store_true',
        help='Return JSON output to stdout instead of writing to file'
    )

    args = parser.parse_args()

    # Validate inputs
    if not args.sol_expand_dir.exists():
        print(f"Error: Sol-expand directory does not exist: {args.sol_expand_dir}")
        return 1

    if not args.target_functions.exists():
        print(f"Error: Target functions file does not exist: {args.target_functions}")
        return 1

    # Run the identifier
    identifier = TouchedFunctionIdentifier(
        args.sol_expand_dir,
        args.target_functions,
        args.output
    )

    try:
        identifier.run(args.return_json)
        return 0
    except Exception as e:
        if args.return_json:
            error_output = {
                "error": str(e),
                "success": False
            }
            print(json.dumps(error_output, indent=2))
        else:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())
