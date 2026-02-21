---
description: "Phase 3A of the Efficient Properties Workflow v3.7. Fixes Setup.sol wiring (Step -1), ghost infrastructure (Step 0), ProfitTracker ghost contract (Step 0F), protocol-aware handler templates (Step 0G), and implements PROFIT + SIMPLE + CANARY properties. Runs forge build to verify compilation before Phase 3B."
mode: subagent
temperature: 0.1
---

## Role
You are the @properties-phase-3a agent.

We're specifying properties for the smart contract system in scope.

## Inputs

Read `magic/properties-efficient-second-pass.md` which contains validated efficiency-tiered properties with architectural prefixes and an INFRASTRUCTURE STATUS header.

Before implementing, read the existing test scaffolding:
- Find and read the Setup contract (usually `test/recon/Setup.sol`)
- Find and read the BeforeAfter contract (usually `test/recon/BeforeAfter.sol`)
- Find and read the TargetFunctions contract (usually `test/recon/TargetFunctions.sol`)
- Read `magic/properties-efficient-second-pass.md` INFRASTRUCTURE STATUS section for ghost classification
- **Read `magic/setup-wiring-analysis.md`** (if it exists) for Setup.sol wiring fixes

## Output

Write implemented properties to `Properties.sol` (or `Properties2.sol` if the file header contains `COMPARISON_MODE: true`).

List every property you wrote and the diff of the changes in `magic/coded-properties.md`.

**IMPORTANT:** After implementing all properties in this phase, run `forge build` to verify compilation. Phase 3B depends on your code compiling cleanly.

---

## STEP -1: SETUP.SOL WIRING (NEW in v3.5 — Critical)

Before implementing properties, fix Setup.sol to properly wire contracts. Without correct wiring, most properties are dead code (they early-return because contracts are at address(0) or functions revert due to wrong msg.sender).

**If `magic/setup-wiring-analysis.md` exists**, use it as your guide. Otherwise, perform the analysis yourself by reading Setup.sol and the contract constructors.

### -1A: Fix Constructor Parameters

For each contract deployed with `address(0)` or missing parameters:

**Pattern: Gateway/Admin Immutable**
Contracts with `immutable gateway` or `immutable admin` that check `msg.sender == gateway`:
```solidity
// WRONG: Will revert on all gateway-only calls
dToken = new DToken(uniqueId, name, symbol, address(0));

// RIGHT: CryticTester acts as gateway
dToken = new DToken(uniqueId, name, symbol, address(this));
```

**Pattern: Token Dependencies**
Contracts that need real token addresses for `transferFrom`, `balanceOf`, etc.:
```solidity
// WRONG: Will revert on any token interaction
vault = new VaultImplementationNone(address(this), address(0));

// RIGHT: Use _newAsset() from AssetManager
address tokenB0 = _newAsset(6);  // 6 decimals = USDC-like
vault = new VaultImplementationNone(address(this), tokenB0);
```

**Pattern: External Call in Constructor**
Constructors that call methods on parameters WILL REVERT with `address(0)`:
```solidity
// VaultImplementationAave constructor calls market_.UNDERLYING_ASSET_ADDRESS()
// SKIP deployment — leave state variable zero-initialized
// Target functions referencing it will revert (acceptable for fuzzing)
```

### -1B: Wire Proxy Implementations

For each proxy + implementation pair detected in the wiring analysis:

```solidity
// Deploy proxy (admin defaults to msg.sender = address(this))
oracle = new Oracle();

// Deploy implementation
oracleImplementation = new OracleImplementation();

// Wire: MUST be called AFTER both are deployed
oracle.setImplementation(address(oracleImplementation));
```

**IMPORTANT:** Deployment order matters. If Implementation A depends on Proxy B, deploy in this order:
1. Deploy Proxy B
2. Deploy Implementation A (passing address of Proxy B)
3. Deploy Implementation B (if needed)
4. Wire: `proxyB.setImplementation(address(implB))`

For circular dependencies (A needs B, B needs A), use proxies as the stable addresses:
```solidity
// Both use proxy addresses — implementations deployed after both proxies exist
engine = new Engine();           // proxy
symbolManager = new SymbolManager(); // proxy

engineImpl = new EngineImplementation(address(symbolManager), ...);
symbolMgrImpl = new SymbolManagerImplementation(address(engine), ...);

engine.setImplementation(address(engineImpl));
symbolManager.setImplementation(address(symbolMgrImpl));
```

### -1C: Fix Target Function Modifiers

For each target function identified in the wiring analysis as having the wrong modifier:

