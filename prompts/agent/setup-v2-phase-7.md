---
description: "Setup V2 Phase 7: Write unit tests to validate all handlers work"
mode: subagent
temperature: 0.1
---

# Setup V2 Phase 7: Write Unit Tests for All Handlers

## Role
You are the @setup-v2-phase-7 agent. Your job is to write Foundry unit tests that prove every handler can be called successfully with proper prerequisites.

## Prerequisites

- Phase 6 complete
- `magic/testing-order.json` exists
- `magic/function-sequences.json` exists

## CRITICAL: Where to Fix What

**NEVER use cheatcodes not defined in the `IHevm` interface.** See: https://github.com/Recon-Fuzz/chimera/blob/main/src/Hevm.sol

**Tests ONLY call handlers and `switchActor()`.** If a test fails, diagnose which layer is responsible:

| Error | Root Cause | Fix In |
|-------|-----------|--------|
| `ERC20: insufficient allowance` | Contract missing from approval array | **Setup.sol** — add to `approvalArray` |
| `ERC20: transfer amount exceeds balance` | Actor not receiving tokens | **Setup.sol** — ensure actor is in `_getActors()` before `_finalizeAssetDeployment()` |
| `Ownable: caller is not the owner` | Missing role/permission grant | **Setup.sol** — add `grantRole()` or `rely()` in post-deploy |
| `AccessControl: account is missing role` | Missing role grant for actor | **Setup.sol** — grant role to actors in post-deploy |
| `"No collateral"` or similar state dep | Missing prerequisite handler call | **Test** — add prerequisite handler calls before target |
| `"Position is healthy"` | Need external state change | **Test** — add implicit prerequisite (e.g. `oracle_setPrice`) |

**NEVER patch approval, balance, or permission issues in tests.** These are always Setup bugs:

```solidity
// WRONG — patching a Setup bug in the test
function test_vault_deposit() public {
    token.approve(address(vault), type(uint256).max);  // ✗ Fix Setup instead
    vault_deposit(1e18);
}

// WRONG — pranking instead of using switchActor
function test_vault_deposit() public {
    vm.prank(address(0x10000));  // ✗ Use switchActor instead
    vault_deposit(1e18);
}

// RIGHT — test only calls handlers and switchActor
function test_vault_deposit() public {
    switchActor(1);
    vault_deposit(1e18);
}
```

---

## Task

Write unit tests in `CryticToFoundry.sol` for ALL handlers in `testing-order.json`.

---

## Test Structure

### Rule 1: Use Handler Functions, Not Direct Calls

```solidity
// CORRECT - call the handler
function test_vault_deposit() public {
    vault_deposit(1e18);
}

// WRONG - don't call contract directly
function test_vault_deposit() public {
    vault.deposit(1e18);  // ✗ Never do this
}
```

### Rule 2: Call Prerequisites First

Use `function-sequences.json` to know what to call before each handler:

```solidity
function test_vault_borrow() public {
    // Prerequisites from function-sequences.json
    vault_supply(10e18);           // prerequisite 1
    vault_supplyCollateral(2e18);  // prerequisite 2

    // Now the target handler
    vault_borrow(1e18);
}
```

### Rule 3: Handle Implicit Prerequisites

For functions needing state changes (like liquidation):

```solidity
function test_vault_liquidate() public {
    // Setup a position
    vault_supply(10e18);
    vault_supplyCollateral(2e18);

    switchActor(1);  // Switch to borrower
    vault_borrow(1e18);

    // Make position unhealthy (implicit prerequisite)
    oracle_setPrice(1);  // Crash the price

    switchActor(0);  // Switch back to liquidator
    vault_liquidate(_getActors()[1], 1e18);
}
```

### Rule 4: Use Manager Functions

```solidity
// Get current actor/asset
address actor = _getActor();
address asset = _getAsset();

// Get specific actor/asset by index
address actor1 = _getActors()[0];
address actor2 = _getActors()[1];
address token1 = _getAssets()[0];

// Switch active actor
switchActor(1);
```

---

## Writing Tests

