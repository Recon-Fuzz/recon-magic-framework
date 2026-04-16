---
description: "Coverage Phase 2: Implements shortcut handlers"
mode: subagent
temperature: 0.1
---

# Phase 2: Creating Shortcut Handlers

## CRITICAL: Never Modify echidna.yaml
**IMPORTANT**: You must NEVER modify the `echidna.yaml` file under any circumstances. The only exception is when linking libraries, which should be handled separately. Do not add, remove, or change any configuration in this file during this phase.

## Objective
Implement shortcut functions that help the fuzzer reach full path coverage by combining prerequisites and calling target functions with parameters that satisfy specific execution path conditions.

## Input File
Read `magic/merged-paths-prerequisites.json`:
```json
{
  "targetFunction": {
    "prerequisite_functions": ["prereq1", "prereq2"],
    "paths": [
      "condition1 && condition2 && functionCall1()",
      "!condition1 && condition3 && functionCall2()"
    ]
  }
}
```

- **prerequisite_functions**: Functions to call before target to establish required state
- **paths**: Execution path conditions (joined by `&&`). Each path = one shortcut function

## Implementation Steps

### 1. For Each Target Function

Iterate through `paths` array and implement one shortcut per path.

### 2. Create Descriptive Function Name

Parse path conditions and extract 2-4 key distinguishing conditions:

**Condition → Descriptor Mapping**:
- `paramName > 0` → `by{ParamName}` (e.g., `seizedAssets > 0` → `bySeizedAssets`)
- `paramName == 0` → `no{ParamName}` (e.g., `data.length == 0` → `noCallback`)
- `position[].collateral == 0` → `badDebt` or `collateralZeroed`
- `position[].collateral != 0` → `partial`
- `data.length > 0` → `withCallback`
- `elapsed != 0` → `withTimeElapsed` or `afterAccrual`
- `market[].fee != 0` → `withFees`

**Naming**: `shortcut_{targetFunc}_{descriptor1}_{descriptor2}_{descriptor3}`

### 3. Implement Shortcut Function

**Example Input** (`merged-paths-prerequisites.json`):
```json
{
  "vault_liquidate": {
    "prerequisite_functions": [
      "vault_supply",
      "vault_supplyCollateral",
      "vault_borrow",
      "oracle_setPrice"
    ],
    "paths": [
      "elapsed != 0 && marketParams.irm != 0 && market[id].fee != 0 && seizedAssets > 0 && position[id][borrower].collateral == 0 && data.length > 0 && UtilsLib.exactlyOneZero(seizedAssets, repaidShares) && marketParams.irm.borrowRate(marketParams, market[id]) && marketParams.oracle.price() && marketParams.collateralToken.safeTransfer(msg.sender, seizedAssets) && msg.sender.onMorphoLiquidate(repaidAssets, data) && marketParams.loanToken.safeTransferFrom(msg.sender, this, repaidAssets)",
      "elapsed == 0 && seizedAssets <= 0 && position[id][borrower].collateral != 0 && data.length <= 0 && UtilsLib.exactlyOneZero(seizedAssets, repaidShares) && marketParams.oracle.price() && marketParams.collateralToken.safeTransfer(msg.sender, seizedAssets) && marketParams.loanToken.safeTransferFrom(msg.sender, this, repaidAssets)"
    ]
  }
}
```

**Implementation Pattern**:
```solidity
// PATH 0: "seizedAssets > 0 && position[].collateral == 0 && data.length > 0 && ..."
// Key distinguishing conditions: bySeizedAssets, badDebt, withCallback
function shortcut_liquidate_bySeizedAssets_badDebt_withCallback(
    uint256 supplyAmount,
    uint256 collateralAmount,
    uint256 borrowAmount,
    uint256 newPrice,
    bytes calldata data
) public {
    // 1. Call prerequisites using CLAMPED handlers
    vault_supply_clamped(supplyAmount);
    switchActor(1);
    vault_supplyCollateral_clamped(collateralAmount);
    vault_borrow_clamped(borrowAmount);

    // Make position liquidatable by changing oracle price
    oracle_setPrice(newPrice);

    // 2. Read state to determine exact values for path conditions
    Position memory pos = vault.position(defaultMarketId, _getActor());
    uint256 seizedAssets = pos.collateral; // Exact value from state to satisfy "collateral == 0"

    // 3. Call target with UNCLAMPED handler (preserve exact values)
    switchActor(0);
    vault_liquidate(defaultMarketParams, _getActor(), seizedAssets, 0, data);
}
```