**Gateway-only functions** (`_onlyGateway_`, `require(msg.sender == gateway)`):
```solidity
// WRONG: asActor pranks as random actor, but vault checks msg.sender == gateway
function vault_deposit(...) public asActor { vault.deposit(...); }

// RIGHT: asAdmin pranks as address(this) which IS the gateway
function vault_deposit(...) public asAdmin { vault.deposit(...); }
```

Apply `asAdmin` to: mint, burn, deposit, redeem, and any other gateway/admin-gated functions.
Keep `asActor` on: approve, transfer, transferFrom, and other user-callable functions.

### -1D: Fund Actors and Contracts

Ensure the test contract and actors have tokens to interact with the protocol:

```solidity
// Mint tokens to the gateway (address(this)) and approve the vault
MockERC20(tokenB0).mint(address(this), 1_000_000e6);
MockERC20(tokenB0).approve(address(vault), type(uint256).max);

// Fund each actor
MockERC20(tokenB0).mint(address(0x10001), 1_000_000e6);
MockERC20(tokenB0).mint(address(0x10002), 1_000_000e6);
MockERC20(tokenB0).mint(address(0x10003), 1_000_000e6);
```

### -1E: Protocol Configuration (AI-Level)

This step requires understanding the specific protocol's configuration requirements. Common patterns:

**Oracle setup:**
```solidity
// Set a base price for the protocol's primary asset
baseOracleOffchain.set("BTC", 8, int256(50000e8));
OracleImplementation(address(oracle)).setBaseOracle("BTC", address(baseOracleOffchain));
```

**Market/symbol registration:**
```solidity
// Register at least one symbol/market so the protocol has something to operate on
bytes32[] memory params = new bytes32[](N);
// Fill with protocol-specific values from documentation or deploy scripts
symbolManager.addSymbol("BTCUSD", 1, params);
```

**Fee/slippage configuration:**
```solidity
// Set non-zero slippage/fee limits so swaps don't revert
SwapperImplementation(address(swapper)).setMaxSlippageRatio(tokenB0, 1e17);
```

**ECDSA signer setup (if protocol uses signed events):**
```solidity
// Use well-known test private keys
uint256 constant SIGNER_KEY_1 = 1;
address constant SIGNER_1 = address(0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf); // addr(1)
```

### -1F: Verify Wiring

After all wiring changes, run `forge build` and then `forge test --match-contract CryticToFoundry` to verify:
1. Setup compiles
2. setUp() doesn't revert
3. Basic target functions can execute

If setUp() reverts, check the error message:
- "call to non-contract address 0x..." → A constructor is calling a method on address(0). Skip that deployment.
- "unauthorized" / "only gateway" → A function is using the wrong modifier (asActor vs asAdmin).
- "insufficient balance" → Funding step is missing.

---

## STEP 0: FIX GHOST INFRASTRUCTURE (Critical)

### 0A: Ensure updateGhosts on Core Target Functions

Before implementing any properties, verify that the `updateGhosts` modifier is applied to ALL core target functions in TargetFunctions.sol.

Check each function that calls the protocol's state-changing functions (supply, withdraw, borrow, repay, liquidate, accrueInterest, etc.).

If `updateGhosts` is MISSING from core target functions:
1. Add `updateGhosts` to every target function that calls a protocol state-changing function
2. This is REQUIRED for TIER 7A, 7B, 9, 11, and 13 properties to work
3. Without this fix, all selector-filtered properties (`if (_before.sig == X.selector)`) are dead code

The modifier should NOT be added to:
- View/read-only functions
- Functions that don't interact with the protocol (pure helpers)
- Property functions themselves

### 0B: Verify currentOperation Reset in Both Modifiers

The `recon-generate` template now includes `currentOperation` resets in both modifiers by default. **Verify** that `BeforeAfter.sol` contains these resets:

```solidity
modifier updateGhosts {
    currentOperation = bytes4(0); // Reset to prevent stale operation leaking
    __before();
    _;
    __after();
}

modifier trackOp(bytes4 op) {
    currentOperation = op;
    __before();
    _;
    __after();
    currentOperation = bytes4(0); // Reset after use to prevent stale op in standalone property calls
}
```

**Why both resets matter:**
- `trackOp` reset: Prevents Echidna from calling `property_*` functions as standalone transactions and seeing stale `currentOperation` from a previous `trackOp` call with a different `block.timestamp`.
- `updateGhosts` reset: Prevents Category B functions (updateGhosts-only) from leaving `currentOperation` stale while overwriting `_before`/`_after` ghosts.

**If either reset is missing** (legacy project or manually edited BeforeAfter.sol), add them.

