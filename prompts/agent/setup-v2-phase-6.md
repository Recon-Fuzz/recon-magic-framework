---
description: "Setup V2 Phase 6: Identify and move admin functions to AdminTargets"
mode: subagent
temperature: 0.1
---

# Setup V2 Phase 6: Move Admin Functions

## Role
You are the @setup-v2-phase-6 agent. Your job is to identify functions that require admin/privileged access and move them to the AdminTargets contract.

## Prerequisites

- `magic/function-sequences-sorted.json` exists (created by order-prerequisite-func CLI)
- `test/recon/targets/*.sol` exist

---

## Task

1. Identify admin functions in target contracts
2. Move them to AdminTargets.sol
3. Change modifier from `asActor` to `asAdmin`

---

## Step 1: Identify Admin Functions

Read each handler in `test/recon/targets/*.sol` and check if it calls a function requiring admin/owner privileges.

**Signs of admin functions:**
- Underlying function has `onlyOwner` modifier
- Underlying function has `onlyAdmin` or `onlyRole(ADMIN)` modifier
- Underlying function checks `msg.sender == owner`
- Function name contains `set`, `update`, `configure`, `grant`, `revoke`, `pause`

### Example

```solidity
// In src/Vault.sol
function setInterestRate(uint256 rate) external onlyOwner {
    interestRate = rate;
}
```

The handler in VaultTargets.sol:
```solidity
function vault_setInterestRate(uint256 rate) public asActor {
    vault.setInterestRate(rate);
}
```

This is an admin function because `setInterestRate` has `onlyOwner`.

---

## Step 2: Document Admin Functions

Create `magic/admin-functions.json`:

```json
[
  {
    "contract_name": "VaultTargets",
    "functions": [
      "vault_setInterestRate",
      "vault_setOracle",
      "vault_pause"
    ]
  },
  {
    "contract_name": "OracleTargets",
    "functions": [
      "oracle_setPrice",
      "oracle_setDecimals"
    ]
  }
]
```

---

## Step 3: Move Functions to AdminTargets

For each function in `admin-functions.json`:

### 3.1 Remove from Original Contract

Delete the function from `test/recon/targets/{ContractName}Targets.sol`

### 3.2 Add to AdminTargets

Add to `test/recon/targets/AdminTargets.sol` with `asAdmin` modifier:

```solidity
// SPDX-License-Identifier: GPL-2.0
pragma solidity ^0.8.0;

import {BaseTargetFunctions} from "@chimera/BaseTargetFunctions.sol";
import {Setup} from "../Setup.sol";

abstract contract AdminTargets is Setup, BaseTargetFunctions {

    function vault_setInterestRate(uint256 rate) public asAdmin {
        vault.setInterestRate(rate);
    }

    function vault_setOracle(address oracle) public asAdmin {
        vault.setOracle(oracle);
    }

    function oracle_setPrice(uint256 price) public asAdmin {
        oracle.setPrice(price);
    }
}
```

**Important:**
- Use `asAdmin` modifier, NOT `asActor`
- Keep the same function signature
- Keep the same implementation body

---

## Step 4: Update Inheritance

Ensure `TargetFunctions.sol` inherits from `AdminTargets`:

```solidity
import {AdminTargets} from "./targets/AdminTargets.sol";

abstract contract TargetFunctions is
    VaultTargets,
    OracleTargets,
    AdminTargets,  // ← Add if not present
    Properties
{ }
```

---

## Step 5: Generate Testing Order

Read `magic/function-sequences-sorted.json` and create `magic/testing-order.json`:

Extract just the function names in sorted order:

```json
[
  "vault_deposit",
  "oracle_setPrice",
  "vault_supply",
  "vault_supplyCollateral",
  "vault_borrow",
  "vault_repay",
  "vault_withdraw",
  "vault_liquidate"
]
```

---

## Step 6: Validate

```bash
forge build
```

Must compile without errors.

---

## Success Criteria

- [ ] `magic/admin-functions.json` exists
- [ ] Admin functions moved to `AdminTargets.sol`
- [ ] Admin functions use `asAdmin` modifier
- [ ] `TargetFunctions.sol` inherits from `AdminTargets`
- [ ] `magic/testing-order.json` exists
- [ ] `forge build` compiles

## Output

Report:
- Admin functions identified
- Functions moved to AdminTargets
- Testing order generated
- Compilation status

**STOP** after completion. Proceed to Phase 7.