### 4. Key Rules

**Handler Selection**:
- Prerequisites: Use **clamped handlers** (e.g., `market_supply_clamped`)
  - **IMPORTANT**: Clamped handlers MUST end with `_clamped` suffix
  - **IMPORTANT**: Clamped handlers should contain exactly ONE state-changing call (to the unclamped handler)
  - **IMPORTANT**: All state-changing calls in clamped handlers should be to handlers, NOT contracts
- Target function: Use **unclamped handler** when passing exact values (e.g., `market_liquidate`)
- Why: Clamped handlers apply modulo that changes values, preventing exact condition satisfaction

**Clamping Rules** (from `${PROMPTS_DIR}/clamping-handler-rules.md`):
- ALL modulo operations MUST include `+ 1`: `amount %= (balance + 1)`
- Use actors from ActorManager: `_getActor()`, `switchActor(1)`
- **Read state for exact values**: Always read from system state (e.g., `pos.collateral`, `pos.borrowShares`) - never arbitrarily multiply or divide input parameters
- For partial values, accept additional parameters and clamp to state bounds: `seizedAmount % (pos.collateral + 1)`
- Use setup state variables: `defaultMarketParams`
- Never use: require statements, conditional logic, if/else

**Exclude Initialization Functions**:
- If a prerequisite is called in `Setup.setup()` to establish a state variable (e.g., `createMarket` → `defaultMarketParams`), exclude it from shortcuts
- Use the state variable directly instead

**Code Location (STRICT REQUIREMENT)**:
- **CRITICAL**: Shortcut functions MUST ONLY be added to the `TargetFunctions` contract
- **NEVER** add shortcut functions to any other contract
- Add below `/// CUSTOM TARGET FUNCTIONS` marker
- Never modify below `/// AUTO GENERATED TARGET FUNCTIONS` marker
- This is a strict, non-negotiable requirement

### 5. Review

- Count check: # shortcuts = # paths
- Remove shortcuts with < 2 state-changing calls
- Verify each shortcut satisfies different path conditions

## Complete Example

**Input** (`merged-paths-prerequisites.json`):
```json
{
  "vault_liquidate": {
    "prerequisite_functions": [
      "vault_supply",
      "vault_supplyCollateral",
      "vault_borrow",
      "oracle_setPrice"
    ],
    "paths": [
      "seizedAssets > 0 && position[id][borrower].collateral == 0 && data.length > 0 && marketParams.oracle.price() && marketParams.collateralToken.safeTransfer(msg.sender, seizedAssets)",
      "seizedAssets > 0 && position[id][borrower].collateral == 0 && data.length == 0 && marketParams.oracle.price() && marketParams.collateralToken.safeTransfer(msg.sender, seizedAssets)",
      "seizedAssets > 0 && position[id][borrower].collateral != 0 && data.length > 0 && marketParams.oracle.price() && marketParams.collateralToken.safeTransfer(msg.sender, seizedAssets)",
      "repaidShares > 0 && position[id][borrower].collateral != 0 && data.length == 0 && marketParams.oracle.price()"
    ]
  }
}
```

