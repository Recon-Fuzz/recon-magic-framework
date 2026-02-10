---
description: "Setup Phase 1: Identify prerequisite functions"
mode: subagent
temperature: 0.1
---

# Phase 1: Identifying Prerequisite Functions

## Objective

For each target handler function, deeply analyze the implementation code to identify which prerequisite handler functions must be called before the target can execute successfully. Store the results as a simple array of handler function names in `magic/function-sequences.json`.

**KEY PRINCIPLES**:
- Target functions in `target-functions.json` are **handler function names** (e.g., `vault_liquidate`, `vault_supply`, `vault_borrow`)
- These handlers are what the system uses to change state
- Prerequisite functions should also be **handler function names** that correspond to the state-changing operations needed
- Analyze the actual handler implementation code to understand state dependencies
- Ensure prerequisite function names are consistent with the handler naming convention used in the codebase

## Input/Output Files

**Input**: `magic/target-functions.json`
```json
[
  {
    "contract": "ContractName",
    "target_functions": ["vault_liquidate", "vault_borrow"]
  }
]
```

**Output**: `magic/function-sequences.json`
```json
{
  "vault_liquidate": {
    "prerequisite_functions": [
      "vault_supply",
      "vault_supplyCollateral",
      "vault_borrow"
    ]
  }
}
```

**Schema Notes**:
- Keys are **handler function names** from `target-functions.json` (e.g., `vault_liquidate`)
- `prerequisite_functions`: Simple array of **handler function names** that must be called before the target
- Handler names should match the naming convention used in the codebase (e.g., `vault_`, `market_`, etc.)
- ONLY analyze functions that appear in `target-functions.json`
- If a function has no prerequisites, use an empty array `[]`

## Workflow

1. Read `magic/target-functions.json` to identify all target handler functions
2. For each target handler function (e.g., `vault_liquidate`):
   - Read the handler's implementation code
   - Identify what underlying contract function it calls (e.g., `vault.liquidate()`)
   - Analyze what state must exist before that contract function can execute successfully
   - Trace back through the code to identify which state-changing operations are needed
   - Map those operations to their corresponding handler functions (e.g., `supplyCollateral` → `vault_supplyCollateral`)
   - **Exclude from sequences**:
     - Initialization functions called in `Setup.setup()` that establish meaningful values (e.g., `market_createMarket` establishing `defaultMarket`)
     - Role management functions (e.g., `admin_grantRole`)
     - Admin configuration functions (e.g., `config_setValue`)
   - Store the prerequisite handler function names as a simple array
3. Write results to `magic/function-sequences.json`

## How to Identify Prerequisites: Step-by-Step Algorithm

### Step 1: Read the target handler implementation
Get the complete source code of the target handler function you're analyzing (e.g., `vault_liquidate`).

### Step 2: Identify the underlying contract call
Look for the contract function call within the handler (e.g., `vault.liquidate(...)`).

### Step 3: Analyze state dependencies in the contract function
Look for:
- `require` statements that check state variables (e.g., `require(market[id].lastUpdate != 0)`)
- State variables that are read or modified (e.g., `position[id][onBehalf].collateral`)
- External calls that depend on prior state (e.g., `oracle.price()` might require oracle to be configured)
- **Implicit state changes needed to satisfy conditions**:
  - Health checks that depend on external data (e.g., `_isHealthy()` reading oracle price)
  - Time-dependent conditions (e.g., `block.timestamp > lastUpdate`)
  - Value comparisons against external state (e.g., collateral value vs loan value)

### Step 4: Map state dependencies to handler functions
For each state dependency, ask: "Which contract operation modifies this state, and what is its corresponding handler?"

**Example - Direct state dependencies**:
```solidity
// Handler: vault_borrow
function vault_borrow(...) internal {
    vault.borrow(marketParams, assets, ...);
}

// Contract function being called
function borrow(MarketParams memory marketParams, uint256 assets, ...) {
    Id id = marketParams.id();
    require(market[id].lastUpdate != 0, "Market not created");  // Requires createMarket
    require(position[id][borrower].collateral > 0, "No collateral");  // Requires supplyCollateral

    // More code...
}
```

From this analysis:
- `market[id].lastUpdate != 0` → requires `createMarket` → maps to `market_createMarket` handler (but this is initialization, so exclude)
- `position[id][borrower].collateral > 0` → requires `supplyCollateral` → maps to `vault_supplyCollateral` handler

**Example - Implicit state dependencies**:
```solidity
// Handler: vault_liquidate
function vault_liquidate(...) internal {
    vault.liquidate(marketParams, borrower, ...);
}

// Contract function being called
function liquidate(MarketParams memory marketParams, address borrower, ...) {
    uint256 collateralPrice = IOracle(marketParams.oracle).price();
    require(!_isHealthy(marketParams, id, borrower, collateralPrice), "HEALTHY_POSITION");
    // Liquidation logic...
}

// Health check that reads oracle price
function _isHealthy(..., uint256 collateralPrice) internal view returns (bool) {
    uint256 collateralValue = position.collateral * collateralPrice;
    uint256 borrowedValue = position.borrowed * LOAN_TOKEN_PRICE;
    return collateralValue >= borrowedValue * LLTV;
}
```

