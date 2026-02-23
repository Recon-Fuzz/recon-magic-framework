---
description: "Phase 3A of the Efficient Properties Workflow v4.2. Builds on v4.1 with flash loan attacker handler (Step 0L), reentrant callback mock (Step 0M), FoundryProperties.sol split (Step 0N), fee volume conservation ghost tracking, and state machine property implementations. Previous: weird token mock deployment (Step 0I), accumulation ghost tracking (Step 0J), token compliance harness (Step 0K), mandatory v4 guards and delegation-aware ProfitTracker. Fixes Setup.sol wiring (Step -1), ghost infrastructure (Step 0), ProfitTracker ghost contract (Step 0F), protocol-aware handler templates (Step 0G), Step 0H admin validation negative tests, core-read-fail rule, deeper ghost variable guidance, and implements PROFIT + SIMPLE + CANARY + WTOK + ACCUM + COMPLY + STATE_MACHINE + FEE_VOL properties. Runs forge build to verify compilation before Phase 3B."
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
- `*_mint(address,uint256)` / `*_burn(address,uint256)` on token contracts — bypasses protocol collateral flow, creates impossible supply states

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

### Ghost Variable Depth Rules (v4)

For HIGH_TAINT functions (from `magic/dataflow-taint-analysis.md`), add ADDITIONAL
ghost variables beyond the standard per-property set:

1. **Per-actor tracking**: For functions that modify per-user state, add per-actor
   ghost snapshots (not just global):
   ```solidity
   _before.actorBalance = protocol.balanceOf(_getActor());
   _before.actorDebt = protocol.debtOf(_getActor());
   ```

2. **Cross-contract tracking**: For functions that modify state across multiple
   contracts, snapshot BOTH contracts:
   ```solidity
   _before.vaultTotalAssets = vault.totalAssets();
   _before.strategyTotalAssets = strategy.totalAssets();
   ```

3. **Cumulative delta tracking**: For deposit/withdraw, track cumulative amounts
   across the entire fuzzing sequence for PROFIT-04:
   ```solidity
   // In __after(), after deposit operations:
   if (currentOperation == SelectorStorage.DEPOSIT) {
       _sequenceTotalDeposits += depositAmount;
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

### 0H: Admin Validation Negative Tests (v4)

For each admin setter function identified in AdminTargets.sol, implement negative tests
in Properties.sol:

1. **Zero-address rejection**: `try protocol.setX(address(0)) { t(false, ...) } catch {}`
2. **Self-assignment rejection**: `try protocol.setX(address(protocol)) { t(false, ...) } catch {}`
3. **State effect verification** (using asAdmin): After calling `setX(newVal)`, verify
   `protocol.x() == newVal`

These tests use the PROTOCOL's actual admin functions, not arbitrary addresses.
Wire them using `asAdmin` modifier to bypass access control (we're testing parameter
validation, not authorization).

If the protocol doesn't validate zero-address inputs (setAdmin(0) succeeds), that's
a REAL BUG — the property correctly catches it.

### 0I: Weird Token Mock Deployment (NEW in v4.1)

**Read `TOKEN_ASSUMPTION` from `magic/contracts-dependency-list.md`.** If `RESTRICTED`, skip this step entirely.

If `TOKEN_ASSUMPTION=OPEN` or `UNSPECIFIED`, and WTOK-* properties are in scope:

**Deploy weird token mocks INSTEAD of standard MockERC20 for the primary protocol token.**

```solidity
// Mock library for weird token testing — add to test/recon/mocks/

/// @notice ERC20 that takes a percentage fee on every transfer
contract MockFeeOnTransferERC20 is MockERC20 {
    uint256 public transferFeeBps; // e.g., 100 = 1%

    constructor(string memory name, string memory symbol, uint8 decimals_, uint256 feeBps)
        MockERC20(name, symbol, decimals_)
    {
        transferFeeBps = feeBps;
    }

    function transfer(address to, uint256 amount) public override returns (bool) {
        uint256 fee = amount * transferFeeBps / 10000;
        uint256 netAmount = amount - fee;
        _burn(msg.sender, fee); // fee is burned (lost)
        return super.transfer(to, netAmount);
    }

    function transferFrom(address from, address to, uint256 amount) public override returns (bool) {
        uint256 fee = amount * transferFeeBps / 10000;
        uint256 netAmount = amount - fee;
        _burn(from, fee); // fee is burned (lost)
        return super.transferFrom(from, to, netAmount);
    }
}

/// @notice ERC20 with adjustable rebase factor — balances scale by factor
contract MockRebasingERC20 is MockERC20 {
    uint256 public rebaseFactor = 1e18; // 1.0x

    constructor(string memory name, string memory symbol, uint8 decimals_)
        MockERC20(name, symbol, decimals_)
    {}

    function rebase(uint256 newFactor) external {
        rebaseFactor = newFactor;
    }

    function balanceOf(address account) public view override returns (uint256) {
        return super.balanceOf(account) * rebaseFactor / 1e18;
    }

    function totalSupply() public view override returns (uint256) {
        return super.totalSupply() * rebaseFactor / 1e18;
    }
}
```

**Deployment rules:**
1. Deploy the weird token mock INSTEAD of (not alongside) the standard `MockERC20` for the primary asset
2. All existing properties (SOL, PROFIT, VT) run unchanged — if they fail, that's a REAL finding
3. For `MockRebasingERC20`, add `rebase(uint256)` as a handler target function in TargetFunctions.sol:
   ```solidity
   function rebase_token(uint256 factor) public updateGhosts {
       factor = factor % 2e18 + 5e17; // clamp to 0.5x-2.5x range
       MockRebasingERC20(address(token)).rebase(factor);
   }
   ```
4. For `MockFeeOnTransferERC20`, use `feeBps=100` (1%) as default — represents common tax tokens
5. Only deploy ONE weird token type per fuzzing campaign — don't mix fee-on-transfer with rebasing

**Which weird token to deploy depends on WEIRD_TOKEN_CLASSES from Phase 0:**
- If `FEE_ON_TRANSFER=APPLICABLE` → deploy `MockFeeOnTransferERC20`
- If `REBASING=APPLICABLE` → deploy `MockRebasingERC20`
- If both APPLICABLE → run two separate campaigns (one per mock type)
- If `LOW_DECIMALS=APPLICABLE` → deploy standard `MockERC20` with `decimals=2` or `decimals=6`

### 0J: Accumulation Ghost Tracking (NEW in v4.1)

**Read `PRECISION_ACCUMULATION` from `magic/economic-oracles.md`.** If `NOT_APPLICABLE`, skip.

If ACCUM-* properties are in scope, add ghost variables to `BeforeAfter.sol`:

```solidity
// Accumulation tracking for ACCUM-* (Tier 17) properties
uint256 internal _totalOps;                              // total operations in this sequence
mapping(address => uint256) internal _accumulatedOps;    // per-actor operation count
mapping(address => int256) internal _actorNetDeposit;    // per-actor cumulative deposit - withdraw
uint256 internal _previousSolvencyGap;                   // last observed gap between balance and accounting