### Step 1: Read Testing Order

Load `magic/testing-order.json` to get the order:

```json
["vault_deposit", "oracle_setPrice", "vault_supply", "vault_borrow", "vault_liquidate"]
```

### Step 2: For Each Handler, Write a Test

```solidity
contract CryticToFoundry is TargetFunctions, Test {

    function setUp() public {
        setup();  // Call inherited setup
    }

    // Test 1: vault_deposit (no prerequisites)
    function test_vault_deposit() public {
        vault_deposit(1e18);
    }

    // Test 2: oracle_setPrice (no prerequisites)
    function test_oracle_setPrice() public {
        oracle_setPrice(1e18);
    }

    // Test 3: vault_supply (no prerequisites)
    function test_vault_supply() public {
        vault_supply(1e18);
    }

    // Test 4: vault_borrow (needs supply + collateral)
    function test_vault_borrow() public {
        vault_supply(10e18);
        vault_supplyCollateral(2e18);
        vault_borrow(1e18);
    }

    // Test 5: vault_liquidate (needs borrow + price crash)
    function test_vault_liquidate() public {
        vault_supply(10e18);

        switchActor(1);
        vault_supplyCollateral(2e18);
        vault_borrow(1e18);

        oracle_setPrice(1);  // Make unhealthy

        switchActor(0);
        vault_liquidate(_getActors()[1], 1e18);
    }
}
```

### Step 3: Run Each Test

After writing each test:

```bash
forge test --match-test test_vault_deposit -vvv
```

Fix any failures before moving to the next test.

---

## Handling Test Failures

### Failure Type A: Missing Prerequisite

```
Error: "No collateral"
```

**Fix:** Add the missing prerequisite call:
```solidity
vault_supplyCollateral(2e18);  // Add this
vault_borrow(1e18);
```

### Failure Type B: Setup Issue (approvals, balances, permissions, configuration)

These errors mean `Setup.sol` is incomplete. **ALWAYS fix in Setup.sol, NEVER in the test.**

```
Error: "Oracle not set"
Error: "ERC20: insufficient allowance"
Error: "ERC20: transfer amount exceeds balance"
Error: "Ownable: caller is not the owner"
Error: "AccessControl: account 0x... is missing role"
```

**Fix:** Modify `Setup.sol` to configure the missing component:
```solidity
// In Setup.setup()
vault.setOracle(address(oracle));          // missing config
approvalArray[1] = address(newContract);   // missing approval
vault.grantRole(DEPOSITOR, actors[0]);     // missing permission
```

**NEVER** add `token.approve()`, `token.mint()`, `vm.prank()`, or `grantRole()` in the test to work around these. If the test needs it, every fuzzing run needs it — so it belongs in Setup.

### Failure Type C: Justified Revert

Some functions are MEANT to revert when called by users:

```solidity
function notifyReward() external {
    require(msg.sender == rewardDistributor, "only distributor");
}
```

**Document in `magic/reverting-handlers.json`:**
```json
{
  "vault_notifyReward": {
    "reason": "Only callable by rewardDistributor contract",
    "justified": true
  }
}
```

**Do NOT keep failing tests for justified reverts.**

---

## Validation

Run all tests:

```bash
forge test --match-contract CryticToFoundry -vvv
```

All tests must pass (or be documented as justified reverts).

---

## Success Criteria

- [ ] Unit test exists for EVERY handler in `testing-order.json`
- [ ] All tests pass OR justified reverts documented
- [ ] Tests use handler functions, not direct contract calls
- [ ] Tests call prerequisites in correct order
- [ ] `magic/reverting-handlers.json` created if any justified reverts

---

## Output

Report:
- Total handlers tested
- Tests passing
- Justified reverts (if any)
- Final validation: `forge test --match-contract CryticToFoundry`

If all tests pass:
```
Setup V2 Complete!

All handlers validated. Ready for Coverage Phase.
```

Create `FUZZING_SETUP_COMPLETE.md` summarizing:
1. Contracts deployed
2. Handlers tested
3. Any justified reverts
4. Ready for Coverage Phase