From this analysis:
- Requires position to be **unhealthy** (collateral value < borrowed value * LLTV)
- For normal borrow flow, position starts healthy
- **Implicit prerequisite**: Something must change to make position unhealthy
- Options:
  1. Change oracle price → maps to `oracle_setPrice` handler ✅
  2. Wait for time to pass and accrue interest → maps to time manipulation
- Include `oracle_setPrice` as a prerequisite for liquidate

### Step 5: Filter out initialization handlers
Before adding to the prerequisite list, check if the handler should be excluded:
- Is it called in `Setup.setup()`?
- Does it establish a state variable used for clamping (e.g., `defaultMarketParams`)?
- **If YES → SKIP this handler** (exclude from sequence)

**Initialization handlers to exclude**:
- Market/pool creation handlers called in setup (e.g., `market_createMarket`)
- Role management handlers (e.g., `admin_grantRole`)
- Admin configuration handlers (e.g., `config_setValue`)

### Step 6: Add runtime prerequisite handlers to the array
For each runtime prerequisite (not initialization), add the **handler function name** to the array, ensuring it matches the naming convention used in the codebase.

## Real Examples

**Example 1: `vault_supplyCollateral` - Simple case with no prerequisites**

```solidity
// Handler function
function vault_supplyCollateral(...) internal {
    vault.supplyCollateral(marketParams, assets, onBehalf, data);
}

// Contract function being called
function supplyCollateral(MarketParams memory marketParams, uint256 assets, address onBehalf, bytes calldata data) external {
    Id id = marketParams.id();
    require(market[id].lastUpdate != 0, ErrorsLib.MARKET_NOT_CREATED);  // Market must exist
    require(assets != 0, ErrorsLib.ZERO_ASSETS);
    require(onBehalf != address(0), ErrorsLib.ZERO_ADDRESS);

    position[id][onBehalf].collateral += assets.toUint128();
    // More code...
}
```

**Analysis:**
- Requires `market[id].lastUpdate != 0` → this means a market must exist
- `createMarket` establishes this state → maps to `market_createMarket` handler
- But `market_createMarket` is called in `Setup.setup()` (initialization), so exclude
- No runtime prerequisite handlers needed

**Output:**
```json
{
  "vault_supplyCollateral": {
    "prerequisite_functions": []
  }
}
```

---

**Example 2: `vault_borrow` - Multiple prerequisites**

```solidity
// Handler function
function vault_borrow(...) internal {
    vault.borrow(marketParams, assets, shares, onBehalf, receiver);
}

// Contract function being called
function borrow(MarketParams memory marketParams, uint256 assets, uint256 shares, address onBehalf, address receiver)
    external returns (uint256, uint256) {
    Id id = marketParams.id();
    require(market[id].lastUpdate != 0, ErrorsLib.MARKET_NOT_CREATED);  // Requires createMarket (initialization)
    require(position[id][onBehalf].collateral > 0, "No collateral");    // Requires supplyCollateral
    require(market[id].totalSupplyAssets > 0, "No liquidity");           // Requires supply

    // More code...
}
```

**Analysis:**
- `market[id].lastUpdate != 0` → requires `createMarket` → `market_createMarket` handler (but this is initialization, so exclude)
- `position[id][onBehalf].collateral > 0` → requires `supplyCollateral` → `vault_supplyCollateral` handler (runtime prerequisite)
- `market[id].totalSupplyAssets > 0` → requires `supply` → `vault_supply` handler (runtime prerequisite)

**Output:**
```json
{
  "vault_borrow": {
    "prerequisite_functions": ["vault_supply", "vault_supplyCollateral"]
  }
}
```

---

**Example 3: `vault_liquidate` - Chained prerequisites with implicit state changes**

```solidity
// Handler function
function vault_liquidate(...) internal {
    vault.liquidate(marketParams, borrower, seizedAssets, repaidShares, data);
}

// Contract function being called
function liquidate(
    MarketParams memory marketParams,
    address borrower,
    uint256 seizedAssets,
    uint256 repaidShares,
    bytes calldata data
) external returns (uint256, uint256) {
    Id id = marketParams.id();
    require(market[id].lastUpdate != 0, ErrorsLib.MARKET_NOT_CREATED);  // Requires createMarket (initialization)

    uint256 collateralPrice = IOracle(marketParams.oracle).price();
    require(!_isHealthy(marketParams, id, borrower, collateralPrice), ErrorsLib.HEALTHY_POSITION);  // Position must be unhealthy

    // For position to be unhealthy, borrower must have:
    // 1. Borrowed funds (requires borrow)
    // 2. Collateral (implicitly from borrow prerequisites)
    // 3. Changed conditions that make position unhealthy (oracle price or time)
    // More code...
}
```

**Analysis:**
- **Direct prerequisites**: Requires an unhealthy position, which means someone must have borrowed
  - `borrow` → `vault_borrow` handler
  - `vault_borrow` requires `vault_supply` and `vault_supplyCollateral`