**Output** (4 paths → 4 shortcuts):
```solidity
// PATH 0: seizedAssets > 0 && collateral == 0 && data.length > 0
function shortcut_liquidate_bySeizedAssets_badDebt_withCallback(
    uint256 supplyAmount,
    uint256 collateralAmount,
    uint256 borrowAmount,
    uint256 newPrice,
    bytes calldata data
) public {
    vault_supply_clamped(supplyAmount);
    switchActor(1);
    vault_supplyCollateral_clamped(collateralAmount);
    vault_borrow_clamped(borrowAmount);

    // Make position liquidatable by changing oracle price
    oracle_setPrice(newPrice);

    // Read exact value from state to satisfy "collateral == 0"
    Position memory pos = vault.position(defaultMarketId, _getActor());
    uint256 seizedAssets = pos.collateral; // Seize ALL → collateral becomes 0

    switchActor(0);
    vault_liquidate(defaultMarketParams, _getActor(), seizedAssets, 0, data);
}

// PATH 1: seizedAssets > 0 && collateral == 0 && data.length == 0
function shortcut_liquidate_bySeizedAssets_badDebt_noCallback(
    uint256 supplyAmount,
    uint256 collateralAmount,
    uint256 borrowAmount,
    uint256 newPrice
) public {
    vault_supply_clamped(supplyAmount);
    switchActor(1);
    vault_supplyCollateral_clamped(collateralAmount);
    vault_borrow_clamped(borrowAmount);

    // Make position liquidatable by changing oracle price
    oracle_setPrice(newPrice);

    // Read exact value from state to satisfy "collateral == 0"
    Position memory pos = vault.position(defaultMarketId, _getActor());
    uint256 seizedAssets = pos.collateral; // Seize ALL → collateral becomes 0

    switchActor(0);
    vault_liquidate(defaultMarketParams, _getActor(), seizedAssets, 0, "");
}

// PATH 2: seizedAssets > 0 && collateral != 0 && data.length > 0
function shortcut_liquidate_bySeizedAssets_partial_withCallback(
    uint256 supplyAmount,
    uint256 collateralAmount,
    uint256 borrowAmount,
    uint256 newPrice,
    uint256 seizedAmount, // Additional parameter for partial liquidation
    bytes calldata data
) public {
    vault_supply_clamped(supplyAmount);
    switchActor(1);
    vault_supplyCollateral_clamped(collateralAmount);
    vault_borrow_clamped(borrowAmount);

    // Make position liquidatable by changing oracle price
    oracle_setPrice(newPrice);

    // Read state and clamp seizedAmount to valid range that leaves collateral
    Position memory pos = vault.position(defaultMarketId, _getActor());
    uint256 seizedAssets = seizedAmount % (pos.collateral + 1); // Partial → collateral != 0

    switchActor(0);
    vault_liquidate(defaultMarketParams, _getActor(), seizedAssets, 0, data);
}

// PATH 3: repaidShares > 0 && collateral != 0 && data.length == 0
function shortcut_liquidate_byRepaidShares_partial_noCallback(
    uint256 supplyAmount,
    uint256 collateralAmount,
    uint256 borrowAmount,
    uint256 newPrice,
    uint256 repaidAmount // Additional parameter for partial liquidation
) public {
    vault_supply_clamped(supplyAmount);
    switchActor(1);
    vault_supplyCollateral_clamped(collateralAmount);
    vault_borrow_clamped(borrowAmount);

    // Make position liquidatable by changing oracle price
    oracle_setPrice(newPrice);

    // Read state and clamp repaidAmount to valid range
    Position memory pos = vault.position(defaultMarketId, _getActor());
    uint256 repaidShares = repaidAmount % (pos.borrowShares + 1); // Partial → collateral != 0

    switchActor(0);
    vault_liquidate(defaultMarketParams, _getActor(), 0, repaidShares, "");
}
```

## Step 6 - Validate Compilation

After implementing all shortcut handlers, you MUST validate that the code compiles:

1. Run `forge build -o out` using the bash tool
2. If compilation fails, carefully review the error messages
3. Fix any compilation errors in the contracts you modified
4. Repeat steps 1-3 until compilation succeeds
5. Only mark your task as complete after successful compilation

**CRITICAL**: Do not complete this phase if compilation is failing. The code must compile before proceeding to the next phase.