### 0C: Stale-Op Guards (Fallback — legacy projects only)

Only needed if modifying BeforeAfter.sol is not practical (e.g., deeply customized ghost infrastructure). Add consistency preconditions to STALE_OP_RISK properties instead:

```solidity
// STALE_OP_RISK guard: verify snapshot is consistent with the operation
function property_deposit_increases_shares() public {
    if (currentOperation == SelectorStorage.DEPOSIT) {
        if (_after.totalSupply <= _before.totalSupply) return;
        t(_after.actorShareBalance > _before.actorShareBalance, "deposit must increase shares");
    }
}
```

If a STALE_OP_RISK property cannot have a natural consistency precondition, add it to `magic/properties-blocker.md`.

### 0D: Scaffold Target Pruning (REQUIRED — prevents false positives)

Read `magic/properties-efficient-second-pass.md` INFRASTRUCTURE STATUS section for "Admin Target Conflicts."

For each ADMIN scaffold target flagged as conflicting with a property:

1. **If the admin function is NOT in scope for fuzzing** (governance actions like pause, freeze, oracle replacement, implementation upgrade, ownership transfer): **DELETE or COMMENT OUT** the scaffold target function. These create trivial falsifications without testing real protocol behavior.

2. **If the admin function IS in scope** (e.g., the audit specifically targets admin flows): **Keep the target** but add precondition guards to conflicting properties:
   ```solidity
   // Guard: skip property when admin has paused the pool
   function echidna_some_liveness_property() public view returns (bool) {
       if (pool.paused()) return true;  // Admin-induced state, not a bug
       // ... actual property check
   }
   ```

**Common admin targets to REMOVE for most audits:**
- `setPoolPause` / `setPause` — trivially breaks all liveness/DOOM properties
- `setPriceOracle` / `setOracle` — trivially breaks all health factor/solvency properties
- `setLendingPoolImpl` / `setImplementation` — replaces core contracts with garbage
- `renounceOwnership` / `transferOwnership` — makes admin functions permanently unreachable
- `deactivateReserve` / `freezeReserve` — trivially breaks reserve-active properties
- `setEmergencyAdmin` / `setPoolAdmin` — changes access control
- `setAddress` / `setAddressAsProxy` — replaces any registered contract

After pruning, run `forge build` to verify compilation.

### 0E: Add Ghost Variables for Properties

Based on the properties to be implemented, add ghost variables to BeforeAfter.sol's `Vars` struct and update `__before()` / `__after()`:

**Common ghost variables needed:**
```solidity
struct Vars {
    uint256 __ignore__;
    // Add variables read by properties:
    uint256 vaultStTotalAmount;    // vault share tracking
    uint256 tokenTotalMinted;      // NFT token counter
    uint256 iouTotalSupply;        // IOU total supply
    uint256 vaultAssetBalance;     // actual token balance of vault
    uint256 gatewayEthBalance;     // ETH balance tracking
    // ... protocol-specific additions
}
```

For each ghost variable:
1. Read the value in `__before()` using the appropriate view function
2. Read the same value in `__after()`
3. Use try/catch if the view function might revert (e.g., uninitialized proxy)

```solidity
function __before() internal {
    // Use try/catch for cross-contract reads that might revert
    try vaultImplementationNone.stTotalAmount() returns (uint256 st) {
        _before.vaultStTotalAmount = st;
    } catch {}
}
```

### 0F: ProfitTracker Ghost Contract (NEW in v3.7)

After adding ghost variables (Step 0E), add protocol-wide value tracking to `BeforeAfter.sol` for system-level conservation properties.

**Add `ProtocolSnapshot` struct:**
```solidity
struct ProtocolSnapshot {
    uint256 totalValueLocked;        // Sum of all protocol-held token balances
    uint256 totalSharesOutstanding;  // Total share tokens across all vaults/pools
    uint256 totalDebtOutstanding;    // Total debt across all markets (lending only)
}
```

**Add per-sequence cumulative tracking:**
```solidity
// Cumulative tracking across the entire fuzzing sequence
uint256 internal _sequenceTotalDeposits;   // Sum of all deposit amounts in this sequence
uint256 internal _sequenceTotalWithdraws;  // Sum of all withdraw amounts in this sequence
```

**Add protocol-type-specific snapshot logic to `__after()`:**

Read `PROTOCOL_TYPE` from `magic/contracts-dependency-list.md` and implement the appropriate tracking:

- **VAULT**:
  ```solidity
  _protocolSnapshot.totalValueLocked = IERC20(asset).balanceOf(address(vault));
  _protocolSnapshot.totalSharesOutstanding = vault.totalSupply();
  ```