// MAX_DUST_PER_OP: Derived from token decimals and rounding operations
// For 18-decimal tokens with 1 roundDown per deposit/withdraw: 1 wei
// For 6-decimal tokens with 1 roundDown: 1 (1 micro-unit)
// For protocols with N rounding ops per call: N
uint256 constant MAX_DUST_PER_OP = 1; // MUST be justified per AP-20
uint256 constant MAX_DRIFT_PER_100_OPS = 100; // = 100 * MAX_DUST_PER_OP
```

**Update `__after()` in BeforeAfter.sol:**
```solidity
// In __after(), increment counters
_totalOps++;
_accumulatedOps[_getActor()]++;

// Track net deposits per actor (update in target function handlers, not here)
// _actorNetDeposit is updated in target functions:
//   deposit handler: _actorNetDeposit[actor] += int256(amount);
//   withdraw handler: _actorNetDeposit[actor] -= int256(amount);
```

**Update target function handlers** to track net deposits:
```solidity
function vault_deposit(uint256 amount) public trackOp(DEPOSIT) {
    // ... existing clamping and call ...
    _actorNetDeposit[_getActor()] += int256(amount);
    _totalVolumeProcessed += amount; // Fee volume conservation (PATTERN 29)
}

function vault_withdraw(uint256 amount) public trackOp(WITHDRAW) {
    // ... existing clamping and call ...
    _actorNetDeposit[_getActor()] -= int256(amount);
    _totalVolumeProcessed += amount; // Fee volume conservation (PATTERN 29)
}
```

**Fee volume conservation ghost tracking (NEW in v4.2 — PATTERN 29):**

If the protocol has a fee mechanism (detected by Phase 0 Step 6 `FEE_EXTRACTION=APPLICABLE` or any `feeRate`/`protocolFee` pattern), add:

```solidity
// Fee volume conservation tracking
uint256 internal _totalVolumeProcessed;  // cumulative sum of all deposit/withdraw/swap/borrow amounts
uint256 internal _totalFeesCollected;    // cumulative sum of all fees taken by protocol

// Update _totalVolumeProcessed in each target function handler:
// deposit: _totalVolumeProcessed += amount;
// withdraw: _totalVolumeProcessed += amount;
// swap: _totalVolumeProcessed += amountIn;
// borrow: _totalVolumeProcessed += amount;

// Update _totalFeesCollected in __after():
// Option A (if protocol exposes cumulative fee counter):
//   _totalFeesCollected = protocol.totalFeesCollected();
// Option B (if protocol has fee recipient):
//   _totalFeesCollected = IERC20(asset).balanceOf(feeRecipient) - _initialFeeRecipientBalance;
// Option C (compute from fee rate):
//   Track in handler: _totalFeesCollected += amount * feeRate / BPS;
```

**Fee volume property implementation:**
```solidity
function property_FEE_VOL_01_feesNeverExceedVolume() public {
    if (_totalVolumeProcessed == 0) return; // no operations yet
    lte(_totalFeesCollected, _totalVolumeProcessed,
        "FEE-VOL-01: fees exceed total volume — fee calculation bug");
}
```

### 0K: Token Compliance Harness (NEW in v4.1)

**Read `ISSUES_TOKENS` from `magic/contracts-dependency-list.md`.** If `false` or no overrides, skip.

If COMPLY-* properties (PATTERN 23-ERC20-E through H) are in scope:

**Implementation rules:**
1. COMPLY-* properties test the protocol's OWN token contract — not external tokens
2. Properties are always SIMPLE or NEGATIVE type
3. Use the actual token contract variable from Setup.sol (e.g., `shareToken`, `aToken`, `lpToken`)
4. Skip entirely if the token inherits unmodified OpenZeppelin ERC20 with NO overrides on transfer/approve/transferFrom

```solidity
// Token compliance properties — test protocol's own ERC20

function property_COMPLY_01_selfTransferPreservesBalance(uint256 amount) public {
    address actor = _getActor();
    if (address(protocolToken) == address(0)) return;
    uint256 actorBal = protocolToken.balanceOf(actor);
    if (actorBal == 0) return;
    amount = amount % (actorBal + 1);
    if (amount == 0) return;

    uint256 before = protocolToken.balanceOf(actor);
    vm.prank(actor);
    protocolToken.transfer(actor, amount);
    uint256 afterBal = protocolToken.balanceOf(actor);
    eq(afterBal, before, "COMPLY-01: self-transfer changed balance");
}

function property_COMPLY_02_approveOverwrites(uint256 amount1, uint256 amount2) public {
    address actor = _getActor();
    address spender = address(this);
    if (address(protocolToken) == address(0)) return;

    vm.startPrank(actor);
    protocolToken.approve(spender, amount1);
    protocolToken.approve(spender, amount2);
    vm.stopPrank();
    eq(protocolToken.allowance(actor, spender), amount2,
       "COMPLY-02: approve is additive, not overwrite");
}

function property_COMPLY_03_zeroTransferSucceeds() public {
    address actor = _getActor();
    address other = address(0x10001); // any non-zero address
    if (address(protocolToken) == address(0)) return;

    vm.prank(actor);
    try protocolToken.transfer(other, 0) {
        // success — zero transfer works
    } catch {
        t(false, "COMPLY-03: zero transfer reverted — breaks composability");
    }
}

