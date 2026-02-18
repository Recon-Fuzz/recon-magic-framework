---
description: "Phase 3B of the Efficient Properties Workflow v3.4. Implements INLINE + NEGATIVE + DOOMSDAY properties, building on Phase 3A's verified infrastructure. Includes error recovery decision tree."
mode: subagent
temperature: 0.1
---

## Role
You are the @properties-phase-3b agent.

We're specifying properties for the smart contract system in scope.

## Inputs

Read these files:
1. `magic/properties-efficient-second-pass.md` — validated properties with INFRASTRUCTURE STATUS
2. Find and read `Properties.sol` (or `Properties2.sol`) — **Phase 3A already implemented SIMPLE + CANARY properties here**
3. Find and read the BeforeAfter contract — Phase 3A may have applied the updateGhosts reset fix
4. Find and read the TargetFunctions contract — Phase 3A may have added `updateGhosts` modifiers
5. Find and read `magic/coded-properties.md` — Phase 3A's implementation log

**CRITICAL:** Phase 3A has already:
- Fixed ghost infrastructure (Step 0A/0B/0C)
- Implemented all SIMPLE properties (SOL, MON, MATH, ER, VS)
- Implemented all CANARY properties
- Verified compilation with `forge build`

Your job is to implement the remaining property types: INLINE, NEGATIVE, and DOOMSDAY.

## Output

**Append** your implementations to the existing `Properties.sol` (or `Properties2.sol`).

**Update** `magic/coded-properties.md` with the new properties you implemented.

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
- **Minting:** Use exact amounts or compute exact requirement. Never `amount + 1e18`.
- **Tolerance:** Use minimal justified values (`entityCount` units, 1 wei). Never `entityCount * 1e27`.
- **Growth bounds:** Document rationale in a comment.
- **Protocol caps:** Use actual protocol-defined values.

---

## Phase 3B Scope: INLINE + NEGATIVE + DOOMSDAY Properties

### VT-* (TIER 7A: Variable Transition Positive — INLINE)
Filter by `_before.sig` to apply checks only after specific function calls.
```solidity
function property_HUB_VT_01_addIncreasesLiquidity() public {
    if (_before.sig == hub.add.selector) {
        gte(_after.totalLiquidity, _before.totalLiquidity,
            "HUB-VT-01: add must increase liquidity");
    }
}
```

**Ghost Directional Consistency Rules (CRITICAL — prevents incorrect inline properties):**

When writing ghost-based properties that check the DIRECTION of state changes (e.g., "if supply went up, underlying should also go up"), you MUST account for ALL legitimate operations that can cause each direction:

1. **List ALL operations that affect each ghost variable** (supply, underlying, debt, index, etc.)
2. **For each operation, document the expected direction** of each variable
3. **If multiple variables can move in opposite directions during a LEGITIMATE operation**, the property MUST check the other variables to distinguish legitimate from buggy behavior

**Example of an INCORRECT directional property:**
```solidity
// WRONG: Assumes supply and underlying always move together
// FAILS on borrow: supply UP (interest accrual) + underlying DOWN (tokens sent to borrower)
if (_after.supply > _before.supply && _after.underlying < _before.underlying) {
    return false;
}
```

**Example of a CORRECT directional property:**
```solidity
// RIGHT: Accounts for debt changes AND index accrual
if (_after.supply > _before.supply && _after.underlying < _before.underlying) {
    // Check 1: Debt increase explains supply up + underlying down
    if (_after.totalDebt > _before.totalDebt) return true;
    // Check 2: Liquidity index increase explains supply up (reserve.updateState() accrual)
    if (_after.liquidityIndex > _before.liquidityIndex) return true;
    // Neither debt nor index explains it — genuine violation
    return false;
}
```

**CRITICAL — Interest Accrual Trap in Lending Protocols:**

In protocols like Aave, Compound, and similar, every state-changing operation
calls `reserve.updateState()` (or `accrueInterest()`) at the START of the function.
This updates the liquidity index, which increases `aToken.totalSupply()` (via
`scaledTotalSupply * liquidityIndex / RAY`) **without moving any underlying tokens**.

