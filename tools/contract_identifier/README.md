# Contract Identifier Tool

A Python script that extracts contracts of interest from a Solidity Setup contract for testing purposes.

## Overview

This tool analyzes a Setup contract and identifies all concrete contracts that are declared as state variables. It validates each contract by searching the codebase for actual contract definitions, excluding:

- Abstract contracts
- Interfaces
- Libraries
- Structs and other non-contract types

## Usage

```bash
python3 tools/contract_identifier/identify_contracts.py <path_to_setup_contract>
```

Or make it executable and run directly:

```bash
chmod +x tools/contract_identifier/identify_contracts.py
./tools/contract_identifier/identify_contracts.py <path_to_setup_contract>
```

### Example

```bash
python3 tools/contract_identifier/identify_contracts.py path/to/Setup.sol
```

## Output

The tool generates a JSON file at `magic/coverage/contracts-to-cover.json` (relative to the Setup contract's directory) with the following format:

```json
{
  "contracts": [
    "ContractName1",
    "ContractName2"
  ]
}
```

## Features

### 1. State Variable Extraction
Extracts contract type names from state variable declarations in the Setup contract:

```solidity
contract Setup {
    Token public token;        // ✓ Extracted
    Vault vault;               // ✓ Extracted (visibility optional)
    uint256 public count;      // ✗ Excluded (not a contract)
}
```

### 2. Import Alias Resolution
Handles import aliases correctly:

```solidity
import {Vault as V} from "./Vault.sol";

contract Setup {
    V public vault;  // ✓ Resolves V → Vault
}
```

### 3. Contract Validation
Searches the codebase to verify each extracted type is a concrete contract:

```solidity
// ✓ Included
contract Token { }

// ✗ Excluded
interface IToken { }
abstract contract BaseToken { }
library TokenLib { }
```

## How It Works

1. **Parse Setup Contract**: Reads and extracts state variable declarations
2. **Extract Import Aliases**: Maps aliased imports to original contract names
3. **Resolve Types**: Converts any aliases to their actual contract names
4. **Validate Contracts**: Searches `.sol` files for concrete contract definitions
5. **Generate Output**: Writes validated contract names to JSON

## Requirements

- Python 3.6+
- No external dependencies (uses only standard library)

## Test Example

The `test_contracts/` directory contains a complete test case:

```bash
python3 identify_contracts.py test_contracts/TestSetup.sol
```

This demonstrates:
- Finding concrete contracts (`Token`, `Vault`)
- Resolving aliases (`V` → `Vault`)
- Excluding interfaces (`IVault`)
- Excluding abstract contracts (`AbstractBase`)