function property_COMPLY_04_maxApprovalPersists(uint256 amount) public {
    address actor = _getActor();
    address spender = address(this);
    if (address(protocolToken) == address(0)) return;
    uint256 actorBal = protocolToken.balanceOf(actor);
    if (actorBal == 0) return;
    amount = amount % (actorBal + 1);
    if (amount == 0) return;

    vm.prank(actor);
    protocolToken.approve(spender, type(uint256).max);

    protocolToken.transferFrom(actor, address(this), amount);
    eq(protocolToken.allowance(actor, spender), type(uint256).max,
       "COMPLY-04: max allowance decreased after transferFrom");
}
```

**Replace `protocolToken` with the actual protocol token variable from Setup.sol** (e.g., `shareToken`, `vault` if it's ERC20, `lpToken`, etc.).

### 0L: Flash Loan Attacker Handler (NEW in v4.2)

**Read `FLASH_LOAN_ARBITRAGE` from `magic/economic-oracles.md`.** If `NOT_APPLICABLE`, skip this step entirely.

Only deploy when `FLASH_LOAN_ARBITRAGE=APPLICABLE` — gives the fuzzer access to large temporary capital to explore flash-loan-amplified attack sequences.

**MockFlashBank contract** — add to `test/recon/mocks/MockFlashBank.sol`:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import {IERC20} from "forge-std/interfaces/IERC20.sol";

interface IFlashBorrower {
    function onFlashLoan(
        address initiator,
        address token,
        uint256 amount,
        uint256 fee,
        bytes calldata data
    ) external returns (bytes32);
}

/// @notice Unlimited flash lender — gives fuzzer access to large temporary capital
contract MockFlashBank {
    function flashLoan(
        address receiver,
        address token,
        uint256 amount,
        bytes calldata data
    ) external {
        uint256 balBefore = IERC20(token).balanceOf(address(this));
        // Transfer tokens to receiver (flash bank must be pre-funded)
        IERC20(token).transfer(receiver, amount);
        // Execute callback
        IFlashBorrower(receiver).onFlashLoan(msg.sender, token, amount, 0, data);
        // Verify repayment
        uint256 balAfter = IERC20(token).balanceOf(address(this));
        require(balAfter >= balBefore, "flash loan not repaid");
    }
}
```

**Handler target function** — add to TargetFunctions.sol or a new handler file:

```solidity
/// @notice Flash loan attack sequence — borrow big, interact, repay
function handler_flashLoan_attack(uint256 amount, uint256 actionSeed) public updateGhosts {
    if (address(flashBank) == address(0)) return;
    amount = amount % 1_000_000_000e18 + 1; // 1 wei to 1B tokens
    address token = _getAsset();

    // Check flash bank has enough
    uint256 available = IERC20(token).balanceOf(address(flashBank));
    if (available < amount) amount = available;
    if (amount == 0) return;

    // Execute flash loan — CryticTester implements onFlashLoan callback
    try flashBank.flashLoan(address(this), token, amount, abi.encode(actionSeed)) {
        // PROFIT properties will catch any value extraction
    } catch {
        // Flash loan failed (e.g., couldn't repay) — acceptable
    }
}
```

**onFlashLoan callback** — implement in CryticTester (or the test contract that inherits TargetFunctions):

```solidity
function onFlashLoan(
    address initiator,
    address token,
    uint256 amount,
    uint256 fee,
    bytes calldata data
) external returns (bytes32) {
    uint256 actionSeed = abi.decode(data, (uint256));
    // Use actionSeed to pick which protocol function to call with the borrowed funds
    _executeFlashAction(token, amount, actionSeed);
    // Repay
    IERC20(token).transfer(msg.sender, amount + fee);
    return keccak256("ERC3156FlashBorrower.onFlashLoan");
}

/// @notice Route flash-loaned funds through protocol functions based on seed
function _executeFlashAction(address token, uint256 amount, uint256 actionSeed) internal {
    // Simple routing: use actionSeed to select a protocol interaction
    // Customize based on protocol's API
    uint256 action = actionSeed % 3;
    if (action == 0) {
        // Deposit borrowed funds
        IERC20(token).approve(address(protocol), amount);
        try protocol.deposit(amount) {} catch {}
    } else if (action == 1) {
        // Swap borrowed funds (if AMM)
        IERC20(token).approve(address(protocol), amount);
        try protocol.swap(token, amount, 0) {} catch {}
    } else {
        // Direct transfer to protocol (donation attack)
        IERC20(token).transfer(address(protocol), amount);
    }
}
```

**Deployment in Setup.sol:**
```solidity
flashBank = new MockFlashBank();
// Fund flash bank with large amounts of each token
address[] memory assets = _getAssets();
for (uint i; i < assets.length; i++) {
    MockERC20(assets[i]).mint(address(flashBank), 1_000_000_000e18);
}
```

**Key rules:**
1. Flash loan handler MUST be paired with PROFIT-01 property — the PROFIT oracle catches extraction, the handler provides capital
2. `_executeFlashAction` should be customized per protocol — add cases for the protocol's actual functions
3. The handler uses `try/catch` throughout to avoid reverting — reverts waste fuzzer cycles
4. Flash bank is pre-funded with `mint()`, not `deal()`, to avoid interference with balance tracking

### 0M: Reentrant Callback Mock (NEW in v4.2)

**Skip if protocol has NO external calls followed by state updates** (check Phase 0 Step 4a for reentrancy vectors). Only deploy when `MULTI_ACTOR=true` with identified reentrancy vectors.

**MockReentrantReceiver contract** — add to `test/recon/mocks/MockReentrantReceiver.sol`:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