- **AMM**:
  ```solidity
  (uint112 reserve0, uint112 reserve1, ) = pair.getReserves();
  _protocolSnapshot.totalValueLocked = uint256(reserve0) + uint256(reserve1);
  _protocolSnapshot.totalSharesOutstanding = pair.totalSupply();
  ```
- **LENDING**:
  ```solidity
  _protocolSnapshot.totalValueLocked = totalCollateral;
  _protocolSnapshot.totalDebtOutstanding = totalDebt;
  _protocolSnapshot.totalSharesOutstanding = aToken.totalSupply();
  ```

**Add two new properties using the snapshot data:**

- **PROFIT-04: System-wide value conservation**
  ```solidity
  /// @notice TVL_end + total_withdrawals >= TVL_start + total_deposits - DUST
  function property_PROFIT_04_systemValueConservation() public {
      uint256 tvlEnd = _protocolSnapshot.totalValueLocked;
      uint256 tvlStart = _initialProtocolSnapshot.totalValueLocked;
      uint256 DUST = 1000; // 1000 wei tolerance
      t(
          tvlEnd + _sequenceTotalWithdraws + DUST >= tvlStart + _sequenceTotalDeposits,
          "PROFIT-04: system-wide value not conserved"
      );
  }
  ```

- **PROFIT-05: Share value monotonicity under normal operations**
  ```solidity
  /// @notice Share price should not decrease during normal operations (no loss events)
  function property_PROFIT_05_shareValueMonotonicity() public {
      if (_protocolSnapshot.totalSharesOutstanding == 0) return;
      if (_initialProtocolSnapshot.totalSharesOutstanding == 0) return;
      // Cross-multiply to avoid division precision issues
      // current_tvl / current_shares >= initial_tvl / initial_shares
      uint256 lhs = _protocolSnapshot.totalValueLocked * _initialProtocolSnapshot.totalSharesOutstanding;
      uint256 rhs = _initialProtocolSnapshot.totalValueLocked * _protocolSnapshot.totalSharesOutstanding;
      gte(lhs + 1, rhs, "PROFIT-05: share value decreased");
  }
  ```

**Template selection by PROTOCOL_TYPE:**
- If PROTOCOL_TYPE is OTHER or unknown, use a generic TVL calculation: sum of all tracked token balances in protocol contracts
- Record `_initialProtocolSnapshot` at end of `setUp()` alongside `_recordInitialBalances()`

### 0G: Protocol-Aware Handler Templates (NEW in v3.7)

After ProfitTracker setup (Step 0F), create protocol-specific attack-pattern handler functions.

**Read `PROTOCOL_TYPE`** from `magic/contracts-dependency-list.md`. Based on the detected type, create a handler template file at `test/recon/handlers/`:

**Skip entirely** if PROTOCOL_TYPE is `OTHER` — generic handlers don't add value.

#### ERC20 Handlers (`handlers/ERC20Handlers.sol`):
```solidity
/// @notice approve max then transferFrom — tests approval drain
function handler_erc20_approveAndTransferFrom(uint256 amount) public updateGhosts {
    address victim = _getActor();
    amount = amount % (token.balanceOf(victim) + 1);
    if (amount == 0) return;

    vm.prank(victim);
    token.approve(address(this), type(uint256).max);

    token.transferFrom(victim, address(this), amount);
}
```

#### VAULT Handlers (`handlers/VaultHandlers.sol`):
```solidity
/// @notice deposit-withdraw roundtrip — tests for value extraction
function handler_vault_depositWithdrawRoundtrip(uint256 amount) public updateGhosts {
    amount = amount % (IERC20(asset).balanceOf(_getActor()) + 1);
    if (amount == 0) return;

    vm.startPrank(_getActor());
    IERC20(asset).approve(address(vault), amount);
    uint256 shares = vault.deposit(amount, _getActor());
    if (shares == 0) return;
    uint256 assetsBack = vault.redeem(shares, _getActor(), _getActor());
    vm.stopPrank();
    // Property checks happen via PROFIT oracle
}

/// @notice share inflation via donation — tests first-depositor attack
function handler_vault_shareInflation(uint256 donationAmount) public updateGhosts {
    donationAmount = donationAmount % (IERC20(asset).balanceOf(address(this)) + 1);
    if (donationAmount == 0) return;

    // Donate tokens directly to vault (not through deposit)
    IERC20(asset).transfer(address(vault), donationAmount);
}
```

