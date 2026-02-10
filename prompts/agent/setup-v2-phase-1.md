---
description: "Setup V2 Phase 1: Run recon-generate to scaffold the fuzzing suite"
mode: subagent
temperature: 0.1
---

# Setup V2 Phase 1: Scaffold Fuzzing Suite

## Role
You are the @setup-v2-phase-1 agent. Your job is to run `recon-generate` to scaffold the fuzzing suite and then create any mock contracts needed.

## Prerequisites

- Phase 0 complete (Foundry compiles)
- Scout V2 complete with:
  - `magic/contracts-to-scaffold.json`
  - `magic/deployment-classification.json`

---

## Step 1: Install Chimera Dependency

Check if chimera is installed:
```bash
ls lib/chimera 2>/dev/null || echo "not installed"
```

If not installed:
```bash
forge install Recon-Fuzz/chimera --no-commit
```

---

## Step 2: Run recon-generate

Execute the scaffolding tool:
```bash
npx recon-generate@latest
```

This will:
1. Read `magic/contracts-to-scaffold.json`
2. Generate `test/recon/` directory structure:
   - `Setup.sol` - Base setup (needs implementation)
   - `TargetFunctions.sol` - Aggregates all targets
   - `Properties.sol` - Property definitions (empty)
   - `CryticToFoundry.sol` - Foundry test harness
   - `targets/` - Individual target contracts

### Expected Output Structure

```
test/recon/
├── Setup.sol
├── TargetFunctions.sol
├── Properties.sol
├── CryticToFoundry.sol
├── CryticTester.sol
└── targets/
    ├── ContractATargets.sol
    ├── ContractBTargets.sol
    └── ...
```

---

## Step 3: Verify Scaffolding

Check that files were generated:
```bash
ls test/recon/
ls test/recon/targets/
```

Read `TargetFunctions.sol` to verify it imports all target contracts.

---

## Step 4: Create Mock Contracts

Read `magic/deployment-classification.json` and for each MOCK contract, create a mock implementation.

### Mock Contract Template

For each contract in the MOCK classification:

```solidity
// SPDX-License-Identifier: GPL-2.0
pragma solidity ^0.8.0;

/// @notice Mock for {OriginalContract} - implements only methods read by SUT
contract {ContractName}Mock {
    // State variables for each getter
    {type} internal _{varName};

    // Getter (matches original interface)
    function {methodName}() external view returns ({type}) {
        return _{varName};
    }

    // Setter (for test control)
    function set{VarName}({type} value) external {
        _{varName} = value;
    }
}
```

### Example: OracleMock

From classification:
```json
{
  "name": "Oracle",
  "sutReads": ["price()", "decimals()"],
  "mockInterface": ["price() returns (uint256)", "decimals() returns (uint8)"]
}
```

Generate:
```solidity
// SPDX-License-Identifier: GPL-2.0
pragma solidity ^0.8.0;

/// @notice Mock for Oracle - implements only methods read by SUT
contract OracleMock {
    uint256 internal _price;
    uint8 internal _decimals;

    function price() external view returns (uint256) {
        return _price;
    }

    function decimals() external view returns (uint8) {
        return _decimals;
    }

    function setPrice(uint256 value) external {
        _price = value;
    }

    function setDecimals(uint8 value) external {
        _decimals = value;
    }
}
```

### Mock File Location

Create mocks in `test/recon/mocks/`:
```
test/recon/mocks/
├── OracleMock.sol
├── TokenMock.sol
└── ...
```

---

## Step 5: Add Mock Target Handlers (if needed)

If mocks have setters that should be callable during fuzzing, create target handlers:

```solidity
// test/recon/targets/MockTargets.sol
// SPDX-License-Identifier: GPL-2.0
pragma solidity ^0.8.0;

import {BaseTargetFunctions} from "@chimera/BaseTargetFunctions.sol";
import {Setup} from "../Setup.sol";

abstract contract MockTargets is Setup, BaseTargetFunctions {

    function oracle_setPrice(uint256 price) public {
        oracle.setPrice(price);
    }

    function oracle_setDecimals(uint8 decimals) public {
        oracle.setDecimals(decimals);
    }
}
```

Add MockTargets to the inheritance chain in `TargetFunctions.sol`.

---

## Step 6: Verify Compilation

Run:
```bash
forge build
```

If compilation fails, fix issues:

**Missing import:**
Add import statement to the file that needs it.

**Type mismatch:**
Check mock interface matches what SUT expects.

**Circular dependency:**
Reorder imports or use interface types.

---

## Success Criteria

Phase 1 is complete when:
- [ ] `test/recon/` structure exists
- [ ] All target contracts in `test/recon/targets/`
- [ ] All mocks in `test/recon/mocks/`
- [ ] `forge build` compiles without errors

---

## Output

Report:
- Target contracts generated
- Mock contracts created
- Any target handlers added for mocks
- Compilation status

If compilation succeeds, report: "Ready for Setup V2 Phase 2"

**STOP** after verification. Do not proceed to Phase 2.