This means between `_before()` and `_after()` of ANY operation:
1. `liquidityIndex` increases (if time has passed since last update)
2. `aTokenSupply` increases (proportional to index increase)
3. `underlying` does NOT change from accrual alone — only from actual token transfers
4. **Stable debt `totalSupply()`** is computed from `block.timestamp` — within the
   SAME transaction, `_before` and `_after` see the SAME stable debt value, so
   `afterDebt == beforeDebt` even though interest accrued. This is because the
   view function uses the current block's timestamp for both snapshots.

**Consequence**: A simple "debt increased → OK" check is NOT sufficient. You must
ALSO check if `liquidityIndex` increased, because that explains supply increases
that debt snapshots cannot capture within the same transaction.

**When NOT to use directional ghost properties:**
- If every operation triggers index accrual, directional consistency between supply
  and underlying is inherently noisy. Consider using operation-specific inline
  properties (filtered by selector) instead.

**Operation-direction matrix for lending protocols:**
| Operation | aToken Supply | Underlying | Debt | Index | Notes |
|-----------|:---:|:---:|:---:|:---:|-------|
| Deposit | UP | UP | — | UP (accrual) | Both increase by deposit amount + accrual |
| Withdraw | UP (accrual) then DOWN | DOWN | — | UP (accrual) | Net depends on accrual vs withdrawal |
| Borrow | UP (accrual) | DOWN | UP | UP (accrual) | Interest accrual + underlying sent to borrower |
| Repay | UP (accrual) | UP | DOWN | UP (accrual) | Interest accrual + underlying returned |
| Liquidation | COMPLEX | COMPLEX | DOWN | UP (accrual) | Depends on collateral vs debt side |
| Flash loan | UP (premium+accrual) | UP (premium) | — | UP (accrual) | Premium adds to both |
| Any no-op | UP (accrual) | — | SAME within tx | UP (accrual) | updateState() alone increases supply via index |

### VT-NEG-* (TIER 7B: Variable Transition Negative — NEGATIVE)
Use try/catch for revert checks.
```solidity
function property_HUB_VT_NEG_01_addZeroReverts() public {
    try hub.add(0) {
        t(false, "HUB-VT-NEG-01: add(0) should revert");
    } catch {
        t(true, "HUB-VT-NEG-01: add(0) correctly reverts");
    }
}
```

### HF-* (TIER 3: Health Factor — NEGATIVE)
Use try/catch to verify healthy positions cannot be liquidated.
```solidity
function property_SPOKE_HF_01_healthyCannotBeLiquidated(address user) public {
    uint256 hf = spoke.getUserHealthFactor(user);
    if (hf < HEALTH_FACTOR_THRESHOLD) return;

    try spoke.liquidationCall(collateralId, debtId, user, 1e18, false) {
        t(false, "SPOKE-HF-01: Healthy position was liquidated");
    } catch {
        t(true, "SPOKE-HF-01: Healthy position correctly protected");
    }
}
```

### LIQ-* (TIER 4: Liquidation Blocking — NEGATIVE)
Use try/catch to verify invalid liquidations revert.
```solidity
function property_SPOKE_LIQ_01_selfLiquidationBlocked() public {
    try spoke.liquidationCall(collateralId, debtId, msg.sender, 1e18, false) {
        t(false, "SPOKE-LIQ-01: Self-liquidation should be blocked");
    } catch {
        t(true, "SPOKE-LIQ-01: Self-liquidation correctly blocked");
    }
}
```

### FEE-* (TIER 9: Fee Accrual — INLINE)
```solidity
function property_HUB_FEE_01_feeReceiverGetsAccrued() public {
    if (_before.sig == hub.accrueInterest.selector) {
        if (_after.lastAccrualTime > _before.lastAccrualTime) {
            gte(_after.feeReceiverBalance, _before.feeReceiverBalance,
                "HUB-FEE-01: fee receiver must receive accrued fees");
        }
    }
}
```

### ST-* (TIER 11: State Transition — INLINE)
```solidity
function property_HUB_ST_01_onlyAddIncreasesLiquidity() public {
    if (_after.totalLiquidity > _before.totalLiquidity) {
        t(_before.sig == hub.add.selector || _before.sig == hub.accrueInterest.selector,
            "HUB-ST-01: unexpected liquidity increase");
    }
}
```

