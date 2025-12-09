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

    def __init__(self, sol_expand_dir: Path, target_functions_file: Path, output_file: Path, quiet: bool = False):
        """Initialize the identifier with paths."""
        self.sol_expand_dir = sol_expand_dir
        self.target_functions_file = target_functions_file
        self.output_file = output_file
        self.project_root = sol_expand_dir.parent
        self.quiet = quiet

        # Data structures
        self.target_functions: List[Dict] = []
        self.functions_to_cover: Dict[str, Set[str]] = defaultdict(set)
        self.contract_type_cache: Dict[str, str] = {}

    def load_target_functions(self) -> None:
        """Load the target-functions.json file."""
        import sys
        with open(self.target_functions_file, 'r') as f:
            self.target_functions = json.load(f)
        output = sys.stderr if self.quiet else sys.stdout
        print(f"✓ Loaded {len(self.target_functions)} contract(s) from target-functions.json", file=output)

    def contract_dir_exists(self, contract_name: str) -> bool:
        """
        Check if a contract directory exists in the sol-expand output AND contains function files.

        This ensures we don't match interface directories that only have interface_*.md files.
        """
        search_pattern = f"**/{contract_name}.sol"
        matches = [m for m in self.sol_expand_dir.glob(search_pattern) if m.is_dir()]

        # Check if any match has function files (not just interface files)
        for match in matches:
            # Look for function_*.md files in the directory
            function_files = list(match.glob("function_*.md"))
            if function_files:
                return True

        return False

    def find_implementation_for_interface(self, interface_name: str) -> Optional[str]:
        """
        Find the implementation contract for a given interface by parsing contract markdown files.

        Args:
            interface_name: Name of the interface (e.g., "IBorrowerOperations")

        Returns:
            Name of the implementation contract, or None if not found
        """
        import sys
        output = sys.stderr if self.quiet else sys.stdout

        # Search all contract markdown files
        search_pattern = "**/contract_*.md"
        contract_files = self.sol_expand_dir.glob(search_pattern)

        for contract_file in contract_files:
            try:
                with open(contract_file, 'r') as f:
                    content = f.read()

                # Look for "## Implements Interfaces" section
                # Pattern: - **InterfaceName** [path]
                if f"- **{interface_name}**" in content:
                    # Extract contract name from file path
                    # e.g., context_output/src/BorrowerOperations.sol/contract_BorrowerOperations.md
                    # -> BorrowerOperations
                    match = re.search(r'/([^/]+)\.sol/contract_\1\.md$', str(contract_file))
                    if match:
                        impl_name = match.group(1)
                        print(f"✓ Mapped interface {interface_name} -> {impl_name}", file=output)
                        return impl_name
            except Exception as e:
                # Silently skip files that can't be read
                continue

        return None

    def resolve_contract_name(self, contract_name: str) -> str:
        """
        Resolve contract name, trying interface-to-implementation mapping.

        This implements a smart fallback strategy:
        1. Try the contract name as-is
        2. If not found and starts with "I", try removing "I" prefix
        3. If still not found, search for implementation in contract markdown files

        Args:
            contract_name: Original contract name (possibly an interface)

        Returns:
            Resolved contract name (implementation if interface)
        """
        import sys
        output = sys.stderr if self.quiet else sys.stdout

        # Try 1: Direct match
        if self.contract_dir_exists(contract_name):
            return contract_name

        # Try 2: Remove "I" prefix heuristic (common naming convention)
        if contract_name.startswith("I") and len(contract_name) > 1:
            impl_name = contract_name[1:]  # Remove "I"
            if self.contract_dir_exists(impl_name):
                print(f"✓ Mapped interface {contract_name} -> {impl_name} (heuristic)", file=output)
                return impl_name

        # Try 3: Search for implementation in markdown files
        impl_name = self.find_implementation_for_interface(contract_name)
        if impl_name:
            return impl_name

        # Fallback: return original name (will likely fail later, but that's expected)
        return contract_name

    def find_function_file(self, contract_name: str, function_name: str) -> Optional[Path]:
        """Find the markdown file for a specific function in sol-expand output."""
        # Resolve interface to implementation if needed
        resolved_name = self.resolve_contract_name(contract_name)

        # Search pattern: context_output/*/ContractName.sol/function_functionName*.md
        search_pattern = f"**/{resolved_name}.sol/function_{function_name}_*.md"

        matches = list(self.sol_expand_dir.glob(search_pattern))
        if not matches:
            # Try without parameters (for functions with no args)
            search_pattern = f"**/{resolved_name}.sol/function_{function_name}.md"
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
            import sys
            output = sys.stderr if self.quiet else sys.stdout
            print(f"⚠ Warning: Could not read {contract_file}: {e}", file=output)
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
        import sys
        output = sys.stderr if self.quiet else sys.stdout

        # Find the function file
        function_file = self.find_function_file(contract_name, function_name)
        if not function_file:
            print(f"⚠ Warning: Could not find function file for {contract_name}.{function_name}", file=output)
            return

        print(f"  Processing {contract_name}.{function_name}", file=output)

        # Parse the call tree
        touched_functions = self.parse_call_tree(function_file)

        # Process each touched function
        for touched_contract, touched_function in touched_functions:
            if self.should_include_contract(touched_contract):
                self.functions_to_cover[touched_contract].add(touched_function)

    def process_all_targets(self) -> None:
        """Process all target functions from target-functions.json."""
        import sys
        output = sys.stderr if self.quiet else sys.stdout

        for contract_info in self.target_functions:
            contract_name = contract_info['contract']
            target_funcs = contract_info['target_functions']

            print(f"\nProcessing contract: {contract_name}", file=output)
            print(f"Target functions: {len(target_funcs)}", file=output)

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

    import sys

    # Validate inputs
    if not args.sol_expand_dir.exists():
        print(f"Error: Sol-expand directory does not exist: {args.sol_expand_dir}", file=sys.stderr)
        return 1

    if not args.target_functions.exists():
        print(f"Error: Target functions file does not exist: {args.target_functions}", file=sys.stderr)
        return 1

    # Run the identifier
    identifier = TouchedFunctionIdentifier(
        args.sol_expand_dir,
        args.target_functions,
        args.output,
        quiet=args.return_json
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