/// @notice Token/ETH receiver that reenters the protocol on receive
contract MockReentrantReceiver {
    address public target;
    bytes public reentrantCalldata;
    bool public shouldReenter;

    function setReentryTarget(address _target, bytes calldata _calldata) external {
        target = _target;
        reentrantCalldata = _calldata;
        shouldReenter = true;
    }

    function disableReentry() external {
        shouldReenter = false;
    }

    // ERC721 callback — reenters on NFT receive
    function onERC721Received(address, address, uint256, bytes calldata)
        external returns (bytes4)
    {
        _tryReenter();
        return this.onERC721Received.selector;
    }

    // ETH receive — reenters on ETH transfer
    receive() external payable {
        _tryReenter();
    }

    // ERC1155 callback
    function onERC1155Received(address, address, uint256, uint256, bytes calldata)
        external returns (bytes4)
    {
        _tryReenter();
        return this.onERC1155Received.selector;
    }

    // Fallback for any other callback
    fallback() external payable {
        _tryReenter();
    }

    function _tryReenter() internal {
        if (shouldReenter && target != address(0)) {
            shouldReenter = false; // prevent infinite loop — single reentry only
            (bool success,) = target.call(reentrantCalldata);
            // success/failure doesn't matter — the property checks state consistency
            // Silence unused variable warning
            success;
        }
    }
}
```

**Handler target function:**
```solidity
/// @notice Set up reentrant callback then trigger it via protocol interaction
function handler_reentrant_setup(uint256 functionSelector, uint256 amount) public updateGhosts {
    if (address(reentrantReceiver) == address(0)) return;
    if (address(protocol) == address(0)) return;

    // Pick which function to reenter with based on functionSelector
    bytes memory calldata_ = _buildReentrantCalldata(functionSelector, amount);
    reentrantReceiver.setReentryTarget(address(protocol), calldata_);

    // Now the next protocol call that sends ETH/tokens to reentrantReceiver
    // will trigger reentry — PROFIT/SOL/MON properties catch any state corruption
}

/// @notice Build calldata for reentrant callback based on seed
function _buildReentrantCalldata(uint256 seed, uint256 amount) internal view returns (bytes memory) {
    // Customize based on protocol's API
    uint256 action = seed % 3;
    if (action == 0) {
        return abi.encodeWithSignature("deposit(uint256)", amount);
    } else if (action == 1) {
        return abi.encodeWithSignature("withdraw(uint256)", amount);
    } else {
        return abi.encodeWithSignature("transfer(address,uint256)", address(this), amount);
    }
}
```

**Deployment in Setup.sol:**
```solidity
reentrantReceiver = new MockReentrantReceiver();
// Register reentrantReceiver as an actor (replace actor[2] or add as actor[3])
// When the protocol sends tokens/ETH to this actor, it automatically reenters
```

**Key rules:**
1. `shouldReenter = false` after first reentry prevents infinite loops — only tests single-depth reentry
2. Reentrant receiver should be registered as a fuzzing actor so the protocol naturally sends to it
3. Existing PROFIT/SOL/MON properties catch any state corruption from reentry — no new property functions needed
4. The handler_reentrant_setup arms the receiver, but the actual reentry happens when the protocol interacts with the receiver actor
5. For protocols that use `ReentrancyGuard`, the reentrant call will revert (expected) — the property system catches cases where the guard is MISSING

---

### 0N: FoundryProperties.sol Split (NEW in v4.2)

**Always run this step.** Creates `FoundryProperties.sol` so that Foundry-only properties (using `vm.snapshot`, `vm.revertTo`, `vm.load`) are separated from Echidna-compatible properties in `Properties.sol`.

**Why this matters:** Echidna and Medusa crash on Foundry cheatcodes (`vm.snapshot`, `vm.revertTo`, `vm.load`). Without the split, DOOM-* and CROSS-G properties cannot coexist with Echidna testing. The split gives each runner the properties it can handle:

| File | Runner | Properties |
|------|--------|-----------|
| `Properties.sol` | Echidna + Foundry | SOL, MON, MATH, VT, FEE, ST, PRIV, CANARY, CROSS-E/F, ACCUM-01/02, FEE-VOL |
| `FoundryProperties.sol` | Foundry only | DOOM-*, CROSS-G, LIQ-04/05, ACCUM-03 |

**Step 1: Create `test/recon/FoundryProperties.sol`**

Check if it already exists. If not, create it:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import {Properties} from "./Properties.sol";
import {Test} from "forge-std/Test.sol";

/// @notice Foundry-only properties: DOOM (vm.snapshot/vm.revertTo), CROSS-G (vm.load)
/// @dev Inherited ONLY by CryticToFoundry — never by CryticTester (Echidna incompatible)
/// @dev Phase 3B appends DOOM-* properties here. Phase 3A writes CROSS-G here if applicable.
abstract contract FoundryProperties is Properties, Test {

}
```

**Step 2: Update `CryticToFoundry.sol` inheritance**

Add the import and change `CryticToFoundry` to inherit `FoundryProperties` instead of `Properties` directly:

```solidity
// BEFORE (or equivalent):
import {Properties} from "./Properties.sol";
contract CryticToFoundry is Test, Properties, TargetFunctions, FoundryAsserts { ... }

// AFTER:
import {FoundryProperties} from "./FoundryProperties.sol";
contract CryticToFoundry is Test, FoundryProperties, TargetFunctions, FoundryAsserts { ... }
```

**IMPORTANT:** Remove the direct `Properties` import from CryticToFoundry — `FoundryProperties` already imports it.

**CryticTester stays UNCHANGED** — it inherits `Properties` only:

```solidity
// CryticTester.sol — no change
contract CryticTester is Properties, TargetFunctions, CryticAsserts { ... }
```

**Step 3: Move any existing vm.snapshot / vm.load calls**

If `Properties.sol` already contains functions with `vm.snapshot()`, `vm.revertTo()`, or `vm.load()`:
1. Move those functions to `FoundryProperties.sol`
2. Delete them from `Properties.sol`
3. Run `forge build` to verify no compilation errors

**Step 4: Write CROSS-G here (if `USES_UPGRADEABLE_PROXY=true`)**

If Phase 0 detected `USES_UPGRADEABLE_PROXY=true`, write the CROSS-G storage slot stability property directly into `FoundryProperties.sol` (it uses `vm.load`):

```solidity
// In FoundryProperties.sol — FOUNDRY ONLY (vm.load)
function property_CROSS_G_01_implSlotUnchanged() public {
    bytes32 IMPL_SLOT = bytes32(uint256(keccak256("eip1967.proxy.implementation")) - 1);
    address impl = address(uint160(uint256(vm.load(address(proxy), IMPL_SLOT))));
    t(impl == address(expectedImplementation),
        "CROSS-G-01: implementation slot changed unexpectedly");
}
```