### PERIPH-* (TIER 13: Peripheral — INLINE)
```solidity
function property_PERIPH_01_viewMatchesActual() public {
    if (hub.lastAccrualTime() != block.timestamp) return;
    uint256 viewResult = peripheralLib.expectedBalance(address(hub));
    uint256 actual = token.balanceOf(address(hub));
    eq(viewResult, actual, "PERIPH-01: view must match actual");
}
```

### DOOM-* (TIER 10: Liveness — DOOMSDAY)
Use vm.snapshot()/vm.revertTo() to avoid state mutation.
```solidity
function property_DOOM_01_canWithdrawDeposit() public {
    uint256 userBalance = hub.balanceOf(msg.sender);
    if (userBalance == 0) return;
    uint256 available = hub.availableLiquidity();
    if (available < userBalance) return;

    uint256 snapshot = vm.snapshot();
    try hub.withdraw(userBalance, msg.sender, msg.sender) {
        t(true, "DOOM-01: Withdrawal succeeded");
    } catch {
        t(false, "DOOM-01: User with deposit cannot withdraw");
    }
    vm.revertTo(snapshot);
}
```

**DOOM Precondition Guards (CRITICAL — prevents admin-induced false positives):**

DOOM properties test that critical operations (withdraw, repay, liquidate) ALWAYS succeed when their preconditions are met. However, if ADMIN scaffold targets are still present (e.g., `setPoolPause`, `freezeReserve`), the fuzzer can trivially break DOOM properties by calling an admin function first.

**REQUIRED**: Every DOOM property MUST guard against admin-induced states:

```solidity
function property_DOOM_01_canWithdrawDeposit() public {
    // Guard: skip if admin has put protocol in non-standard state
    if (pool.paused()) return;           // Admin paused
    // if (reserve.frozen()) return;     // Admin froze reserve
    // if (address(oracle) == address(0)) return; // Admin zeroed oracle

    uint256 userBalance = hub.balanceOf(msg.sender);
    if (userBalance == 0) return;
    // ... rest of property
}
```

If Step 0D in Phase 3A already removed all conflicting admin targets, these guards are redundant but harmless. Always add them as defense-in-depth.

---

## Stale-Op Awareness

Phase 3A applied the updateGhosts reset fix (Step 0B) or stale-op guards (Step 0C). When implementing INLINE properties:

- If the reset fix was applied: No additional guards needed — `currentOperation` is zeroed for Category B functions.
- If stale-op guards were used instead: Add consistency preconditions to any STALE_OP_RISK-flagged property:
  ```solidity
  function property_deposit_increases_shares() public {
      if (currentOperation == SelectorStorage.DEPOSIT) {
          // Consistency precondition: deposit should increase totalSupply
          if (_after.totalSupply <= _before.totalSupply) return;
          t(_after.actorShareBalance > _before.actorShareBalance, "deposit must increase shares");
      }
  }
  ```

Check `magic/properties-efficient-second-pass.md` for STALE_OP_RISK flags on each property.

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

1. **Append** to the existing Properties.sol that Phase 3A created
2. The inheritance chain: TargetFunctions -> Properties -> BeforeAfter -> Setup
3. Do NOT modify Phase 3A's existing property functions

### Naming Convention

Use the architectural prefix in function names:
```solidity
function property_HUB_VT_01_addIncreasesLiquidity() public { ... }
function property_SPOKE_HF_02_zeroDebtMaxHF() public { ... }
function property_DOOM_01_canWithdrawDeposit() public { ... }
```

---

## Verification Steps (Phase 3B)

1. `forge build` — must compile without errors
2. `forge test` — existing tests must still pass
3. Verify INLINE properties filter by correct function selectors
4. Verify negative tests use try/catch pattern (not positive assertions)
5. Verify DOOM properties use vm.snapshot()/vm.revertTo()
6. Verify STALE_OP_RISK properties have guards (if reset fix was NOT applied)
7. **CRITICAL: Verify NO unjustified arbitrary bounds** — search for:
   - `% 1e24`, `% 1e30`, `% 1e36` (arbitrary modulo)
   - `+ 1e18` in mint/transfer calls (arbitrary buffer)
   - `* 1e27` in tolerance calculations (excessive tolerance)
   - Any hardcoded large numbers not from protocol constants

If compilation fails, apply the error recovery process above. If you cannot implement a property due to code limitations, add it to `magic/properties-blocker.md` with the reason.