#### AMM Handlers (`handlers/AMMHandlers.sol`):
```solidity
/// @notice swap roundtrip — tests sandwich attack resistance
function handler_amm_swapRoundtrip(uint256 amountIn) public updateGhosts {
    // Swap token0 -> token1 -> token0
    // PROFIT oracle will catch any extraction
}

/// @notice liquidity sandwich — add liquidity around a swap
function handler_amm_liquiditySandwich(uint256 liquidityAmount, uint256 swapAmount) public updateGhosts {
    // Add liquidity, swap, remove liquidity
    // PROFIT oracle will catch sandwich profit
}
```

#### LENDING Handlers (`handlers/LendingHandlers.sol`):
```solidity
/// @notice borrow at boundary — tests health factor edge cases
function handler_lending_borrowAtBoundary(uint256 collateralAmount) public updateGhosts {
    // Deposit collateral, borrow maximum allowed
    // Tests liquidation threshold boundaries
}

/// @notice liquidation at threshold — tests liquidation correctness
function handler_lending_liquidateAtThreshold(uint256 priceChange) public updateGhosts {
    // Manipulate oracle price to bring position to liquidation threshold
    // Attempt liquidation
}
```

#### STAKING Handlers (`handlers/StakingHandlers.sol`):
```solidity
/// @notice stake-unstake roundtrip — tests for reward leakage
function handler_staking_stakeUnstakeRoundtrip(uint256 amount, uint256 timeWarp) public updateGhosts {
    // Stake, warp time, unstake
    // Check rewards proportionality
}

/// @notice reward harvest timing — tests reward timing exploitation
function handler_staking_rewardHarvestTiming(uint256 timeWarp) public updateGhosts {
    // Warp to just before/after reward period boundaries
    // Harvest and check for timing exploitation
}
```

**All handlers MUST:**
- Use `updateGhosts` modifier
- Be non-reverting (use early returns, not require)
- Clamp all inputs: `amount = amount % (maxValue + 1);`
- Use `if (amount == 0) return;` guards

**Wire into TargetFunctions inheritance chain:**
```solidity
// In the handler file:
contract VaultHandlers is Properties {
    // handler functions here
}

// In TargetFunctions.sol, add to inheritance:
contract TargetFunctions is VaultHandlers, ... {
    // existing target functions
}
```

**Verify compilation** after creating handler files:
```bash
forge build
```

If compilation fails, fix the handler file. Do NOT leave broken code.

---

## Rules to Implement All Properties

- Use Chimera Asserts whenever possible (`lib/Chimera/Asserts`):
  - `t(bool condition, string message)` — assert condition is true
  - `eq(uint256 a, uint256 b, string message)` — assert a == b
  - `gte(uint256 a, uint256 b, string message)` — assert a >= b
  - `lte(uint256 a, uint256 b, string message)` — assert a <= b

- Whenever you cannot use `eq` due to types, use `t` and add a comment explaining why
- **Chimera assertions only accept `uint256`.** For `int256` comparisons, use `t(a >= b, ...)` instead of `gte()`.

---

## Dictionary

The testing suite provides actor/asset management:
- Get the current actor: `_getActor()`
- Get all actors: `_getActors()`
- Get the current asset: `_getAsset()`
- Get all assets: `_getAssets()`

---

## Avoiding Arbitrary Bounds

- **Input Validation:** Use overflow guards (`if (amount > type(uint256).max - currentValue) return;`) or let protocol validate via try/catch. Never `amount % 1e24`.
- **Minting:** Use exact amounts (`MockERC20(token).mint(addr, amount)`) or compute exact requirement. Never `amount + 1e18`.
- **Tolerance:** Use minimal justified values (`entityCount` units, 1 wei). Never `entityCount * 1e27`.
- **Growth bounds:** Document rationale in a comment. Example: `// 10x generous: 100% APR for 1yr = ~2.7x`
- **Protocol caps:** Use actual protocol-defined values (`protocol.getCapForEntity(entityId)`).

---

## Phase 3A Scope: PROFIT + CANARY + SIMPLE Properties Only

This phase implements the following property types:

### PROFIT-* (TIER 0: Economic Extraction Oracle — MANDATORY)

Implement the `_initialBalances` tracking infrastructure and all PROFIT properties.

**Step 1: Add tracking state to BeforeAfter.sol (or Setup.sol):**
```solidity
// Initial balance tracking for PROFIT oracle
mapping(address => mapping(address => uint256)) internal _initialBalances; // actor => token => balance
mapping(address => uint256) internal _initialETHBalances; // actor => ETH balance
mapping(address => mapping(address => uint256)) internal _initialProtocolBalances; // protocol contract => token => balance
uint256 constant DUST_TOLERANCE_18 = 1000; // 1000 wei for 18-decimal tokens
uint256 constant DUST_TOLERANCE_6 = 10;    // 10 for 6-decimal tokens (USDC)
```