**Key rules:**
1. `FoundryProperties.sol` MUST import `Properties` (not re-declare all parents)
2. `FoundryProperties.sol` MUST import `forge-std/Test.sol` for `vm` cheatcodes
3. `CryticToFoundry` inherits `FoundryProperties` → gets both `Properties` and `Test` transitively
4. Phase 3B will place all DOOM-* properties in `FoundryProperties.sol` (routing table in Phase 3B)
5. Update `magic/coded-properties.md` to note the file each property was written to

---

## Rules to Implement All Properties

- Use Chimera Asserts whenever possible (`lib/Chimera/Asserts`):
  - `t(bool condition, string message)` — assert condition is true
  - `eq(uint256 a, uint256 b, string message)` — assert a == b
  - `gte(uint256 a, uint256 b, string message)` — assert a >= b
  - `lte(uint256 a, uint256 b, string message)` — assert a <= b

- Whenever you cannot use `eq` due to types, use `t` and add a comment explaining why
- **Chimera assertions only accept `uint256`.** For `int256` comparisons, use `t(a >= b, ...)` instead of `gte()`.

### Core State Read Failure Rule (v4)

When a property needs to read protocol state via a view function that MIGHT revert
(e.g., due to uninitialized proxy, paused contract, zeroed storage):

**DISTINGUISH between two cases:**

1. **Setup-dependent view** (might revert because setup is incomplete):
   Use try/catch with SKIP (not pass):
   ```solidity
   try protocol.getState() returns (...) {
       // assert on returned values
   } catch {
       // Skip — setup may not have initialized this path
       return;
   }
   ```

2. **Core state read** (should NEVER revert in a healthy protocol):
   Use try/catch with FAIL:
   ```solidity
   try protocol.totalSupply() returns (uint256 supply) {
       // assert on supply
   } catch {
       t(false, "CORE READ FAILURE: totalSupply() must not revert");
   }
   ```

**Heuristic:** If the function is called by other protocol functions internally
(visible in the dependency list), it's a core read — use FAIL pattern.

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

## Phase 3A Scope: PROFIT + CANARY + SIMPLE + WTOK + ACCUM + COMPLY + STATE_MACHINE + FEE_VOL Properties

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

### WTOK-* (TIER 16: Weird Token Integration — SIMPLE)
WTOK properties re-use existing SOL/PROFIT properties — the "property" is the mock token deployment.
No new property functions are needed; existing properties should break when weird tokens expose bugs.
See Step 0I for mock deployment instructions.

### ACCUM-* (TIER 17: Precision Accumulation — SIMPLE/NEGATIVE)
```solidity
// ACCUM-01: Per-actor precision drift bounded
function property_ACCUM_01_precisionDriftBounded() public {
    address actor = _getActor();
    if (_accumulatedOps[actor] == 0) return; // no ops, no drift
    if (_actorNetDeposit[actor] <= 0) return; // net withdrawer, skip

    uint256 expectedBalance = uint256(_actorNetDeposit[actor]);
    uint256 actualBalance = IERC20(asset).balanceOf(actor);
    if (expectedBalance > actualBalance) {
        uint256 drift = expectedBalance - actualBalance;
        uint256 allowedDrift = _accumulatedOps[actor] * MAX_DUST_PER_OP;
        lte(drift, allowedDrift, "ACCUM-01: precision drift exceeds bounded accumulation");
    }
}

// ACCUM-02: Solvency gap does not grow unboundedly
function property_ACCUM_02_solvencyGapBounded() public {
    if (address(protocol) == address(0)) return;
    if (_totalOps < 100) return; // need enough ops for meaningful signal

    uint256 realBalance = IERC20(asset).balanceOf(address(protocol));
    uint256 accounting = protocol.totalAssets();
    uint256 gap = realBalance > accounting
        ? realBalance - accounting
        : accounting - realBalance;

    lte(gap, _previousSolvencyGap + MAX_DRIFT_PER_100_OPS,
        "ACCUM-02: solvency gap growing unboundedly");
    _previousSolvencyGap = gap;
}

// ACCUM-03: Non-zero deposit must mint non-zero shares
function property_ACCUM_03_noZeroShareMint(uint256 amount) public {
    if (address(vault) == address(0)) return;
    address actor = _getActor();
    uint256 actorBal = IERC20(asset).balanceOf(actor);
    if (actorBal == 0) return;
    amount = amount % (actorBal + 1);
    if (amount == 0) return;

    uint256 sharesBefore = vault.balanceOf(actor);
    vm.prank(actor);
    IERC20(asset).approve(address(vault), amount);
    vm.prank(actor);
    try vault.deposit(amount, actor) {
        uint256 sharesAfter = vault.balanceOf(actor);
        gt(sharesAfter, sharesBefore, "ACCUM-03: deposit minted 0 shares — silent value loss");
    } catch {
        // Revert is acceptable — protocol rejects too-small deposits
    }
}
```

### COMPLY-* (TIER 12 Extension: Token Compliance — SIMPLE/NEGATIVE)
See Step 0K for full implementation templates. Replace `protocolToken` with actual token variable.

### CROSS-E/F/G (State Machine Properties — NEGATIVE/SIMPLE) (NEW in v4.2)

**Check `State Machine Patterns` from `magic/contracts-dependency-list.md`.** Skip if all three are false.

