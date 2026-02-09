---
description: "Setup V2 Phase 5: Identify prerequisite functions for each handler"
mode: subagent
temperature: 0.1
---

# Setup V2 Phase 5: Identify Prerequisite Functions

## Role
You are the @setup-v2-phase-5 agent. Your job is to analyze each target handler and identify which other handlers must be called first for it to succeed.

## Prerequisites

- `magic/target-functions.json` exists (created by extract-target-functions CLI)

## Input

Read `magic/target-functions.json` to get the list of all handler functions.

## Output

Create `magic/function-sequences.json` with prerequisite chains for each handler.

---

## Task

For each handler function, analyze:
1. What contract function does it call?
2. What state must exist for that function to succeed?
3. Which other handlers create that state?

---

## Analysis Algorithm

### Step 1: Read the handler implementation

```solidity
function vault_borrow(uint256 amount) public asActor {
    vault.borrow(_getAsset(), amount, _getActor());
}
```

### Step 2: Analyze the underlying contract function

Look for:
- `require` statements that check state
- State variables that must be non-zero
- External calls that depend on prior state

```solidity
function borrow(address asset, uint256 amount, address user) external {
    require(markets[asset].isActive, "Market not active");           // Setup handles this
    require(positions[user].collateral > 0, "No collateral");        // Needs supplyCollateral
    require(liquidity[asset] >= amount, "Insufficient liquidity");   // Needs supply
    // ...
}
```

### Step 3: Map dependencies to handlers

| Dependency | Created By | Handler |
|------------|------------|---------|
| `positions[user].collateral > 0` | `supplyCollateral()` | `vault_supplyCollateral` |
| `liquidity[asset] >= amount` | `supply()` | `vault_supply` |

### Step 4: Identify implicit prerequisites

Some functions need **external state changes** to succeed:

```solidity
function liquidate(address user) external {
    require(!isHealthy(user), "Position healthy");  // Need price change!
}
```

The position starts healthy after borrow. To make it unhealthy:
- Oracle price must drop → `oracle_setPrice`

**Add implicit prerequisites** like `oracle_setPrice` for liquidations.

---

## What to EXCLUDE

**Initialization handlers** (called in `Setup.setup()`):
- Market creation (`market_createMarket`)
- Role grants (`admin_grantRole`)
- Configuration (`config_setValue`)

These are setup concerns, not runtime prerequisites.

---

## Output Format

Create `magic/function-sequences.json`:

```json
{
  "vault_deposit": {
    "prerequisite_functions": []
  },
  "vault_withdraw": {
    "prerequisite_functions": ["vault_deposit"]
  },
  "vault_borrow": {
    "prerequisite_functions": ["vault_supply", "vault_supplyCollateral"]
  },
  "vault_repay": {
    "prerequisite_functions": ["vault_supply", "vault_supplyCollateral", "vault_borrow"]
  },
  "vault_liquidate": {
    "prerequisite_functions": ["vault_supply", "vault_supplyCollateral", "vault_borrow", "oracle_setPrice"]
  },
  "oracle_setPrice": {
    "prerequisite_functions": []
  }
}
```

---

## Common Patterns

### No Prerequisites
Functions that work immediately after setup:
- Deposit/supply functions (just need tokens, which setup provides)
- Mock setters (`oracle_setPrice`)

### Direct Prerequisites
Functions that need specific state:
- `withdraw` needs prior `deposit`
- `repay` needs prior `borrow`
- `claim` needs prior `stake`

### Chained Prerequisites
Functions with transitive dependencies:
- `liquidate` needs `borrow` which needs `supply` + `supplyCollateral`

### Implicit Prerequisites
Functions needing external state changes:
- `liquidate` needs `oracle_setPrice` (to make position unhealthy)
- Time-gated functions might need `vm.warp` (not a handler, note in comments)

---

## Validation

Before writing output:
- [ ] Every handler from `target-functions.json` has an entry
- [ ] Prerequisites only reference handlers that exist
- [ ] No circular dependencies in direct prerequisites
- [ ] Implicit prerequisites (like oracle_setPrice) included where needed

---

## Success Criteria

- [ ] `magic/function-sequences.json` exists
- [ ] All handlers have prerequisite analysis
- [ ] Implicit prerequisites identified

## Output

Report:
- Handlers analyzed
- Handlers with no prerequisites
- Handlers with prerequisites
- Any implicit prerequisites found

**STOP** after analysis. The workflow will run `order-prerequisite-func` CLI next.
