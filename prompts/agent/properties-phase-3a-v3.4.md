---
description: "Phase 3A of the Efficient Properties Workflow v3.4. Fixes ghost infrastructure (Step 0) and implements SIMPLE + CANARY properties. Runs forge build to verify compilation before Phase 3B."
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

## Output

Write implemented properties to `Properties.sol` (or `Properties2.sol` if the file header contains `COMPARISON_MODE: true`).

List every property you wrote and the diff of the changes in `magic/coded-properties.md`.

**IMPORTANT:** After implementing all properties in this phase, run `forge build` to verify compilation. Phase 3B depends on your code compiling cleanly.

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

---

## Rules to Implement All Properties

- Use Chimera Asserts whenever possible (`lib/Chimera/Asserts`):
  - `t(bool condition, string message)` — assert condition is true
  - `eq(uint256 a, uint256 b, string message)` — assert a == b
  - `gte(uint256 a, uint256 b, string message)` — assert a >= b
  - `lte(uint256 a, uint256 b, string message)` — assert a <= b

- Whenever you cannot use `eq` due to types, use `t` and add a comment explaining why

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

## Phase 3A Scope: CANARY + SIMPLE Properties Only

This phase implements the following property types:

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

## Error Recovery

If `forge build` fails, classify the error:

| Error Type | Example | Action |
|-----------|---------|--------|
| Missing import | "Identifier not found" | Add import from parent contract or lib/ |
| Wrong function signature | "Member not found" | Check actual protocol API in dependency list |
| Type mismatch | "Type uint256 not implicitly convertible" | Use explicit cast or t() instead of eq() |
| using-for needed | "Member function not found" | Add `using LibName for TypeName` |
| Overflow in constant | "Literal too large" | Use unchecked block or split computation |
| UNRECOVERABLE | "Contract too large" | Move properties to Properties2.sol extension |

After fixing, re-run `forge build`. Max 3 fix-compile cycles per batch.
If still failing after 3 cycles, move remaining properties to `magic/properties-blocker.md`.

---

## Handling BLOCKED_BY_INFRASTRUCTURE Properties

For properties marked `BLOCKED_BY_INFRASTRUCTURE` in the second pass:
1. Check if you can add the required infrastructure in Setup.sol
2. If infrastructure can be added feasibly, add it and implement the property
3. If infrastructure cannot be added, skip the property and document it:
```solidity
// BLOCKED_BY_INFRASTRUCTURE: SPOKE-HF-01
// Requires: Spoke contract deployment, Oracle mock
// To enable: Add Spoke deployment to Setup.sol
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
2. Verify `updateGhosts` was added to all core target functions (Step 0A)
3. Verify updateGhosts reset fix was applied if Category B functions exist (Step 0B)
4. Verify no tautological properties were implemented (spot-check against protocol require statements)
5. **CRITICAL: Verify NO unjustified arbitrary bounds** — search for:
   - `% 1e24`, `% 1e30`, `% 1e36` (arbitrary modulo)
   - `+ 1e18` in mint/transfer calls (arbitrary buffer)
   - `* 1e27` in tolerance calculations (excessive tolerance)
   - Any hardcoded large numbers not from protocol constants

**Phase 3A must compile cleanly before Phase 3B starts.** If compilation fails after 3 fix cycles, document blockers and proceed with what compiles.