```solidity
// CROSS-E-01: Re-initialization blocked (if HAS_INITIALIZER=true)
function property_CROSS_E_01_initializeRevertsWhenInitialized() public {
    if (address(protocol) == address(0)) return;
    // Protocol should already be initialized from setUp()
    // Use the same initialize params from Setup.sol
    try protocol.initialize(/* setUp params */) {
        t(false, "CROSS-E-01: initialize() succeeded on already-initialized contract");
    } catch {
        // expected — re-initialization blocked
    }
}

// CROSS-F: Pause-freeze invariant (if HAS_PAUSE=true)
function property_CROSS_F_pauseFreezeInvariant() public {
    if (address(protocol) == address(0)) return;
    try protocol.paused() returns (bool isPaused) {
        if (!isPaused) return; // only check while paused
        // Critical state should not change while paused
        eq(_after.totalAssets, _before.totalAssets,
           "CROSS-F: totalAssets changed while paused");
        eq(_after.totalSupply, _before.totalSupply,
           "CROSS-F: totalSupply changed while paused");
    } catch {
        return; // paused() not available
    }
}

// CROSS-G: Storage slot stability (if USES_UPGRADEABLE_PROXY=true)
// ⚠️ FOUNDRY ONLY: vm.load is a Foundry cheatcode. Implement ONLY in CryticToFoundry,
// NOT in CryticTester (Echidna/Medusa will fail to compile/run this property).
// Wrap with `#ifdef FOUNDRY` or move to a separate FoundryProperties.sol if needed.
function property_CROSS_G_storageSlotStability() public {
    if (address(proxy) == address(0)) return;

    // EIP-1967 implementation slot
    bytes32 IMPL_SLOT = bytes32(uint256(keccak256("eip1967.proxy.implementation")) - 1);
    bytes32 implSlotValue = vm.load(address(proxy), IMPL_SLOT);
    address currentImpl = address(uint160(uint256(implSlotValue)));
    t(currentImpl != address(0), "CROSS-G: implementation slot zeroed — bricked proxy");
    eq(currentImpl, address(expectedImplementation),
       "CROSS-G: implementation slot changed unexpectedly");

    // EIP-1967 admin slot
    bytes32 ADMIN_SLOT = bytes32(uint256(keccak256("eip1967.proxy.admin")) - 1);
    bytes32 adminSlotValue = vm.load(address(proxy), ADMIN_SLOT);
    address currentAdmin = address(uint160(uint256(adminSlotValue)));
    t(currentAdmin != address(0), "CROSS-G: admin slot zeroed — unrecoverable proxy");
}
```

**Replace `protocol`, `proxy`, `expectedImplementation` with actual contract variables from Setup.sol.** Adapt the initialize params to match your protocol's constructor/initializer.

**CROSS-E adaptation note:** Replace `protocol.initialize(/* setUp params */)` with the EXACT same call used in `setUp()`. The function signature and parameter types must match precisely — do not guess.

**CROSS-F adaptation note:** Replace `_after.totalAssets`, `_before.totalAssets`, `_after.totalSupply`, `_before.totalSupply` with the ACTUAL ghost variable names from your BeforeAfter.sol `Vars` struct. Use the variables that track the protocol's most critical accounting state (e.g., `_after.vaultTotalAssets`, `_after.poolTotalShares`). If these ghost variables don't exist, add them in Step 0E first.

### FEE-VOL-* (TIER 9C: Fee Volume Conservation — SIMPLE) (NEW in v4.2)
See Step 0J fee volume section for ghost variable setup. The property itself is straightforward:
```solidity
function property_FEE_VOL_01_feesNeverExceedVolume() public {
    if (_totalVolumeProcessed == 0) return; // no operations yet
    lte(_totalFeesCollected, _totalVolumeProcessed,
        "FEE-VOL-01: fees exceed total volume — fee calculation bug");
}
```
**Skip entirely** if the protocol has no fee mechanism.

### PRIV-AUTH-* (Auth Sweep — NEGATIVE) (NEW in v4.2)

For each function in the Access Control Inventory (Phase 0 Step 4h) marked `In PRIV-NEG? = NO`:

```solidity
// Template: adapt per function
function property_PRIV_AUTH_XX_functionName_rejectsUnauthorized() public {
    address actor = _getActor();
    if (address(protocol) == address(0)) return;
    // Skip if actor already has the required role
    if (actor == protocol.owner()) return;
    // Add checks for ALL relevant roles:
    // if (actor == protocol.admin()) return;
    // if (protocol.hasRole(REQUIRED_ROLE, actor)) return;

    vm.prank(actor);
    try protocol.functionName(/* args */) {
        t(false, "PRIV-AUTH-XX: unauthorized functionName succeeded");
    } catch {
        // expected — access control works
    }
}
```

**Replace `protocol.functionName` and role checks with actual contract API.** Generate one property per access-controlled function not in PRIV-NEG.

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
   After Step 0N, the inheritance chains MUST be:
   ```solidity
   // CryticTester.sol — inherits Properties (Echidna-compatible only)
   contract CryticTester is Properties, TargetFunctions, CryticAsserts { ... }

   // CryticToFoundry.sol — inherits FoundryProperties (which includes Properties transitively)
   contract CryticToFoundry is Test, FoundryProperties, TargetFunctions, FoundryAsserts { ... }
   ```
   If `FoundryProperties` is missing from CryticToFoundry, add the import and update inheritance.
   **Order matters:** `FoundryProperties` / `Properties` must come BEFORE `TargetFunctions` to satisfy
   Solidity C3 linearization (both inherit from `BeforeAfter → Setup`, so the base must appear first).
8. **CRITICAL: Verify Properties.sol has NO Foundry cheatcodes.**
   Run: `grep -n "vm\.snapshot\|vm\.revertTo\|vm\.load" test/recon/Properties.sol`
   This MUST return zero results. If any are found, move them to `FoundryProperties.sol`.

**Phase 3A must compile cleanly before Phase 3B starts.** If compilation fails after 3 fix cycles, document blockers and proceed with what compiles.

---

## V4.0 MANDATORY RULES

The following rules are new in v4.0 and MUST be applied to every property implemented in this phase.

### RULE: ACTOR_GHOST_GUARD (v4 — MANDATORY)

Any property comparing `_before` and `_after` values for a specific actor (not global totals) MUST include as the first line:

```solidity
if (!_actorConsistent) return; // actor switched mid-call, ghosts invalid
```

This prevents false positives from `switchActor()` calls between `__before()` and `__after()`. The `_actorConsistent` flag is set automatically by both `updateGhosts` and `trackOp` modifiers in BeforeAfter.sol.

---

### RULE: ADDRESS_ZERO_GUARD (v4 — MANDATORY)

Any property that reads state from a contract variable (e.g., `vaultProxy.totalSupply()`) MUST guard:

```solidity
if (address(vaultProxy) == address(0)) return; // not initialized
```

This prevents false positives from incomplete setup wiring and separates "property untestable" from "property failed."

---

### RULE: TOLERANCE_JUSTIFICATION (v4 — MANDATORY)

When writing a property with additive tolerance (`+1`, `+2`) or relative tolerance, the `coded-properties.md` entry MUST include a tolerance justification:

```markdown
| MATH-RAY-03 | `x + 2` | Each rayMul/rayDiv introduces ±1 rounding; 2-step round-trip = +2 max |
```

Properties with unjustified tolerance MUST be flagged for review. Guidelines:
- Count rounding operations in the code path (each mulDiv* = ±1 unit)
- Guard degenerate inputs: `if (x < 1000 || y == 0) return;`
- Prefer relative + absolute: `result <= expected + expected/1e6 + DUST`
- For index-based accounting: always allow ±1 per index operation

---

### RULE: FP-PREVENTION PATTERNS (v4.1 — prevents systematic false positives)

The following implementation patterns address the 5 most common false positive root causes identified across fuzzing campaigns. Apply the relevant pattern whenever implementing properties in the listed categories.

**Pattern FP-1: Deduplicating actor sets in balance summation**

When summing balances across actors plus additional protocol addresses (feeRecipient, treasury, `address(this)`), always deduplicate to prevent double-counting if any protocol address is also an actor.

```solidity
// CORRECT: deduplicate before summing
uint256 sum = 0;
address[] memory allActors = _getActors();
for (uint i; i < allActors.length; i++) {
    sum += vault.balanceOf(allActors[i]);
}
// Add protocol addresses only if NOT already in actor set
address fr = vault.feeRecipient();
bool frInActors = false;
for (uint i; i < allActors.length; i++) {
    if (allActors[i] == fr) { frInActors = true; break; }
}
if (!frInActors) sum += vault.balanceOf(fr);
```

**When to apply:** Any SOL-* or AGG-* property that sums `balanceOf` across actors and also includes protocol-level addresses (feeRecipient, treasury, vault itself). See AP-15.

---

**Pattern FP-2: Operation-gated idle balance checks**

Never check idle balance (token balance of vault/contract) as a standalone global property. Gate on specific operations that should flush idle tokens.

```solidity
// CORRECT: only check after ops that should flush idle tokens
function property_no_idle_balance() public {
    if (currentOperation == bytes4(0)) return; // standalone call, skip
    if (currentOperation == SUBMIT_CAP) return; // admin op, skip
    if (currentOperation == SET_FEE) return;    // admin op, skip
    // Only runs after deposit/withdraw/mint/redeem/reallocate
    uint256 idle = token.balanceOf(address(vault));
    uint256 wqLen = vault.withdrawQueueLength();
    t(idle <= wqLen * 1, "idle balance exceeds expected rounding dust");
}
```

**When to apply:** Any property checking token balance held by a contract against a threshold. See AP-16.

---

**Pattern FP-3: NEGATIVE precondition guards**

Before asserting that an operation must revert, verify that the operation would actually have a meaningful effect in the current state. No-op edge cases (zero amounts, empty positions) may legitimately succeed.

```solidity
// CORRECT: verify the operation would have an effect before asserting revert
function property_neg_unbalanced_reallocate_reverts() public {
    Id id = MarketParamsLib.id(marketParams);
    // Precondition: position exists (operation would actually withdraw)
    if (morpho.supplyShares(id, address(vault)) == 0) return; // no-op edge, skip
    // Now the reallocate would actually withdraw, so it SHOULD revert
    try vault.reallocate(invalidAllocations) {
        t(false, "unbalanced reallocate should revert");
    } catch {
        // expected
    }
}
```

**When to apply:** All VT-NEG-* properties. See AP-18. Common no-op edges: zero-from-zero withdrawals, self-approvals, operations on empty positions.

---

**Pattern FP-4: Interest-aware cap checks**

When checking that a value stays below a cap (e.g., market supply <= supply cap), account for passive interest growth that can push the value above the cap without any new deposits.

```solidity
// CORRECT: account for passive interest growth exceeding static cap
// Interest accrual can push supplyAssets above cap without any new deposits.
// At 50% APR over ~4.5 years of simulated time, growth factor ≈ 10x.
uint256 maxGrowthFactor = 10; // generous bound for simulated time ranges
t(supplyAssets <= uint256(cap) * maxGrowthFactor + 1e18,
    "supply within cap accounting for interest growth");