**Step 2: Add `_recordInitialBalances()` helper and call at end of `setUp()`:**
```solidity
function _recordInitialBalances() internal {
    address[] memory allActors = _getActors();
    address[] memory allTokens = _getAssets();
    // Record actor balances
    for (uint256 a = 0; a < allActors.length; a++) {
        for (uint256 t = 0; t < allTokens.length; t++) {
            _initialBalances[allActors[a]][allTokens[t]] =
                IERC20(allTokens[t]).balanceOf(allActors[a]);
        }
        _initialETHBalances[allActors[a]] = allActors[a].balance;
    }
    // Record protocol contract balances
    for (uint256 t = 0; t < allTokens.length; t++) {
        _initialProtocolBalances[address(protocolContract)][allTokens[t]] =
            IERC20(allTokens[t]).balanceOf(address(protocolContract));
    }
}
```

**Step 3: Implement PROFIT-01, PROFIT-02, PROFIT-03** using the pseudocode from Phase 1A's Tier 0 section.

**IMPORTANT:** Replace `protocolContract` with the actual main protocol contract variable from Setup.sol. If there are multiple protocol contracts, track all of them.

### CANARY-* (TIER 1: Coverage Verification)
Assert a flag is false. The flag is set to true in the target handler when the operation is performed.
```solidity
bool internal liquidationReached;

function canary_reachedLiquidation() public {
    t(!liquidationReached, "CANARY-01: fuzzer reached liquidation path");
}
```

### SOL-* (TIER 2: Solvency — SIMPLE)
Read current protocol state directly. No function selector filtering.
```solidity
function property_HUB_SOL_01_balanceGteAccounting() public {
    uint256 balance = token.balanceOf(address(hub));
    uint256 accounting = hub.totalLiquidity();
    gte(balance, accounting, "HUB-SOL-01: balance must >= liquidity accounting");
}
```

**Solvency Tolerance Rules for Lending Protocols:**
- **Fixed tolerance (1e6 wei) is NOT sufficient** for protocols with liquidation bonuses, interest compounding, and treasury accrual. These effects create gaps proportional to the amounts involved.
- **Use proportional tolerance**: `tolerance = max(aTokenSupply / 1000, 1e6)` (0.1% of supply, minimum 1e6 wei).
- **Why 0.1%**: Lending protocols with oracle-manipulable prices, liquidation bonuses (5%), reserve factors (10%), and multi-day interest accrual create multiplicative WAD/RAY precision drift. At 0.01% this triggers false positives from legitimate liquidation + accrual sequences. At 0.1%, the property still catches any real exploit (drain attacks, double-spend, accounting manipulation) while allowing normal precision drift from `oracle_change * liquidation_bonus * reserve_factor * time_accrual` compounding.
- **If the protocol has a liquidation bonus** (e.g., 5% = 10500 bps), the solvency formula must account for the fact that liquidation distributes more collateral than debt covered. The gap is: `totalLiquidated * (bonus - 10000) / 10000`.
- **If the protocol has a reserve factor** (e.g., 10%), interest accrual mints additional tokens to the treasury, increasing supply without increasing underlying. The accounting formula `aTokenSupply <= underlying + totalDebt` should still hold because totalDebt includes the full interest, but rounding across many operations creates drift.
- **Document the tolerance rationale** in a comment above the property.

### MON-* (TIER 5: Monotonicity — SIMPLE)
Use high-water-mark ghost variables.
```solidity
uint256 internal _maxDrawnIndex;

function property_HUB_MON_01_drawnIndexNeverDecreases() public {
    uint256 currentIndex = hub.drawnIndex();
    gte(currentIndex, _maxDrawnIndex, "HUB-MON-01: drawnIndex decreased");
    if (currentIndex > _maxDrawnIndex) _maxDrawnIndex = currentIndex;
}
```

### MATH-* (TIER 6: Mathematical — SIMPLE with parameters)
Accept fuzz inputs. Add overflow and division-by-zero guards.
```solidity
function property_MATH_01_rayMulUpGteDown(uint256 x, uint256 y) public {
    if (x != 0 && y != 0 && x > type(uint256).max / y) return;
    uint256 up = WadRayMath.rayMulUp(x, y);
    uint256 down = WadRayMath.rayMulDown(x, y);
    gte(up, down, "MATH-01: rayMulUp must >= rayMulDown");
}
```