- **Implicit prerequisite**: Position must become unhealthy
  - After borrow, position is initially healthy
  - Need to change oracle price to make collateral value drop
  - `oracle.price()` reads current price → can be changed via `oracle_setPrice` handler
- So the chain is: vault_supply + vault_supplyCollateral → vault_borrow → **oracle_setPrice** → vault_liquidate

**Output:**
```json
{
  "vault_liquidate": {
    "prerequisite_functions": ["vault_supply", "vault_supplyCollateral", "vault_borrow", "oracle_setPrice"]
  }
}
```

**Key insight**: The `oracle_setPrice` prerequisite is **implicit** - it's not directly checked in a require statement, but it's necessary to satisfy the health check condition.

---

**Example 4: Identifying implicit state changes for conditional execution**

Some functions require specific conditions to be true that aren't directly set by other functions, but require **changing external state**:

**Common patterns to look for:**

1. **Health checks reading oracle prices**:
```solidity
uint256 price = oracle.price();
require(!_isHealthy(..., price), "Position is healthy");
```
→ Requires `oracle_setPrice` to change price and make position unhealthy

2. **Time-based conditions**:
```solidity
require(block.timestamp > lastUpdate + MIN_DELAY, "Too soon");
```
→ May require time manipulation (warp) - but typically not added as prerequisite

3. **Threshold comparisons**:
```solidity
require(totalDebt > totalCollateral, "Insufficient debt");
```
→ Analyze what changes these values - may need oracle price change

4. **Protocol state flags**:
```solidity
require(market.isPaused == false, "Market paused");
```
→ Requires `admin_unpause` or similar state change

**How to identify**:
1. Look for external contract calls in conditionals (`oracle.price()`, `token.balanceOf()`)
2. Look for complex calculations in require statements
3. Trace what variables feed into the condition
4. Ask: "What external state changes would satisfy this condition?"
5. Map to corresponding handler functions

**Example - Liquidation requiring price change**:
```solidity
function liquidate(...) {
    uint256 collateralPrice = oracle.price();
    uint256 collateralValue = position.collateral * collateralPrice;
    uint256 borrowValue = position.borrowed * LOAN_PRICE;

    require(collateralValue < borrowValue * LLTV, "Position healthy");
    // Liquidation logic...
}
```

**Analysis**:
- Condition: `collateralValue < borrowValue * LLTV`
- Variables: `collateralPrice` (from oracle), `position.collateral`, `position.borrowed`
- After borrow: `collateralValue >= borrowValue * LLTV` (healthy position)
- To satisfy condition: Need `collateralPrice` to decrease
- Handler: `oracle_setPrice` changes the oracle price
- **Add `oracle_setPrice` as implicit prerequisite**

---

**Example 5: Excluding initialization handlers**

From the `Setup` contract:

```solidity
abstract contract Setup {
    MarketParams defaultMarketParams;  // State variable for clamping

    function setup() internal {
        // Creates a default market and stores it for clamping
        defaultMarketParams = MarketParams({...});
        this.market_createMarket(...);  // Calls handler in setup
    }
}
```

**Analysis:**
- `market_createMarket` handler is called in `Setup.setup()` to establish `defaultMarketParams`
- Clamped handlers use `defaultMarketParams` directly (it's already initialized)
- Don't include `market_createMarket` as a prerequisite for any target handler

**Key principle**: If a handler is called in `Setup.setup()` and establishes state used for clamping, it's initialization, not a runtime prerequisite.

---

## Summary

This simplified phase focuses on identifying the minimal set of prerequisite handler functions needed for each target handler to execute successfully. The output is a simple array of handler function names, making it easy to understand the dependency chain.

**Key Points:**
1. Work with **handler function names** (e.g., `vault_liquidate`, `vault_supply`) - these are what the system uses to change state
2. Deeply analyze handler implementation code to understand state dependencies
3. Map state dependencies to their corresponding handler functions
4. **Include implicit state changes**: Look for conditions that require external state changes (e.g., oracle price updates for liquidations)
5. Exclude initialization handlers called in `Setup.setup()`
6. Output a simple array of runtime prerequisite handler function names
7. Ensure all handler names are consistent with the naming convention used in the codebase

**Types of prerequisites to identify:**
- **Direct prerequisites**: Functions that directly modify state read by the target (e.g., `vault_supply` before `vault_borrow`)
- **Implicit prerequisites**: Functions that change external state needed to satisfy conditions (e.g., `oracle_setPrice` before `vault_liquidate`)
- **Chained prerequisites**: Prerequisites of prerequisites (e.g., `vault_supply` → `vault_borrow` → `vault_liquidate`)

**Example output:**
```json
{
  "vault_liquidate": {
    "prerequisite_functions": ["vault_supply", "vault_supplyCollateral", "vault_borrow", "oracle_setPrice"]
  }
}
```

Note: `oracle_setPrice` is an **implicit prerequisite** - it's needed to make the position unhealthy so liquidation can succeed.

The output from this phase will be used in subsequent phases to generate test shortcuts that properly set up state before calling target handlers.