```

**When to apply:** Any VS-* or MON-* property comparing a growing value (debt, supply, accrued interest) against a fixed cap. See AP-17. Document the growth factor derivation in a comment.

---

**Pattern FP-5: PROFIT with yield awareness**

When implementing PROFIT-01 for protocols where users legitimately earn yield, exclude earned yield from the extraction check.

```solidity
// CORRECT: exclude legitimately earned yield
// Option A (simple): only check zero-participation actors
address[] memory allActors = _getActors();
for (uint256 a = 0; a < allActors.length; a++) {
    if (_totalDeposited[allActors[a]] > 0) continue; // skip actors who used the vault
    int256 netExtraction = 0;
    for (uint256 t = 0; t < allTokens.length; t++) {
        uint256 current = IERC20(allTokens[t]).balanceOf(allActors[a]);
        uint256 initial = _initialBalances[allActors[a]][allTokens[t]];
        netExtraction += int256(current) - int256(initial);
    }
    t(netExtraction <= int256(DUST_TOLERANCE), "PROFIT-01: non-depositor extracted value");
}

// Option B (precise): track deposits/withdrawals per actor
for (uint256 a = 0; a < allActors.length; a++) {
    int256 netExtraction = int256(currentBalance + sharesValue) - int256(initialBalance);
    int256 netDeposits = int256(_totalDeposited[allActors[a]]) - int256(_totalWithdrawn[allActors[a]]);
    t(netExtraction - netDeposits <= int256(DUST_TOLERANCE), "PROFIT-01: extraction exceeds deposits");
}
```

**When to apply:** All PROFIT-01 implementations in vault/lending/staking protocols where yield accrual is expected. See PROFIT_YIELD_AWARENESS rule in Phase 1A.

---

### RULE: DELEGATION_TRACKING (v4 — MANDATORY)

When writing properties that track cumulative state (profit tracking, net deposits, share accounting), identify ALL delegation patterns:
- `onBehalfOf` parameters (Aave/Morpho supply/deposit/borrow)
- `from`/`to` that differ from `msg.sender`
- Fee recipients receiving shares without calling functions

Tracking variables MUST be conditioned on the actual token flow, not the accounting credit:
```solidity
// WRONG: tracks regardless of who sends tokens
_netDeposited[asset] += amount;