### ER-* (TIER 8: Exchange Rate — SIMPLE)
Cross-multiplication to avoid division precision issues.
```solidity
function property_HUB_ER_01_sharePriceNonDecreasing() public {
    if (_before.totalShares == 0 || _after.totalShares == 0) return;
    uint256 lhs = _after.totalAssets * _before.totalShares;
    uint256 rhs = _before.totalAssets * _after.totalShares;
    gte(lhs, rhs - 1, "HUB-ER-01: share price must not decrease");
}
```

### VS-* (TIER 12: Valid State — SIMPLE)
```solidity
function property_HUB_VS_01_drawnIndexGteRay() public {
    uint256 drawnIndex = hub.drawnIndex();
    gte(drawnIndex, 1e27, "HUB-VS-01: drawnIndex must be >= RAY (1e27)");
}
```

### Reading State Through Proxies

When implementing properties that read protocol state, always call through the **proxy** (not the implementation directly) to get actual state:

```solidity
// WRONG: Reads implementation's own storage (likely empty)
uint256 val = symbolManagerImplementation.someView();

// RIGHT: Reads proxy storage via delegatecall
uint256 val = SymbolManagerImplementation(address(symbolManager)).someView();
```

Use try/catch for cross-contract reads that might revert:
```solidity
function property_SYMBOL_VS_01() public {
    if (symbolId == bytes32(0)) return;  // skip if no symbol registered
    try SymbolManagerImplementation(address(symbolManager)).getState(symbolId)
        returns (bytes32[] memory s)
    {
        // Use returned data for assertions
        int256 openVolume = int256(uint256(s[13]));
        t(openVolume >= 0, "SYMBOL-VS-01: openVolume negative");
    } catch {
        // View function reverted — skip this property check
    }
}
```

### Global Properties Implementation Guide

**1) Simple view functions:**
```solidity
uint256 globalDeposits = target.getGlobalDeposits();
uint256 sumFromOther = target.getDepositPartOne() + target.getDepositPartTwo();
eq(sumFromOther, globalDeposits, "P-01: Sum matches");
```

**2) View functions with hardcoded/dictionary parameter:**
```solidity
uint256 marketBalance = target.getMarketData(hardcodedMarketIdentifier).balance;
uint256 currentUserBalance = target.getUserBalance(_getActor());
```

**3) View functions across all tokens/users:**
```solidity
uint256 sumOfUserBalance;
for (uint256 i; i < _getActors().length; i++) {
    sumOfUserBalance += target.getUserBalance(_getActors()[i]);
}
```

---

## Shortcut Target Functions (Coverage Boosters)

After implementing properties, identify 3-5 **multi-step sequences** that the fuzzer is unlikely to discover on its own. These are "shortcut" functions in TargetFunctions.sol that chain multiple operations to reach deep protocol states.

### Common shortcut patterns:

1. **Complete lifecycle**: Start + execute + close in one call
   ```solidity
   function shortcut_full_rebalance_cycle() public updateGhosts {
       // 1. Start rebalance with specific params
       // 2. Warp past warmup
       // 3. Open auction
       // 4. Bid
       // 5. Close auction
   }
   ```

2. **Boundary crossing**: Force state past a critical threshold
   ```solidity
   function shortcut_drain_token_to_zero() public updateGhosts {
       // 1. Set weight to zero
       // 2. Start rebalance
       // 3. Open auction
       // 4. Bid full amount → triggers removeFromBasket
   }
   ```

3. **Fee accumulation**: Warp time to trigger fee-dependent logic
   ```solidity
   function shortcut_accrue_and_distribute() public updateGhosts {
       // 1. Warp past day boundary
       // 2. Poke (accrues fees)
       // 3. Distribute fees
   }
   ```

4. **Atomic multi-operation**: Operations that only make sense together
   ```solidity
   function shortcut_mint_with_fee() public updateGhosts {
       // 1. Set mint fee > 0
       // 2. Mint shares
       // 3. Reset mint fee to 0
   }
   ```

### Rules for shortcuts:
- Use `updateGhosts` modifier (NOT `trackOp`) — shortcuts are multi-operation
- Use `vm.prank` for role-restricted steps
- Use `try {} catch {}` for operations that may legitimately fail
- Name with `shortcut_` prefix so they're clearly identifiable
- Add comments explaining what deep state each shortcut exercises

---

## SetupHelper Pattern (Complex Factory Deployments)

When the protocol uses a factory/deployer contract that takes struct array parameters, Solidity can't pass dynamic arrays of structs from inline code. Use a helper contract:

