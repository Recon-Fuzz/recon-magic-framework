#!/usr/bin/env python3
"""
Contract Identifier Tool

Extracts contracts of interest from a Setup contract for testing purposes.
Validates that extracted contracts are actual contract definitions (not interfaces,
abstract contracts, structs, or constants).

Usage:
    python identify_contracts.py <path_to_setup_contract>
"""

import re
import sys
import json
import os
from pathlib import Path
from typing import Set, Dict, List


class ContractIdentifier:
    def __init__(self, setup_path: str, project_root: str = None):
        self.setup_path = Path(setup_path).resolve()
        if project_root:
            self.project_root = Path(project_root).resolve()
        else:
            # Auto-detect project root by looking for src/ or foundry.toml
            self.project_root = self._find_project_root()
        self.import_aliases: Dict[str, str] = {}

    def _find_project_root(self) -> Path:
        """
        Find the project root by looking for characteristic files/directories.
        Searches upward from the setup file location.
        """
        current = self.setup_path.parent

        # Search upward for src/ directory or foundry.toml
        while current != current.parent:  # Stop at filesystem root
            if (current / "src").exists() or (current / "foundry.toml").exists():
                return current
            current = current.parent

        # Fallback to setup file's parent if not found
        return self.setup_path.parent

    def extract_import_aliases(self, content: str) -> Dict[str, str]:
        """
        Extract import aliases from the Setup contract.

        Example: import {Vault as V} from "./Vault.sol";
        Returns: {"V": "Vault"}
        """
        aliases = {}

        # Pattern for named imports with aliases: import {Name as Alias, ...}
        alias_pattern = r'import\s+\{[^}]*\b(\w+)\s+as\s+(\w+)[^}]*\}\s+from'
        for match in re.finditer(alias_pattern, content):
            original_name = match.group(1)
            alias_name = match.group(2)
            aliases[alias_name] = original_name

        return aliases

    def extract_state_variables(self, content: str) -> Set[str]:
        """
        Extract state variable type names from the Setup contract.

        Looks for patterns like:
        - ContractType public variableName;
        - ContractType internal variableName;
        - ContractType private variableName;
        - ContractType variableName;
        """
        state_vars = set()

        # Find the contract definition
        contract_match = re.search(r'contract\s+\w+\s*(?:is\s+[^{]+)?\s*\{', content)
        if not contract_match:
            return state_vars

        # Extract the contract body
        start_idx = contract_match.end()
        brace_count = 1
        end_idx = start_idx

        for i in range(start_idx, len(content)):
            if content[i] == '{':
                brace_count += 1
            elif content[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i
                    break

        contract_body = content[start_idx:end_idx]

        # Pattern for state variable declarations
        # Matches: TypeName visibility? variableName;
        # Allows single-char type names (e.g., V for aliases)
        # Format: TypeName [visibility] variableName;
        state_var_pattern = r'\b([A-Z]\w*)\s+(?:public|private|internal)?\s*(\w+)\s*;'

        for match in re.finditer(state_var_pattern, contract_body, re.MULTILINE):
            type_name = match.group(1)

            # Skip common non-contract types and Solidity structs
            skip_types = {'MarketParams', 'Id', 'uint256', 'address', 'bool', 'string', 'bytes32', 'bytes', 'uint', 'int'}
            if type_name in skip_types:
                continue

            state_vars.add(type_name)

        return state_vars

    def resolve_aliases(self, type_names: Set[str]) -> Set[str]:
        """
        Resolve any aliased type names to their original names.
        """
        resolved = set()

        for type_name in type_names:
            # If it's an alias, use the original name
            if type_name in self.import_aliases:
                resolved.add(self.import_aliases[type_name])
            else:
                resolved.add(type_name)

        return resolved

    def find_contract_definition(self, contract_name: str) -> bool:
        """
        Search the codebase for an actual contract definition.

        Returns True if found a non-abstract, non-interface contract definition.
        Excludes:
        - abstract contract ContractName
        - interface ContractName
        - library ContractName
        """
        # Search for the pattern in all .sol files
        sol_files = list(self.project_root.rglob("*.sol"))

        # Patterns to match
        concrete_contract_pattern = rf'\bcontract\s+{re.escape(contract_name)}\b'
        abstract_pattern = rf'\babstract\s+contract\s+{re.escape(contract_name)}\b'
        interface_pattern = rf'\binterface\s+{re.escape(contract_name)}\b'
        library_pattern = rf'\blibrary\s+{re.escape(contract_name)}\b'

        for sol_file in sol_files:
            try:
                with open(sol_file, 'r', encoding='utf-8') as f:
                    file_content = f.read()

                    # Check if it's an abstract contract, interface, or library
                    if re.search(abstract_pattern, file_content):
                        return False
                    if re.search(interface_pattern, file_content):
                        return False
                    if re.search(library_pattern, file_content):
                        return False

                    # Check if it's a concrete contract
                    if re.search(concrete_contract_pattern, file_content):
                        return True

            except (IOError, UnicodeDecodeError):
                continue

        return False

    def identify_contracts(self) -> List[str]:
        """
        Main method to identify contracts from the Setup contract.

        Returns a list of validated contract names.
        """
        # Read the Setup contract
        with open(self.setup_path, 'r', encoding='utf-8') as f:
            setup_content = f.read()

        # Extract import aliases
        self.import_aliases = self.extract_import_aliases(setup_content)

        # Extract state variable type names
        type_names = self.extract_state_variables(setup_content)

        # Resolve any aliases
        resolved_names = self.resolve_aliases(type_names)

        # Validate that each is an actual contract
        validated_contracts = []
        for contract_name in sorted(resolved_names):
            if self.find_contract_definition(contract_name):
                validated_contracts.append(contract_name)

        return validated_contracts

    def write_output(self, contracts: List[str], output_path: str = None):
        """
        Write the validated contracts to a JSON file.
        """
        if output_path is None:
            output_path = self.project_root / "magic" / "coverage" / "contracts-to-cover.json"
        else:
            output_path = Path(output_path)

        # Create directories if they don't exist
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write the JSON output
        output_data = {
            "contracts": contracts
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)

        return output_path


def main():
    if len(sys.argv) < 2:
        print("Usage: python identify_contracts.py <path_to_setup_contract>")
        sys.exit(1)

    setup_path = sys.argv[1]

    if not os.path.exists(setup_path):
        print(f"Error: Setup contract not found at {setup_path}")
        sys.exit(1)

    # Initialize the identifier
    identifier = ContractIdentifier(setup_path)

    # Identify contracts
    print(f"Analyzing Setup contract: {setup_path}")
    contracts = identifier.identify_contracts()

    # Write output
    output_path = identifier.write_output(contracts)

    print(f"\nFound {len(contracts)} contracts:")
    for contract in contracts:
        print(f"  - {contract}")

    print(f"\nOutput written to: {output_path}")


if __name__ == "__main__":
    main()