// CORRECT: only track when this contract sends tokens
if (msg.sender == address(this)) {
    _netDeposited[asset] += amount;
}
```

For share conservation properties, use `<=` (not `==`) if system addresses (fee recipients) are untracked.

---

### RULE: STALE_LIVE_CONSISTENCY (v4 — MANDATORY)

In protocols with lazy interest accrual (Aave, Compound, Morpho), all values in a property assertion MUST use the same temporal reference:
- BOTH live: call the protocol's normalized getters (e.g., `getReserveNormalizedVariableDebt()`)
- BOTH stored: raw storage fields with precondition `block.timestamp == lastUpdate`
- Or force update: call `accrueInterest()` in `__before()` to synchronize

---

### RULE: MSG_SIG_WRAPPER_AUDIT (v4 — MANDATORY)

When implementing INLINE properties that filter on `_before.sig` or `_after.sig`:

**Problem:** `msg.sig` captures the selector of the OUTERMOST call in the transaction,
which is the target function wrapper (e.g., `yVault_deposit_clamped`), NOT the
underlying protocol function (e.g., `IyVault.deposit`). If the property checks
`_after.sig == IyVault.deposit.selector`, it will NEVER match when the fuzzer calls
through a wrapper — creating a silent false positive (the property body never executes).

**Rule:** For every INLINE property that gates on `_before.sig == X.func.selector`:

1. **List ALL target function wrappers** that ultimately call `func`:
   - Direct wrappers: `yVault_deposit(amount)` → `vault.deposit(amount)`
   - Clamped wrappers: `yVault_deposit_clamped(amount)` → clamp → `vault.deposit(amount)`
   - Shortcut wrappers: `shortcut_deposit_then_earn(amount)` → `vault.deposit(amount)` + `vault.earn()`

2. **Check which wrappers have `updateGhosts`**: Only wrappers with `updateGhosts`
   set `_before.sig`. If a clamped wrapper does NOT have `updateGhosts` but calls an
   inner function that does, `_before.sig` will be the INNER function's selector
   (correct). But if the clamped wrapper itself has `updateGhosts`, `_before.sig` will
   be the WRAPPER's selector (incorrect for the property gate).

3. **Choose the correct approach** based on the wrapper analysis:

   **Option A (preferred): Delta-based gating** — Replace selector filtering with
   observable state change detection:
   ```solidity
   // Instead of: if (_after.sig == IyVault.deposit.selector)
   // Use:
   if (_after.vaultTotalSupply > _before.vaultTotalSupply) {
       // A deposit occurred — check deposit invariants
   }
   ```
   This works regardless of which wrapper was called.

   **Option B: Multi-selector OR** — Include ALL wrapper selectors in the guard:
   ```solidity
   if (_after.sig == IyVault.deposit.selector ||
       _after.sig == this.yVault_deposit_clamped.selector ||
       _after.sig == this.shortcut_deposit_then_earn.selector) {
       // ...
   }
   ```
   This is fragile — breaks whenever a new wrapper is added.

   **Option C: trackOp delegation** — Use `currentOperation` from trackOp instead of
   `msg.sig`. Wrappers call the inner function which has `trackOp(DEPOSIT)`, so
   `currentOperation` reflects the actual operation, not the wrapper.

   Prefer Option A > C > B.

4. **Document the choice** in `coded-properties.md`:
   ```
   MSG_SIG_AUDIT: Uses delta-based gating (Option A) — immune to wrapper selectors.
   ```

---

### Step 0F Addition: ProfitTracker — Delegation-Aware Implementation (v4)

When implementing ProfitTracker or net-deposit tracking (from Step 0F above):

1. **Identify all onBehalfOf/delegation patterns** in the protocol's deposit/supply/borrow functions
2. **Track actual token sender**, not position beneficiary:
   ```solidity
   function lendingPool_deposit(address asset, uint256 amount, address onBehalfOf) external {
       // Only track when THIS contract sends tokens
       if (msg.sender == address(this)) {
           _netDeposited[asset] += amount;
       }
       lendingPool.deposit(asset, amount, onBehalfOf, 0);
   }
   ```
3. **Track fee recipients in share conservation**: Include `feeRecipient`, `address(0)`, and `treasury` in summation, or use `<=` instead of `==`
4. **Track setup mints**: Use existing `_ghost_setupMinted[token]` to offset direct mints during setup

---

## Contract Variable Guards (REQUIRED)

### The Problem
`_deployLegacy()` may return `address(0)` if the target constructor reverts internally
(e.g., calls an external contract that doesn't exist at that address in the test env).
`new Contract()` can also leave a variable at `address(0)` if a conditional deployment
path is never triggered. Properties that call `.balance`, `.balanceOf()`, or any view
on an uninitialised variable will get empty/default return data — causing spurious
pass/fail.

### Rule
For **every** property that reads from a protocol contract variable, the **first line**
must be a zero-address guard:
```solidity
if (address(contractVar) == address(0)) return; // not initialized
```
Add one guard per contract variable accessed. If a property reads N contract variables,
it needs N guards at the top.

---

## Access Control False Positives (PRIV Properties)

### The Problem
`ActorManager` always includes `address(this)` (the test contract, e.g. CryticTester)
in the actor set and sets it as the initial `_actor`. This means:

- Any target function with `asActor` that assigns a role to `_getActor()` can
  make `address(this)` a privileged holder.
- PRIV properties that then prank `_getActor()` and call a restricted function will
  **succeed legitimately** — the actor really does hold the role.
- This looks like a property failure but is a false positive.

### Rule
In every PRIV / access-control property, before pranking and calling the restricted
function, add TWO guards:
```solidity
address actor = _getActor();
if (address(target) == address(0)) return;              // not initialized
if (actor == target.getPrivilegedRole()) return;        // actor already has the role
vm.prank(actor);
try target.restrictedFunction(...) {
    t(false, "PRIV-XX: non-holder called restricted function");
} catch {}
```
Replace `target.getPrivilegedRole()` with the actual view function that returns the
current holder (e.g. `getAccessor()`, `owner()`, `getManager()`). Check dynamically —
role assignments can change during the fuzzing campaign.