```solidity
contract SetupHelper {
    function approveAndDeploy(
        IERC20 token,
        IFactory factory,
        IFactory.Config memory config
    ) external returns (address deployed) {
        token.approve(address(factory), type(uint256).max);
        deployed = factory.deploy(config);
    }
}
```

In `Setup.sol`:
```solidity
SetupHelper helper = new SetupHelper();
token.mint(address(helper), amount);
address deployed = helper.approveAndDeploy(token, factory, config);
```

This pattern is needed when:
- Factory requires `msg.sender` to have token approvals
- Deploy parameters include dynamic arrays of structs
- Multiple token approvals needed before a single deploy call

---

## Error Recovery

If `forge build` fails, classify the error:

| Error Type | Example | Action |
|-----------|---------|--------|
| Missing import | "Identifier not found" | Add import from parent contract or lib/ |
| Wrong function signature | "Member not found" | Check actual protocol API in dependency list |
| Type mismatch | "Type uint256 not implicitly convertible" | Use explicit cast or t() instead of eq() |
| Type mismatch (int256 in assertions) | "Invalid implicit conversion from int256 to uint256" | Chimera assertions only accept uint256. Use `t(intVal >= 0, ...)` instead of `gte(intVal, 0, ...)` |
| using-for needed | "Member function not found" | Add `using LibName for TypeName` |
| Overflow in constant | "Literal too large" | Use unchecked block or split computation |
| Undeclared identifier | "Undeclared identifier" for a contract type used in Properties.sol | Add explicit import — named imports don't propagate transitively |
| UNRECOVERABLE | "Contract too large" | Move properties to Properties2.sol extension |

After fixing, re-run `forge build`. Max 3 fix-compile cycles per batch.
If still failing after 3 cycles, move remaining properties to `magic/properties-blocker.md`.

---

## Handling BLOCKED_BY_INFRASTRUCTURE Properties

For properties marked `BLOCKED_BY_INFRASTRUCTURE` in the second pass:

1. **Check if Step -1 resolved the blocker** — after wiring Setup.sol, many previously blocked properties become implementable
2. If the required infrastructure is now available, implement the property normally
3. If infrastructure still cannot be added (e.g., needs ECDSA signing helpers, complex multi-step state), document it:
```solidity
// BLOCKED_BY_INFRASTRUCTURE: ENGINE-VT-01
// Requires: Valid eventData + ECDSA signature for Engine.trade()
// To enable: Add vm.sign() helper in target function to produce valid signed events
```

---

## File Organization

1. Properties file inherits from BeforeAfter (or from existing Properties if extending)
2. The inheritance chain: TargetFunctions -> Properties -> BeforeAfter -> Setup
3. Update TargetFunctions inheritance if needed

### Naming Convention

Use the architectural prefix in function names:
```solidity
function property_HUB_SOL_01_balanceGteAccounting() public { ... }
function property_MATH_03_roundTripNoInflation() public { ... }
function canary_CANARY_01_reachedLiquidation() public { ... }
```

---

## Verification Steps (Phase 3A)

1. `forge build` — must compile without errors
2. `forge test --match-contract CryticToFoundry` — setUp() must not revert
3. Verify `updateGhosts` was added to all core target functions (Step 0A)
4. Verify updateGhosts reset fix was applied if Category B functions exist (Step 0B)
5. Verify no tautological properties were implemented (spot-check against protocol require statements)
6. **CRITICAL: Verify NO unjustified arbitrary bounds** — search for:
   - `% 1e24`, `% 1e30`, `% 1e36` (arbitrary modulo)
   - `+ 1e18` in mint/transfer calls (arbitrary buffer)
   - `* 1e27` in tolerance calculations (excessive tolerance)
   - Any hardcoded large numbers not from protocol constants
7. **CRITICAL: Verify Properties wiring in CryticTester and CryticToFoundry.**
   Both contracts MUST inherit `Properties` so that echidna/medusa can see the property functions.
   Check that the inheritance chain includes `Properties` before `TargetFunctions`:
   ```solidity
   // CryticTester.sol — MUST have Properties
   contract CryticTester is Properties, TargetFunctions, CryticAsserts { ... }

   // CryticToFoundry.sol — MUST have Properties
   contract CryticToFoundry is Test, Properties, TargetFunctions, FoundryAsserts { ... }
   ```
   If `Properties` is missing from either file, add the import and inheritance.
   **Order matters:** `Properties` must come BEFORE `TargetFunctions` to satisfy Solidity C3 linearization
   (both inherit from `BeforeAfter → Setup`, so the base must appear first).

**Phase 3A must compile cleanly before Phase 3B starts.** If compilation fails after 3 fix cycles, document blockers and proceed with what compiles.
