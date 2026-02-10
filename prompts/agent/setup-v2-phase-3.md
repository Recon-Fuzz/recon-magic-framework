---
description: "Setup V2 Phase 3: Validate setup with compilation and tests"
mode: subagent
temperature: 0.1
---

# Setup V2 Phase 3: Validation

## Role
You are the @setup-v2-phase-3 agent. Your job is to validate the setup by running compilation and tests, fixing any issues that arise.

## Prerequisites

- Phase 2 complete (Setup.sol implemented)

---

## Step 1: Compile

```bash
forge build
```

### If Compilation Fails

Read the error message and fix:

**Import error:**
```
Error: Source "..." not found
```
→ Add missing import or fix remapping

**Type error:**
```
Error: Type ... is not implicitly convertible to ...
```
→ Add explicit cast or fix type

**Undeclared identifier:**
```
Error: Undeclared identifier
```
→ Add missing variable declaration or import

After each fix, re-run `forge build` until successful.

---

## Step 2: Run CryticToFoundry Test

```bash
forge test --match-contract CryticToFoundry -vvv
```

This runs the Foundry test harness which calls `setup()`.

### Expected Output

```
[PASS] test_crytic() ...
```

### If Setup Reverts

Run with more verbosity:
```bash
forge test --match-contract CryticToFoundry -vvvv
```

Look for the revert reason in the trace.

---

## Step 3: Common Setup Issues and Fixes

### Issue: "Arithmetic overflow/underflow"

**Cause:** Math operation with insufficient values
**Fix:** Ensure initial values are set before operations

```solidity
// Before: oracle.price() returns 0, causing division issues
// Fix: Set price before deploying dependent contracts
oracle.setPrice(1e18);
vault = new Vault(address(oracle), ...);
```

### Issue: "Ownable: caller is not the owner"

**Cause:** Post-deploy action called from wrong address
**Fix:** Ensure `address(this)` is the owner

```solidity
// Constructor should set address(this) as owner
vault = new Vault(address(this), ...);

// Now post-deploy calls work
vault.setFee(100);
```

### Issue: "ERC20: insufficient allowance"

**Cause:** Token transfer without approval
**Fix:** Ensure contract is in approval array

```solidity
address[] memory approvalArray = new address[](1);
approvalArray[0] = address(vault);  // Add vault to get approvals
_finalizeAssetDeployment(_getActors(), approvalArray, type(uint88).max);
```

### Issue: "ERC20: transfer amount exceeds balance"

**Cause:** Trying to transfer more than minted
**Fix:** `_finalizeAssetDeployment` mints `type(uint88).max` to each actor, which should be sufficient. If not, check if custom token needs separate minting.

### Issue: "Invalid initialization"

**Cause:** Upgradeable contract initialized twice
**Fix:** Call `initialize()` only once, after proxy deployment

### Issue: "Address: low-level call failed"

**Cause:** Calling function on wrong address or uninitialized contract
**Fix:** Check deployment order and address assignments

---

## Step 4: Run Echidna

Echidna validation is **required** to confirm the fuzzing setup works correctly.

```bash
echidna test/recon/CryticTester.sol --contract CryticTester --config echidna.yaml
```

### 4.1 Ensure echidna.yaml Exists

If no `echidna.yaml` exists, create one per `${PROMPTS_DIR}/styleguide.md`:

```yaml
testMode: "assertion"
prefix: "optimize_"
coverage: true
corpusDir: "echidna"
balanceAddr: 0x1043561a8829300000
balanceContract: 0x1043561a8829300000
filterFunctions: []
cryticArgs: ["--foundry-compile-all"]
deployer: "0x1804c8AB1F12E6bbf3894d4083f33e07309d1f38"
contractAddr: "0x7FA9385bE102ac3EAc297483Dd6233D62b3e1496"
shrinkLimit: 100000
```

### 4.2 Expected Output

Echidna should:
1. Compile the contracts
2. Deploy via `Setup.setup()`
3. Run fuzzing without crashes
4. Report property results (may show "passing" or "failed" - both are valid at this stage)

