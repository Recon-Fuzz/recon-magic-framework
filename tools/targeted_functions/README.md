# Target Function Extraction Script

This script automatically extracts all targeted functions from a Recon fuzzing suite and generates a structured JSON output listing each contract and its associated target functions.

## Overview

When writing fuzzing campaigns with Recon/Chimera, you define target functions that wrap calls to your actual contract functions. This tool automates the extraction of those underlying contract functions for analysis and coverage tracking.

## How It Works

The script performs three main steps:

### 1. Parse Setup Contract
Reads `Setup.sol` to build a mapping of state variables to their contract types.

**Example from Setup.sol:**
```solidity
contract Setup {
    Morpho morpho;           // Maps: morpho -> Morpho
    ERC20Mock loanToken;     // Maps: loanToken -> ERC20Mock

    function setup() public {
        morpho = new Morpho(address(this));
        loanToken = new ERC20Mock();
    }
}
```

### 2. Extract Function Calls
Scans all target function contracts to find function calls made to state variables.

**Example from target files:**
```solidity
// In targets/MorphoTargets.sol
function morpho_supply(MarketParams memory marketParams, uint256 assets) public {
    morpho.supply(marketParams, assets, shares, onBehalf, data);
    // Extracts: morpho.supply -> "supply"
}

function morpho_borrow(MarketParams memory marketParams, uint256 assets) public {
    morpho.borrow(marketParams, assets, shares, onBehalf, receiver);
    // Extracts: morpho.borrow -> "borrow"
}
```

The script looks in:
- `TargetFunctions.sol` (if it exists in the targets directory)
- All `.sol` files in the `targets/` subdirectory

### 3. Generate JSON Output
Groups extracted functions by their contract type and writes to `magic/target-functions.json` in the current working directory.

**Output format:**
```json
[
  {
    "contract": "Morpho",
    "target_functions": [
      "accrueInterest",
      "borrow",
      "supply",
      "withdraw"
    ]
  },
  {
    "contract": "ERC20Mock",
    "target_functions": [
      "approve",
      "transfer"
    ]
  }
]
```

## Usage

### Basic Usage

Run from your project root directory (where you want `magic/` to be created):

```bash
cd morpho-blue  # or wherever your project root is
python3 targeted_functions/extract_target_functions.py --targets test/recon
```

This will:
1. Read `test/recon/Setup.sol` to get state variable mappings
2. Scan `test/recon/TargetFunctions.sol` and `test/recon/targets/*.sol`
3. Create `morpho-blue/magic/target-functions.json` with the results

### Command-Line Arguments

**Required:**
- `--targets <directory>` - Path to directory containing:
  - `Setup.sol` (must exist)
  - `TargetFunctions.sol` (optional)
  - `targets/` subdirectory with additional target files (optional)

**Optional:**
- `--output <path>` - Custom output file path
  - Default: `magic/target-functions.json` (relative to current directory)
  - The `magic/` directory will be created if it doesn't exist

### Examples

**Example 1: Basic usage**
```bash
cd morpho-blue
python3 targeted_functions/extract_target_functions.py --targets test/recon
# Output: morpho-blue/magic/target-functions.json
```

**Example 2: Custom output location**
```bash
python3 targeted_functions/extract_target_functions.py \
  --targets test/recon \
  --output output/functions.json
# Output: output/functions.json
```

**Example 3: Run from different directory**
```bash
cd /some/other/directory
python3 /path/to/morpho-blue/targeted_functions/extract_target_functions.py \
  --targets /path/to/morpho-blue/test/recon
# Output: /some/other/directory/magic/target-functions.json
```

## Expected Directory Structure

Your fuzzing suite should be structured like this:

```
test/recon/
├── Setup.sol                    # Required: Contains state variable declarations
├── TargetFunctions.sol          # Optional: Contains target function wrappers
├── targets/                     # Optional: Additional target files
│   ├── AdminTargets.sol
│   ├── MorphoTargets.sol
│   └── DoomsdayTargets.sol
├── Properties.sol
└── BeforeAfter.sol
```

## Pattern Matching

The script uses regex patterns to identify:

**State Variables:**
```solidity
Morpho morpho;                    // Matches: Morpho morpho
ERC20Mock public loanToken;       // Matches: ERC20Mock loanToken
IrmMock internal irm;             // Matches: IrmMock irm
```

**Function Calls:**
```solidity
morpho.supply(...)                // Extracts: supply
loanToken.transfer(...)           // Extracts: transfer
irm.borrowRate(...)               // Extracts: borrowRate
```

## Output

The script provides detailed console output:

```
============================================================
Target Function Extraction Script
============================================================
Targets directory: test/recon
Setup file: test/recon/Setup.sol
Output file: /path/to/magic/target-functions.json
============================================================

Step 1: Parsing Setup contract...
Found 7 state variables

Step 2: Processing target function files...
Processing: AdminTargets.sol
Processing: DoomsdayTargets.sol
Processing: MorphoTargets.sol
Processing: ManagersTargets.sol
Processing: TargetFunctions.sol

Step 3: Generating output...

Output written to: /path/to/magic/target-functions.json
Total contracts: 1
Total unique functions: 17

Done!
```

### Warnings

If the script encounters state variables that aren't defined in `Setup.sol`, it will display warnings:

```
Warning: The following state variables were not found in Setup contract:
  - someVariable
  - anotherVariable
```

These warnings help identify:
- Typos in state variable names
- Missing state variable declarations in Setup.sol
- Variables that might need to be added to Setup.sol

## Error Handling

The script validates inputs and provides clear error messages:

**Missing targets directory:**
```
Error: Targets directory not found: test/recon
```

**Missing Setup.sol:**
```
Error: Setup file not found: test/recon/Setup.sol
```

## Requirements

- Python 3.6 or higher (uses `pathlib`, type hints, and f-strings)
- No external dependencies (uses only Python standard library)

## Troubleshooting

**Problem:** "No such file or directory" when running the script

**Solution:** Make sure you're referencing the script path correctly:
```bash
# If you're in morpho-blue/
python3 targeted_functions/extract_target_functions.py --targets test/recon

# If you're elsewhere
python3 /full/path/to/targeted_functions/extract_target_functions.py --targets /full/path/to/test/recon
```

**Problem:** No functions extracted

**Solution:**
- Verify your target files contain function calls to state variables
- Check that state variables are declared in Setup.sol
- Look for warnings about unmapped state variables

**Problem:** Wrong contract type in output

**Solution:**
- Verify state variable declarations in Setup.sol match the actual types
- Ensure variable names in target functions match Setup.sol exactly (case-sensitive)

## Use Cases

This tool is useful for:

1. **Coverage Analysis** - Identify which contract functions are being tested
2. **Documentation** - Generate a list of all targeted functions automatically
3. **Audit Preparation** - Show auditors which functions have fuzzing coverage
4. **Gap Analysis** - Compare extracted functions against contract ABI to find untested functions
5. **Test Planning** - Verify that critical functions are included in fuzzing campaign