**Success looks like:**
```
Analyzing contract: test/recon/CryticTester.sol:CryticTester
Running 1 test(s)...
echidna_revert_test: passing
```

### 4.3 Common Echidna Issues and Fixes

**IMPORTANT**: Refer to `${PROMPTS_DIR}/styleguide.md` for authoritative fix patterns. Key rules:

1. **NEVER modify `echidna.yaml`** except for library linking
2. Always use `AssetManager` and `ActorManager`
3. Constructor must be `payable`

---

**"Error: Contract not found"**
→ Check contract name in command matches contract in file

**"Error: Setup reverted"**
→ Same as Foundry test failure - debug with forge test first

**"Error: Could not compile"**
→ Check `forge build` works, ensure cryticArgs has `--foundry-compile-all`

**"Error: Could not compile" (but forge works)**
→ Check `dynamic_test_linking` in foundry.toml - disable it if true

**"Error: No tests found"**
→ Ensure CryticTester inherits from TargetFunctions and has at least one property

**Library linking errors:**
→ Add libraries to echidna.yaml per `${PROMPTS_DIR}/styleguide.md`:
```yaml
cryticArgs: ["--foundry-compile-all", "--compile-libraries=(LibName,0xf01)"]
deployContracts: [["0xf01", "LibName"]]
```

**AccessControl reverts (missing role):**
→ Per `${PROMPTS_DIR}/styleguide.md`, grant roles in Setup.sol:
```solidity
vm.prank(admin);
contractName.grantRole(contractName.ROLE_NAME(), appropriateAddress);
```

**Property immediately fails (not due to bug):**
→ Check property implementation - may need setup fixes

**Echidna hangs or runs forever:**
→ Set `testLimit` in echidna.yaml to bound execution

**Echidna compilation is slow:**
→ Expected - Echidna can take multiple minutes to compile

### 4.4 Debug Echidna Failures

If Echidna fails but Foundry passes:

1. Check for non-determinism (block.timestamp, randomness)
2. Check for Echidna-specific constraints (sender addresses)
3. Run with `--format text` for detailed output:
   ```bash
   echidna test/recon/CryticTester.sol --contract CryticTester --config echidna.yaml --format text
   ```

4. Check the corpus for failing sequences:
   ```bash
   ls echidna-corpus/
   ```

---

## Step 5: Create Setup Notes

After validation succeeds, create `magic/setup-notes.md`:

```markdown
# Setup Notes

## Contracts Deployed

### FULL (Real Implementations)
- `vault` - Vault.sol - Main contract under test
- `token` - MockERC20 via AssetManager

### MOCK (Simplified)
- `oracle` - OracleMock - Price feed mock

### ABSORB (Pranked)
- `liquidator` - address(0x11Q) - For liquidation calls

## Configuration

| Parameter | Value | Reason |
|-----------|-------|--------|
| fee | 100 (1%) | Enables fee collection without edge cases |
| oracle.price | 1e18 | Non-zero for normal operation |

## Post-Deploy Actions
1. `vault.initialize()` - Required for upgradeable pattern
2. `oracle.setPrice(1e18)` - Initial price

## Actors
- `address(this)` - Admin/owner
- `address(0x10000)` - User actor

## Known Limitations
- External oracle not connected (using mock)
```

---

## Success Criteria

Phase 3 is complete when:
- [ ] `forge build` succeeds
- [ ] `forge test --match-contract CryticToFoundry -vvv` passes
- [ ] `echidna` runs without setup crashes (properties may pass or fail)
- [ ] `magic/setup-notes.md` created

---

## Output

Report:
- Compilation status: PASS/FAIL
- Foundry test status: PASS/FAIL
- Echidna status: PASS/FAIL (setup runs without crash)
- Issues fixed (if any)
- Setup notes location

If all validations pass:
```
Setup V2 Complete!

- forge build: PASS
- forge test: PASS
- echidna: PASS (setup runs)

Ready for Coverage Phase.
```

**STOP** after validation. Setup V2 is complete.
