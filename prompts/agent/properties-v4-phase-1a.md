---
description: "Phase 1A of the Efficient Properties Workflow v4.2. Generates high-priority security-relevant properties for Tiers 0-17 (PROFIT through ACCUM) using inline mandatory patterns, condensed anti-patterns, reachability integration, protocol-type templates, cross-protocol templates, economic oracle integration, expanded economic oracles, taint-informed property prioritization, privilege escalation negative tests, share inflation pattern, math round-trip, deposit-withdraw sandwich resistance, weird token integration (Tier 16), precision loss accumulation (Tier 17), token compliance patterns (ERC20-E through H), state machine properties (CROSS-E/F/G), systematic auth sweep (PRIV-AUTH), and fee volume conservation (PATTERN 29)."
mode: subagent
temperature: 0.1
---

## Role
You are the @properties-phase-1a agent.

We're specifying properties for the smart contract system in scope.

## Inputs

First, read these Phase 0 outputs to understand the protocol:
- `magic/contracts-dependency-list.md` — all contracts, functions, storage slots, call relationships, **PROTOCOL_TYPE classification**, **TOKEN_ASSUMPTION**, **ISSUES_TOKENS**, **State Machine Patterns** (HAS_INITIALIZER, HAS_PAUSE, USES_UPGRADEABLE_PROXY), **Access Control Inventory**
- `magic/properties-review-priority.md` — review order by complexity
- `magic/reachability-analysis.md` (if it exists) — hard-to-reach branches and shortcut target functions
- `magic/economic-oracles.md` (if it exists) — economic vulnerability class analysis with per-class applicability
- `magic/dataflow-taint-analysis.md` (if it exists) — per-function taint classification (HIGH_TAINT, MEDIUM_TAINT, LOW_TAINT, NO_TAINT) informing property density

For each contract in the review priority list, generate security-relevant properties for fuzzing/invariant testing.

The goal is to produce a **COMPREHENSIVE SUPERSET** of properties covering BOTH:
1. **WIDE OPERATIONAL COVERAGE**: Per-function directional state changes, solvency invariants, valid states, exchange rate monotonicity, fee/reward consistency, state transitions, dust cleanup, balance consistency
2. **DEEP SECURITY PROPERTIES**: Mathematical rounding guarantees (with attack scenarios), position safety enforcement, liveness guarantees, peripheral library consistency

## Reachability Integration

**If `magic/reachability-analysis.md` exists**, apply these rules throughout property generation:
- For each MULTI-STEP or INDIRECT branch, create a CANARY property (Tier 1) to verify the fuzzer reaches it
- For each shortcut target function, create a VT property (Tier 7A) covering its state transitions
- Cross-reference DOOM properties (Tier 10) with reachability findings to ensure liveness paths are testable
- Prioritize canaries for the hardest-to-reach paths identified in the analysis

## Taint-Informed Property Prioritization (NEW in v3.6)

**Read `magic/dataflow-taint-analysis.md`** (if it exists). This file contains per-function exploitability classifications from Phase 0 Step 7.

### Property Density Rules by Taint Classification

Use taint classification to modulate the NUMBER and DEPTH of properties generated per function. This supplements (does NOT replace) the existing tier system — tiers determine WHAT KIND of properties, taint determines HOW MANY and HOW DEEP.

| Classification | Exploitability | Property Density | Property Types |
|---------------|---------------|------------------|----------------|
| **HIGH_TAINT** (>=6) | Deep taint propagation, multiple sources reaching critical sinks | **Min 4 properties/function** | Deep invariants, exact-delta VT (not just directional), cross-function state correlation, rounding direction properties, economic extraction checks |
| **MEDIUM_TAINT** (2-5) | Some taint propagation, limited sink exposure | **Min 2 properties/function** | Standard directional VT checks, boundary condition properties, basic solvency coverage |
| **LOW_TAINT** (1) | Minimal taint — single source, single shallow path | **CANARY-only** | Coverage verification canary to ensure fuzzer reaches the function. No deep properties needed. |
| **NO_TAINT** (0) | No taint sources reach any sinks | **Skip entirely** | View functions, pure helpers — no properties needed. Do not waste property budget on these. |

### Integration with Existing Tier System

Taint classification modulates density WITHIN each tier, it does not override tier selection:

1. **Tier 0 (PROFIT)**: Applied to ALL functions regardless of taint (universal oracle)
2. **Tier 1 (CANARY)**: LOW_TAINT functions get canaries; HIGH_TAINT functions get canaries for their hardest-to-reach paths
3. **Tiers 2-6 (Solvency, HF, Liquidation, Monotonicity, Math)**: These are GLOBAL properties — taint doesn't affect them
4. **Tier 7A (VT — Positive)**: HIGH_TAINT functions get EXACT-DELTA checks (not just directional `gte`/`lte`). MEDIUM_TAINT functions get standard directional checks. LOW_TAINT functions get canary-only.
5. **Tier 7B (VT — Negative)**: Focus negative tests on HIGH_TAINT functions — these are the most likely revert target for attacks
6. **Tiers 8-9 (Exchange Rate, Fees)**: HIGH_TAINT functions in these categories get additional cross-multiplication overflow checks and rounding direction verification
7. **Tier 10 (DOOM)**: Liveness properties for functions with ANY taint reaching critical sinks
8. **Tier 10B (Multi-Actor)**: HIGH_TAINT functions with shared mutable resources get reentrancy atomicity properties

### Graceful Fallback

**If `magic/dataflow-taint-analysis.md` does not exist**, behave exactly like v3.5 — apply standard property density rules without taint modulation. Do NOT attempt to independently perform taint analysis — that's Phase 0's job.

### Taint-Specific Property Patterns

For HIGH_TAINT functions, additionally generate:

- **Exact-delta VT**: Instead of `gte(_after.x, _before.x, ...)`, use `eq(_after.x, _before.x + expectedDelta, ...)` where the expected delta can be computed from inputs
- **Cross-function correlation**: If function A's taint flows into function B, verify that A followed by B preserves the invariant (e.g., deposit then withdraw returns ≤ deposited)
- **Rounding direction**: For functions with arithmetic taint propagation, verify rounding favors the protocol (never the user)
- **Source diversity coverage**: If a function has 3+ distinct taint source types, ensure at least one property exercises each source type independently

## Output

Write all properties to: `magic/properties-efficient-first-pass.md`

---

## ARCHITECTURAL PREFIX NAMING CONVENTION

All properties MUST use architectural prefixes to indicate which contract layer they target.
The prefix format is: `LAYER-CATEGORY-NUMBER`

**LAYER** is derived from Phase 0 analysis (examples):
- Core/central contracts: CORE-*, POOL-*, VAULT-*, HUB-*
- Secondary/peripheral contracts: SPOKE-*, MARKET-*, STRATEGY-*
- Libraries: MATH-*, LIB-*
- Special categories: CANARY-*, DOOM-*, PERIPH-*

**CATEGORY** indicates the property type:
- **SOL**: Solvency properties (accounting <= balance)
- **MON**: Monotonicity properties (values never decrease)
- **VT**: Variable transition properties (per-function state changes)
- **ST**: State transition properties (which functions cause changes)
- **ER**: Exchange rate properties (share price monotonicity)
- **FEE**: Fee/interest accrual properties
- **VS**: Valid state properties (parameter bounds)
- **HF**: Health factor properties (liquidation eligibility)
- **LIQ**: Liquidation blocking properties (unfair liquidation prevention)
- **AGG**: Aggregation properties (sum of children == parent)

Example prefixes for a Hub/Spoke architecture:
- HUB-SOL-01, HUB-MON-01, SPOKE-HF-01, MATH-01, CANARY-01, DOOM-01

Example prefixes for a Vault/Strategy architecture:
- VAULT-SOL-01, VAULT-MON-01, STRATEGY-VT-01, MATH-01, CANARY-01, DOOM-01

This naming immediately communicates:
1. Which contract layer is being tested (discovered from Phase 0)
2. What category of property it is
3. Sequential numbering within category

---

## ANTI-PATTERNS (DO NOT GENERATE)

Before writing ANY property, check it against these. If a property matches, DO NOT include it:

- **AP-1 TAUTOLOGICAL**: Property restates a `require`/`revert` guard already in the function. A successful call trivially satisfies it. *Exception:* checking the condition ACROSS multiple operations or at a GLOBAL level that no single function enforces.
  - BAD: "Post-borrow position must be healthy" when `borrow()` already has `require(_isHealthy(...))`
- **AP-2 STRUCTURALLY IMPOSSIBLE**: Function never writes to the checked variable (no SSTORE to that slot). *Exception:* cross-variable checks where the function accesses both variables.
  - BAD: "supply() must not change borrowShares" when supply() never touches borrowShares
- **AP-3 TRIVIALLY TRUE MATH**: Math function is 3-5 lines, no branching, no overflow potential, no rounding behavior. Only write math properties for functions with multiple branches, overflow potential, composed operations, or non-obvious rounding.
- **AP-4 DEAD CODE (ghost dependency)**: Property uses `_before`/`_after` ghosts but `updateGhosts` modifier is not on the target function. Before writing ghost-dependent properties, verify `updateGhosts` is applied. If missing, note as REQUIRED FIX in output header.
- **AP-5 INFRASTRUCTURE_MISSING**: Property requires Spoke/Oracle/Position infrastructure not in Setup.sol. Verify test harness has required contracts before writing. If not met, mark as `BLOCKED_BY_INFRASTRUCTURE`.
- **AP-6 NEGATIVE_TEST_AS_POSITIVE**: Writing "X is blocked" as positive assertion. Use try/catch revert pattern instead.
  - WRONG: `t(result == 0, "blocked")` — RIGHT: `try X { t(false, "should revert") } catch { t(true, "blocked") }`
- **AP-7 ARBITRARY BOUNDS**: Hardcoded modulo/addition values without protocol justification. If you use a hardcoded bound, you MUST add a comment explaining why. Acceptable: WAD, RAY, PERCENTAGE_FACTOR, protocol MAX_* constants, type(uintN).max.
  - WRONG: `amount % 1e24` — RIGHT: `if (amount > type(uint256).max - current) return;`

---

## REQUIRED TIERS (ordered by PRIORITY — Financial Impact)

### TIER 0: PROFIT ORACLE PROPERTIES (PROFIT-*)
**PRIORITY: CRITICAL — MANDATORY for all DeFi protocols**

Universal economic extraction detection. These properties catch any attack where an actor extracts more value than they put in, regardless of the specific vulnerability mechanism. Research shows simple profit oracles outperform sophisticated analysis for detecting economic exploits.

**PROPERTY_TYPE:** SIMPLE (checked after every operation)

**Mandatory Pattern:** PATTERN 22 (Net Economic Extraction)
Detection: Any protocol that handles ERC20 tokens or ETH.
Pattern: No actor should have a net positive extraction across all tokens.

**Required properties (adapt to protocol's token set):**

- **PROFIT-01: No actor has net positive ERC20 extraction**
  Track `_initialBalances[actor][token]` set in `setUp()`. After every operation, verify:
  `sum_over_all_tokens(currentBalance[actor][token] - initialBalance[actor][token]) <= DUST_TOLERANCE`
  Tolerance: 1000 wei for 18-decimal tokens, 10 for 6-decimal tokens.
  ```solidity
  function property_PROFIT_01_noNetERC20Extraction() public {
      address[] memory allActors = _getActors();
      address[] memory allTokens = _getAssets();
      for (uint256 a = 0; a < allActors.length; a++) {
          int256 netExtraction = 0;
          for (uint256 t = 0; t < allTokens.length; t++) {
              uint256 current = IERC20(allTokens[t]).balanceOf(allActors[a]);
              uint256 initial = _initialBalances[allActors[a]][allTokens[t]];
              netExtraction += int256(current) - int256(initial);
          }
          t(netExtraction <= int256(DUST_TOLERANCE), "PROFIT-01: actor has net positive ERC20 extraction");
      }
  }
  ```

**RULE: PROFIT_YIELD_AWARENESS (v4.1 — prevents PROFIT-01 false positives in yield protocols)**

For vault/lending protocols where users legitimately earn yield (interest, fees, rewards), PROFIT-01 must not fire on earned interest. The existing DUST_TOLERANCE (1000 wei) is NOT sufficient because yield can legitimately grow by orders of magnitude over simulated time.

Two implementation patterns:

- **Pattern A (simple — recommended for most cases):** Only check actors with `_totalDeposited[actor] == 0` (never-participated actors). If an actor has deposited into the protocol, they can legitimately earn yield, so skip them. This requires a ghost variable `_totalDeposited[actor]` incremented in deposit/supply target functions.
  ```solidity
  // Pattern A: skip actors who have used the vault (they can legitimately earn yield)
  address feeRecipient = address(0); // set if protocol has fee recipient (e.g., vault.feeRecipient())
  for (uint256 a = 0; a < allActors.length; a++) {
      if (_totalDeposited[allActors[a]] > 0) continue; // earned yield is legitimate
      if (feeRecipient != address(0) && allActors[a] == feeRecipient) continue; // fee shares are legitimate
      int256 netExtraction = 0;
      for (uint256 t = 0; t < allTokens.length; t++) {
          uint256 current = IERC20(allTokens[t]).balanceOf(allActors[a]);
          uint256 initial = _initialBalances[allActors[a]][allTokens[t]];
          netExtraction += int256(current) - int256(initial);
      }
      t(netExtraction <= int256(DUST_TOLERANCE), "PROFIT-01: non-depositor has net positive extraction");
  }
  ```

  > **FEE_RECIPIENT_EXTRACTION (v4.1 edge case):** In vault protocols with a fee recipient, the feeRecipient gains vault shares via `_accrueInterest()` without ever calling `deposit()`. This means `_totalDeposited[feeRecipient] == 0` while their `sharesValue > 0`, causing Pattern A to fire on them. Always skip the current `feeRecipient` explicitly, or set `feeRecipient` in the loop guard as shown above. If the feeRecipient can change mid-run (e.g., via `setFeeRecipient()`), read the current value from the contract each time rather than caching it at setup.

- **Pattern B (precise — for protocols where non-depositing actors shouldn't exist):** Track `_totalDeposited[actor]` and `_totalWithdrawn[actor]` ghosts; assert `currentBalance + sharesValue <= initialBalance + _totalDeposited - _totalWithdrawn + DUST`.
  ```solidity
  // Pattern B: account for deposits and withdrawals explicitly
  for (uint256 a = 0; a < allActors.length; a++) {
      int256 netExtraction = int256(currentBalance + sharesValue) - int256(initialBalance);
      int256 netDeposits = int256(_totalDeposited[allActors[a]]) - int256(_totalWithdrawn[allActors[a]]);
      t(netExtraction - netDeposits <= int256(DUST_TOLERANCE), "PROFIT-01: actor extracted beyond deposits + yield");
  }
  ```

**Connection to harness design:** If the harness includes an `asset_mint` (or similar `*_mint`) target function that mints the tracked token directly to an actor — bypassing the protocol's deposit flow — this inflates `currentBalance` without incrementing `_totalDeposited`, causing a PROFIT-01 false positive. See AP-14 (Phase 2) for detection and fix.

- **PROFIT-02: No actor has net positive ETH extraction**
  Same pattern for ETH balances. Track initial ETH balances of all actors.
  ```solidity
  function property_PROFIT_02_noNetETHExtraction() public {
      address[] memory allActors = _getActors();
      for (uint256 a = 0; a < allActors.length; a++) {
          int256 delta = int256(allActors[a].balance) - int256(_initialETHBalances[allActors[a]]);
          t(delta <= int256(DUST_TOLERANCE), "PROFIT-02: actor has net positive ETH extraction");
      }
  }
  ```

- **PROFIT-03: Protocol contract balances not drained beyond expected outflows**
  Track initial token balances of all protocol contracts. Verify no contract loses more than the sum of legitimate outflows.
  ```solidity
  function property_PROFIT_03_noProtocolDrain() public {
      address[] memory allTokens = _getAssets();
      // Check each protocol contract's balance hasn't dropped below threshold
      for (uint256 t = 0; t < allTokens.length; t++) {
          uint256 current = IERC20(allTokens[t]).balanceOf(address(protocolContract));
          uint256 initial = _initialProtocolBalances[address(protocolContract)][allTokens[t]];
          // Allow decrease but not complete drain.
          // Exception: if all depositors have exited (totalSupply == 0), zero balance is legitimate.
          if (initial > 0) {
              bool fullyWithdrawn = (vault.totalSupply() == 0); // replace vault with actual share token
              t(current > 0 || initial <= DUST_TOLERANCE || fullyWithdrawn,
                "PROFIT-03: protocol contract drained to zero");
          }
      }
  }
  ```

  > **FULL_WITHDRAWAL_DRAIN (v4.1 edge case):** When all depositors redeem their shares (`totalSupply == 0`), the underlying protocol contract's token balance legitimately drops to zero. Without the `fullyWithdrawn` guard, the property fires on every full-exit scenario. For lending protocols without a share token, use an equivalent check such as `totalDeposited == 0` or `pool.totalBorrows() == 0 && pool.totalDeposits() == 0`.

**Implementation notes:**
- `_initialBalances` mapping: `mapping(address => mapping(address => uint256))` — set in `setUp()` after all funding
- `_initialETHBalances` mapping: `mapping(address => uint256)` — set in `setUp()`
- `_recordInitialBalances()` helper: Call at end of `setUp()` to snapshot all actor and protocol balances
- DUST_TOLERANCE: `1000` for 18-decimal tokens, `10` for 6-decimal tokens — accounts for rounding without masking real exploits

**RULE: MULTI_MARKET_TOLERANCE (v4.1 — prevents false positives in multi-market/multi-pool protocols)**

For protocols with N markets/pools (e.g., Morpho, Aave, Compound), rounding dust accumulates per-market per-operation. A static tolerance of 1000 wei is insufficient when the protocol performs rounding operations across multiple markets in a single transaction (e.g., `reallocate` across N markets).

- **Minimum tolerance for idle-balance properties:** `N * rounding_per_op` where N is the number of markets/pools and `rounding_per_op` is the maximum rounding error per market interaction (typically 1 wei for integer division).
  - For Morpho-style vaults: `withdrawQueueLength * 1 wei` per reallocate operation.
  - For Aave-style pools: `numberOfActiveReserves * 1 wei` per multi-reserve operation.

- **Static tolerance is insufficient when external state changes occur:** Donations (direct token transfers to vault), failed skims, or interest accrual across markets can cause idle balances that exceed any static threshold. For these cases, use **operation-gated checks** instead of global checks:
  ```
  // WRONG: global idle balance check with static tolerance
  t(token.balanceOf(address(vault)) <= N * 1, "idle balance");

  // RIGHT: operation-gated — only check after ops that should flush idle tokens
  // Use lastTrackedOperation (not currentOperation) — persists after trackOp completes
  if (lastTrackedOperation == DEPOSIT || lastTrackedOperation == WITHDRAW ||
      lastTrackedOperation == REALLOCATE) {
      t(token.balanceOf(address(vault)) <= wqLen * 1, "idle balance after user op");
  }
  ```

- **For PROFIT-03 (protocol drain):** When tracking multi-market protocol contract balances, tolerance should be `sum_over_all_markets(expected_rounding_per_market)`, not a fixed constant. Document the derivation in a comment.

**ATTACK_SCENARIO:** "If any actor can extract more value than they deposited, the protocol has a direct loss-of-funds vulnerability. This catches flash loan attacks, oracle manipulation, rounding exploits, and any other economic extraction regardless of the specific mechanism."

Minimum: 3 properties

### TIER 1: CANARY / COVERAGE PROPERTIES (CANARY-*)
**PRIORITY: CRITICAL — Verify First**

Properties intentionally designed to be VIOLATED when the fuzzer reaches important states. If a canary never breaks, the fuzzer isn't exploring deeply enough. ALL OTHER PROPERTIES ARE VACUOUSLY TRUE if the fuzzer doesn't reach interesting states.

For each critical protocol path (e.g., repayment, liquidation, reward claiming), create a boolean flag that gets set when that path executes, and a canary property that asserts the flag is false.

**If magic/reachability-analysis.md exists**, use it to identify which paths are hardest to reach and prioritize canaries for those paths.

**Attack scenario template:** "If the fuzzer never triggers [path], all properties gating on [state] are vacuously true. Canary detects exploration failure."

Minimum: 2 properties

### TIER 2: SOLVENCY & GLOBAL ACCOUNTING INVARIANTS
**PRIORITY: CRITICAL — Direct Loss of Funds**

System-wide accounting that must always hold regardless of what operations are performed.

**Attack scenario template:** "If `sum(children) != parent`, an attacker can [deposit/withdraw via specific child] to extract [amount] that the parent doesn't track. Victims: all other depositors who can't withdraw."

#### 2A: MULTI-LEVEL ACCOUNTING AGGREGATION INVARIANTS

If the protocol maintains parallel accounting at multiple levels (e.g., global vs per-entity, pool vs market, parent vs child), generate aggregation properties for EACH accounting variable tracked at both levels.

**Mandatory Pattern:** PATTERN 1 (Multi-Level Aggregation)
Detection: Parent/child accounting. Pattern: `sum(child.var) == parent.var`
Generate ONE property per aggregated variable.

#### 2B: BALANCE SOLVENCY

**Mandatory Pattern:** PATTERN 3 (Balance Solvency)
Detection: Internal accounting vs actual token balance. Pattern: `internal_accounting <= IERC20(token).balanceOf(contract)`
Generate ONE property per token/asset tracked.

#### 2C: GENERAL SOLVENCY

Additional solvency properties:
- Total inflows >= total outflows in accounting
- Timestamp/block tracking variables are never in the future

Minimum: 6 properties (4 aggregation + 1 balance + 1 general)

### TIER 3: HEALTH FACTOR PROPERTIES (Apply PATTERN 9)
**PRIORITY: HIGH — User Liquidation Fairness**

**Attack scenario template:** "If healthy positions can be liquidated, an attacker front-runs price updates to liquidate solvent users and seize their collateral. Victims: borrowers with adequate collateral."

Required properties (adapt to protocol's API):
- **HF-01**: Health factor >= threshold prevents liquidation
- **HF-02**: Zero debt implies max/infinite health factor
- **HF-03**: Successful borrow maintains health above threshold
- **HF-04**: Successful collateral withdrawal maintains health above threshold

**Detection:** Look for `healthFactor`, `isHealthy()`, `collateralizationRatio`, `ltv` in the dependency list.

**PREREQUISITES (check before implementing):**
- [ ] Health factor calculation accessible
- [ ] Oracle/price feeds available
- [ ] Position data accessible

If prerequisites NOT met: Mark as `BLOCKED_BY_INFRASTRUCTURE` and skip implementation.

Minimum: 4 properties (or mark all as BLOCKED_BY_INFRASTRUCTURE)

### TIER 4: LIQUIDATION BLOCKING PROPERTIES (Apply PATTERN 10)
**PRIORITY: HIGH — Unfair Liquidation Prevention**

**Attack scenario template:** "If self-liquidation succeeds, an attacker liquidates themselves to extract liquidation bonus from the protocol. If solvent positions are liquidatable, an attacker triggers liquidation on healthy users to seize collateral at a discount."

Required properties (using try/catch negative test pattern):
- **LIQ-01**: Self-liquidation reverts
- **LIQ-02**: Liquidation blocked when position is healthy
- **LIQ-03**: Liquidation of zero-debt position reverts
- **LIQ-04**: Liquidation amount cannot exceed debt
- **LIQ-05**: Seized collateral cannot exceed position's collateral

**Detection:** Look for `liquidate()`, `liquidationCall()` functions in dependency list.
**PREREQUISITES:** Same as TIER 3.

Minimum: 4 properties (or mark all as BLOCKED_BY_INFRASTRUCTURE)

### TIER 5: MONOTONICITY PROPERTIES
**PRIORITY: HIGH — Interest Manipulation Prevention**

**Attack scenario template:** "If `drawnIndex` decreases, debt shrinks retroactively. Borrowers wait for the index decrease then repay less than owed. Victims: lenders who receive less interest."

- Index values (drawnIndex, supplyIndex, etc.) must never decrease
- Use high-water-mark ghost variables to track maximum observed values

Minimum: 2 properties

### TIER 6: CORE MATHEMATICAL PROPERTIES (MATH-*)
**PRIORITY: HIGH — Foundation for All Calculations**

Library-level rounding and conversion guarantees.

**WHY these matter for security:**
- Rounding direction violations: If roundUp < roundDown, attackers exploit mispricing to extract funds
- Round-trip inflation: If converting A->B->A returns MORE than original A, attackers loop to drain funds
- Approximation underestimates: If approximation < first-order term, calculations become incorrect

Required property patterns:
- For each pair of roundUp/roundDown functions: roundUp >= roundDown
- For each conversion pair (e.g., assets<->shares): round-trip must not inflate

**Mandatory Pattern:** PATTERN 6 (Share/Asset Round-Trip No Inflation)
Detection: Share-based accounting with conversion functions. Pattern: `shares->assets->shares` must not increase shares.

**Mandatory Pattern:** PATTERN 7 (Share/Asset Round-Trip No Deflation)
Detection: Same as Pattern 6. Pattern: `assets->shares->assets` must not decrease assets.

**Mandatory Pattern:** PATTERN 26 (Math Library Round-Trip No Inflation)
Detection: Any pair of inverse functions (mulUp/divDown, toShares/toAssets, encode/decode).
Pattern: `f(g(x)) <= x` for value-preserving direction, `g(f(x)) >= x` for protocol-favoring.

Generate one property per inverse function pair found in the dependency list.

Only write properties for non-trivial functions (see AP-3).

Minimum: 5 properties

### TIER 7A: VARIABLE TRANSITION PROPERTIES — POSITIVE
**PRIORITY: MEDIUM — State Change Correctness**

For EACH major state-changing function, verify that specific state variables change in the expected direction.

Use a before/after ghost variable pattern: capture state before the function call, capture state after, compare. Filter by function selector.

**IMPORTANT**: Only check variables that the function ACTUALLY WRITES TO (see AP-2).

**Attack scenario template:** "If `deposit` doesn't increase `totalAssets`, a reentrant call could drain the difference. If `withdraw` doesn't decrease `totalShares`, share dilution occurs."

**Exact vs directional checks:** For single-operation functions (not batch), prefer exact delta checks (`eq(_after.x, _before.x + 1)`) over directional checks (`gte`). For batch operations, use directional checks. Exact deltas catch off-by-one and double-increment bugs that directional checks miss.

**Privileged function state effects:** For functions gated by access control modifiers (onlyOwner, onlyMaster, initializer), write properties that verify the STATE EFFECT — e.g., after `initialize()`, master actually changed; after `setConfig(x)`, config == x. Do NOT write properties that restate the modifier's guarantee (AP-1). The modifier ensures authorization; the property ensures the function did its job.

Example patterns:
- Deposit/supply: total assets increases, total shares increases, user's position increases
- Withdraw: total assets decreases, total shares decreases
- Borrow: total debt increases, user's debt increases
- Repay: total debt decreases, user's debt decreases
- Liquidation: borrower's debt decreases, borrower's collateral decreases
- Single add/remove: count changes by exactly +1/-1
- Privileged config: after setX(val), storage == val (not just "caller was admin")

Minimum: 12 properties

### TIER 7B: VARIABLE TRANSITION PROPERTIES — NEGATIVE
**PRIORITY: MEDIUM — Revert Correctness**

What should NOT change and what should REVERT. Use try/catch for revert checks.

- Operations that should revert under certain conditions
- State isolation — variables that should not change (only when the function DOES access related storage)

Minimum: 3 properties

### TIER 7B-PRIV: PRIVILEGE ESCALATION NEGATIVE TESTS
**PRIORITY: HIGH — Authorization Bypass Prevention**

For EVERY function with an access control modifier (onlyOwner, onlyAdmin, onlyGateway,
require(msg.sender == X)), generate negative tests verifying unauthorized callers are rejected.

**Attack scenario template:** "If setAdmin(address(0)) succeeds, the admin role is
destroyed and protocol governance is permanently bricked. If setImplementation(attacker)
succeeds, the attacker can execute arbitrary code in the protocol's storage context."

**NEVER_DISCARD: These properties MUST NOT be discarded by Phase 2, regardless of
AP-1 matching. They appear tautological but test that the AUTHORIZATION GATE itself
works — distinct from testing post-authorization state effects.**

Required patterns:
- **PRIV-NEG-01: Admin setters reject zero address**
  For each setter that takes an address and stores it (setAdmin, setOracle, setImplementation):
  ```solidity
  try protocol.setAdmin(address(0)) {
      t(false, "PRIV-NEG-01: setAdmin(address(0)) must revert");
  } catch { /* expected */ }
  ```

- **PRIV-NEG-02: Admin setters reject self-assignment**
  ```solidity
  try protocol.setAdmin(address(protocol)) {
      t(false, "PRIV-NEG-02: setAdmin(self) must revert");
  } catch { /* expected */ }
  ```

- **PRIV-NEG-03: Privileged state effect verification**
  After a successful admin setter call (via asAdmin), verify the state actually changed:
  ```solidity
  // Use asAdmin modifier to call as authorized
  protocol.setFeeRate(newRate);
  eq(protocol.feeRate(), newRate, "PRIV-NEG-03: setFeeRate did not update storage");
  ```

Minimum: 2 properties per admin setter function

### TIER 7B-PRIV (Extended): SYSTEMATIC AUTH SWEEP (PRIV-AUTH-*) (NEW in v4.2)
**PRIORITY: HIGH — Full Authorization Coverage**

**Check `Access Control Inventory` from PROTOCOL CHARACTERISTICS section of `magic/contracts-dependency-list.md`** (generated by Phase 0 Step 4h). For every function that has an access control modifier AND is NOT already covered by PRIV-NEG-01/02/03 (admin setters), generate one PRIV-AUTH property.

**Attack scenario template:** "If [functionName] is callable by unauthorized addresses, an attacker can [describe impact: drain funds, change config, brick protocol]. Access control bugs in non-setter functions are the #1 most common exploit vector on Immunefi."

**NEVER_DISCARD: PRIV-AUTH properties MUST NOT be discarded by Phase 2, regardless of AP-1 matching. Like PRIV-NEG, they test that the authorization gate itself works.**

**Generation rule:** Phase 1A reads the Access Control Inventory from Phase 0 Step 4h. For each function marked `In PRIV-NEG? = NO` with a non-trivial access modifier (not just `whenNotPaused`), auto-generate one PRIV-AUTH property.

**Required pattern:**

```
### PRIV-AUTH-XX: [functionName] rejects unauthorized caller
- Pattern: Auth Sweep
- Category: NEGATIVE
- Tier: 7B-PRIV (extended)

Pseudocode:
  address actor = _getActor();
  if (actor == protocol.owner()) return; // actor already has role, skip
  // Add checks for ALL relevant roles the function requires:
  // if (actor == protocol.admin()) return;
  // if (protocol.hasRole(ROLE, actor)) return;
  vm.prank(actor);
  try protocol.functionName(args) {
      t(false, "PRIV-AUTH-XX: unauthorized [functionName] succeeded");
  } catch {
      // expected — access control works
  }

ATTACK_SCENARIO: "If [functionName] is callable by unauthorized addresses, attacker can
[describe impact: drain funds, change config, brick protocol]."
ANTI-PATTERN_CHECK: Not tautological — tests that the access control modifier EXISTS and
WORKS on this specific function, not just that msg.sender is checked somewhere.
```

**Minimum:** 1 property per access-controlled function not already in PRIV-NEG. NEVER_DISCARD category.

### TIER 8: EXCHANGE RATE / SHARE PRICE INVARIANTS
**PRIORITY: MEDIUM — Share Price Manipulation Prevention**

**Attack scenario template:** "If share price decreases after a deposit, the first depositor inflates share price, then later depositors' shares round to zero. Attacker extracts the deposited assets."

Use cross-multiplication to avoid division precision issues:
`after.numerator * before.denominator >= before.numerator * after.denominator`
(with small tolerance for rounding, e.g., 1 wei)

**Mandatory Pattern:** PATTERN 25 (Share Inflation / First-Depositor Attack)
Detection: Any vault/pool with share-based accounting where `totalSupply` can be 0.
Pattern: After a donation (direct token transfer to vault), the next depositor's shares
must not round to zero.

```solidity
function property_ER_shareInflation(uint256 donationAmt, uint256 depositAmt) public {
    if (vault.totalSupply() > 0) return; // Only test first-depositor scenario
    // Donate tokens directly (not through deposit)
    IERC20(asset).transfer(address(vault), donationAmt);
    // Now deposit as a different actor
    uint256 shares = vault.deposit(depositAmt, actor);
    t(shares > 0, "ER-INFLATE: first depositor got zero shares after donation");
}
```

Minimum: 1 property per exchange rate in the protocol

### TIER 9: TIME-BASED ACCRUAL & FEE PROPERTIES
**PRIORITY: MEDIUM — Fee Extraction Prevention**

**Attack scenario template:** "If fees accrue incorrectly, an attacker can deposit, trigger accrual with zero time elapsed, and extract unearned fees. Victims: protocol treasury or other users."

**Check `PROTOCOL CHARACTERISTICS` section of `magic/contracts-dependency-list.md`** for `TIME_BASED` and `TIME_PATTERN` flags. If `TIME_BASED=true`, this tier is CRITICAL and requires time-warping properties.

#### 9A: BASIC FEE/ACCRUAL PROPERTIES

- Fee recipient balances should increase whenever accrual happens with non-zero fee and non-zero amount
- Time tracking variables should never decrease
- Zero time elapsed = no interest accrual

#### 9B: TIME-WARPING PROPERTIES (if TIME_BASED=true)

For each time-dependent function identified in Phase 0's protocol characteristics, generate properties that USE `hevm.warp()` to advance time.

**Mandatory Pattern:** PATTERN 13 (Time-Dependent Monotonicity)
Detection: Storage slot modified by `block.timestamp - lastUpdate` calculation.
Pattern: Warp time forward → trigger accrual → value should increase (or stay same).

```solidity
// Template: Time-dependent monotonicity
uint valueBefore = getAccumulatedValue();
hevm.warp(block.timestamp + TIME_DELTA);
triggerAccrual();
uint valueAfter = getAccumulatedValue();
t(valueAfter >= valueBefore, "FEE: value must not decrease with time");
```

**Mandatory Pattern:** PATTERN 14 (Accrual Proportionality)
Detection: Interest/reward rate multiplied by time delta.
Pattern: Accrual over 2x time ≈ 2x accrual over 1x time (within rounding tolerance).

```solidity
// Template: Accrual proportionality
uint snapshot = vm.snapshot();
hevm.warp(block.timestamp + DELTA);
triggerAccrual();
uint accrual1x = getAccumulated() - baseLine;
vm.revertTo(snapshot);
hevm.warp(block.timestamp + 2 * DELTA);
triggerAccrual();
uint accrual2x = getAccumulated() - baseLine;
// For linear accrual: 2x should be ~2x of 1x
// For compound: 2x should be >= 2x of 1x
t(accrual2x >= 2 * accrual1x - ROUNDING_TOLERANCE, "FEE: accrual not proportional to time");
```

**Mandatory Pattern:** PATTERN 15 (Zero-Time No-Op)
Detection: Any accrual function.
Pattern: Calling accrual with zero time elapsed should not change state.

```solidity
// Template: Zero-time no-op
uint valueBefore = getAccumulatedValue();
triggerAccrual();  // Same block, no time elapsed
uint valueAfter = getAccumulatedValue();
eq(valueAfter, valueBefore, "FEE: zero-time accrual must be no-op");
```

**TIME_PATTERN-specific properties:**
- If `accrual`: Generate PATTERN 13 + 14 + 15
- If `vesting`: Generate unlock schedule property (0% at start, 100% at end, proportional between)
- If `epoch`: Generate epoch boundary property (state changes only at epoch transitions)
- If `lockup`: Generate unlock timing property (withdrawal blocked before, allowed after)

Minimum: 2 properties (4+ if TIME_BASED=true)

#### 9C: FEE VOLUME CONSERVATION (NEW in v4.2)

**Mandatory Pattern:** PATTERN 29 (Fee Volume Conservation)
Detection: Protocol has fee collection (`feeRate`, `protocolFee`, `performanceFee`, `managementFee`, or any function that deducts a percentage from user operations).
Pattern: Total fees collected must never exceed total volume processed.

**PROPERTY_TYPE:** SIMPLE (checked after every operation using ghost counters)

```
### FEE-VOL-01: Total fees collected never exceed total volume
- Pattern: PATTERN 29
- Category: SIMPLE
- Tier: 9A

Ghost variables:
- _totalVolumeProcessed: cumulative sum of all deposit/withdraw/swap/borrow amounts
- _totalFeesCollected: cumulative sum of all fees taken by protocol

Pseudocode:
  lte(_totalFeesCollected, _totalVolumeProcessed,
      "FEE-VOL-01: fees exceed total volume — fee calculation bug");

ATTACK_SCENARIO: "Fee calculation bug causes protocol to charge 110% fee on a 100-unit
swap. Cumulative fees exceed total volume, indicating the fee math is broken.
Victims: all users who overpay fees."
ANTI-PATTERN_CHECK: Not tautological — no single require checks cumulative fee/volume ratio.
Not structurally impossible — fee accounting storage IS written by swap/deposit/withdraw.
Distinct from SOL-* (Tier 2) which checks solvency, not fee correctness.
Distinct from PROFIT-* (Tier 0) which checks actor-level extraction, not protocol-level fees.
```

**Implementation note:** Ghost variables `_totalVolumeProcessed` and `_totalFeesCollected` must be tracked in target function handlers (Phase 3A). `_totalVolumeProcessed` is incremented by the amount parameter in deposit/withdraw/swap/borrow handlers. `_totalFeesCollected` is tracked by reading the protocol's fee recipient balance or cumulative fee counter in `__after()`.

**Skip condition:** If the protocol has NO fee mechanism (no feeRate, no protocolFee, no fee recipient), skip this pattern entirely.

Minimum: 1 property (if protocol has fees; 0 if no fee mechanism)

### TIER 10: DOOMSDAY / LIVENESS PROPERTIES (DOOM-*)
**PRIORITY: MEDIUM — Fund Locking Prevention**

**Attack scenario template:** "If users who deposited cannot withdraw despite sufficient liquidity, funds are permanently locked. The protocol becomes insolvent in practice even if solvent on paper."

**If magic/reachability-analysis.md exists**, cross-reference liveness paths with reachability findings to ensure the fuzzer CAN actually test these paths.

Verify via try/catch:
- Users who deposited CAN withdraw when sufficient liquidity exists
- Users who borrowed CAN always repay their debt
- Positions eligible for liquidation CAN always be liquidated

**STATE MUTATION WARNING:** Use vm.snapshot()/vm.revertTo() to rollback after try/catch tests.

Minimum: 4 properties

### TIER 10B: MULTI-ACTOR COORDINATION PROPERTIES
**PRIORITY: MEDIUM-HIGH — Reentrancy & Race Condition Prevention**

**Check `PROTOCOL CHARACTERISTICS` section of `magic/contracts-dependency-list.md`** for `MULTI_ACTOR` flag. If `MULTI_ACTOR=false`, skip this tier entirely.

**Attack scenario template:** "If two users can operate on the same resource concurrently without proper isolation, an attacker reenters during an external call to double-withdraw, or front-runs a liquidation to steal the bonus. Victims: other depositors, the protocol itself."

#### 10B-A: REENTRANCY SAFETY (if external calls precede state updates)

For each function where an external call (`call`, `transfer`, `safeTransfer`, callback) precedes a state update (SSTORE), generate a property verifying the state change is atomic.

**Mandatory Pattern:** PATTERN 16 (Reentrancy Atomicity)
Detection: External call followed by SSTORE in the same function.
Pattern: Total accounting before operation == total accounting after operation ± expected delta (no extra delta from reentrant call).

```solidity
// Template: Reentrancy atomicity
uint totalBefore = getTotalAccounting();
uint userBalanceBefore = getUserBalance(actor);
// Execute operation that has external call
performOperation(amount);
uint totalAfter = getTotalAccounting();
uint userBalanceAfter = getUserBalance(actor);
// Total change should exactly equal user's change
int totalDelta = int(totalAfter) - int(totalBefore);
int userDelta = int(userBalanceAfter) - int(userBalanceBefore);
eq(totalDelta, userDelta, "MULTI-ACTOR: accounting mismatch suggests reentrancy");
```

**PROPERTY_TYPE:** SIMPLE (checked after every operation)

#### 10B-B: NO DOUBLE-SPEND ON SHARED RESOURCES

For each storage slot written by multiple external-facing functions from different callers, verify that the total change across all callers equals the sum of individual changes.

**Mandatory Pattern:** PATTERN 17 (Shared Resource Integrity)
Detection: Storage slot written by 2+ functions callable by different msg.senders.
Pattern: After any operation, global invariant still holds (sum of parts == whole).

```solidity
// Template: Shared resource integrity (builds on Tier 2 solvency)
// This is NOT a duplicate of Tier 2 — it specifically checks that
// multi-actor interaction preserves solvency, not just single-actor
uint sumUserBalances = 0;
for (uint i = 0; i < actors.length; i++) {
    sumUserBalances += getUserBalance(actors[i]);
}
t(sumUserBalances <= getTotalSupply(), "MULTI-ACTOR: user balances exceed total supply");
```

**PROPERTY_TYPE:** SIMPLE

**ANTI-PATTERN_CHECK:** This is NOT a duplicate of Tier 2 solvency. Tier 2 checks `internal_accounting <= token.balanceOf()`. This checks that the SUM of per-user accounting equals the global accounting — catching cases where concurrent operations corrupt per-user tracking even though the global number looks correct.

#### 10B-C: LIQUIDATION RACE CONDITION SAFETY (if liquidation exists)

If the protocol has liquidation, verify that concurrent liquidation attempts don't extract more value than the position holds.

```solidity
// Template: No double-liquidation value extraction
// Use vm.snapshot/revertTo to test both paths
uint snapshotId = vm.snapshot();
// Path 1: liquidator1 liquidates
try protocol.liquidate(borrower, amount) {
    uint extracted1 = getExtractedValue(liquidator1);
    vm.revertTo(snapshotId);
    // Path 2: liquidator2 liquidates same position
    try protocol.liquidate(borrower, amount) {
        uint extracted2 = getExtractedValue(liquidator2);
        // Total extracted across both paths should not exceed position value
        t(extracted1 <= positionValue && extracted2 <= positionValue,
          "MULTI-ACTOR: double liquidation extracts excess value");
    } catch {}
} catch {}
```

**PROPERTY_TYPE:** DOOMSDAY (uses vm.snapshot/revertTo)
**PREREQUISITES:** Same as TIER 3/4 (health factor, liquidation infrastructure)

Minimum: 2 properties (if MULTI_ACTOR=true; 0 if false)

---

## PROPERTY_TYPE (one per property)

- **PROFIT**: Economic extraction oracle — checks net value flow across all actors after every operation. (Tier 0)
- **SIMPLE**: Global invariant not tied to a specific function call. Checked after every operation. (Tiers 2, 5, 6, 8, 9C, 12, 16, 17)
- **INLINE**: Per-function assertion using before/after ghost state. Filters on function selector. (Tiers 7A, 7B, 9, 11)
- **DOOMSDAY**: A liveness guarantee verified via try/catch, or an unacceptable state that must never occur. (Tier 10)
- **NEGATIVE**: A spec-based negative test verifying an operation reverts. Uses try/catch pattern. (Tiers 3, 4, 7B, 17)
- **CANARY**: Coverage verification property designed to break when fuzzer reaches target state. (Tier 1)
- **FLAG**: Static detection flag — not a runtime property, but a code analysis finding. (Tier 16 WTOK-C only)

---

## PROPERTY TEMPLATE

For each property, use this template:
```
ARCHITECTURE_PREFIX (e.g., HUB-SOL-01, SPOKE-HF-01, MATH-01)
PROPERTY_TYPE
Title
ATTACK_SCENARIO: [REQUIRED] What attack does this prevent? Who loses money if violated?
DESCRIPTION (technical explanation)
ANTI-PATTERN_CHECK: Briefly explain why this property is NOT tautological, NOT structurally impossible, and NOT trivially true. Reference the specific code you checked.
SUGGESTED_PSEUDOCODE (implementable Solidity using t(), eq(), gte(), lte() assertion helpers)
```

Also classify each property:
- Safety vs liveness vs mixed
- Local vs global vs parametric

---

## PATTERN APPLICATION PROCESS

1. Read `magic/contracts-dependency-list.md` thoroughly
2. For each PATTERN referenced inline in the tiers above, scan the dependency list to identify matching storage slots/functions
3. Generate a concrete property for each match found
4. Use the protocol's actual API in the pseudocode

**Remaining mandatory patterns to apply across all tiers:**

| Pattern | Detection | Generate |
|---------|-----------|----------|
| PATTERN 22: Net Economic Extraction | Any DeFi protocol with token transfers | THREE properties (ERC20, ETH, protocol drain) — Tier 0 |
| PATTERN 2: Index/Rate Minimum Bounds | Index/rate vars initialized to non-zero constants (RAY, WAD) | ONE property per index/rate variable |
| PATTERN 4: Configuration Bounds | MAX_*, MAXIMUM_* constants and config fields | ONE property per (config, max) pair |
| PATTERN 5: Membership/Registry Validity | Beneficiary/receiver addresses that must be registered | ONE property per membership validation |
| PATTERN 8: Critical Value Range Bounds | Storage vars with custom uint types (uint200, uint128, uint96) | ONE property per critical custom-sized variable |
| PATTERN 13: Time-Dependent Monotonicity | `block.timestamp - lastUpdate` in accrual (TIME_BASED=true) | ONE property per time-dependent accumulator |
| PATTERN 14: Accrual Proportionality | Interest/reward rate × time delta (TIME_BASED=true) | ONE property per accrual mechanism |
| PATTERN 15: Zero-Time No-Op | Any accrual function (TIME_BASED=true) | ONE property per accrual function |
| PATTERN 16: Reentrancy Atomicity | External call followed by SSTORE (MULTI_ACTOR=true) | ONE property per external-call-before-SSTORE pattern |
| PATTERN 17: Shared Resource Integrity | Storage slot written by 2+ functions from different callers (MULTI_ACTOR=true) | ONE property per shared storage slot |
| PATTERN 27-A: Precision Drift Bounded | Deposit + withdraw with integer division (PRECISION_ACCUMULATION=APPLICABLE) | ONE property tracking per-actor drift |
| PATTERN 27-B: Solvency Gap Growth | Internal accounting vs real balance (PRECISION_ACCUMULATION=APPLICABLE) | ONE property tracking gap growth rate |
| PATTERN 27-C: Zero-Share Prevention | Share-based accounting (PRECISION_ACCUMULATION=APPLICABLE) | ONE property per deposit function |
| PATTERN 28-WTOK-A: Fee-on-Transfer Solvency | TOKEN_ASSUMPTION=OPEN\|UNSPECIFIED, FEE_ON_TRANSFER != ALREADY_HANDLED | ONE mock deployment + re-use SOL properties |
| PATTERN 28-WTOK-B: Rebasing Accounting | TOKEN_ASSUMPTION=OPEN\|UNSPECIFIED, REBASING != ALREADY_HANDLED | ONE mock deployment + rebase handler |
| PATTERN 28-WTOK-D: Low Decimals Precision | TOKEN_ASSUMPTION=OPEN\|UNSPECIFIED, LOW_DECIMALS != ALREADY_HANDLED | ONE mock deployment + re-use MATH properties |
| PATTERN 23-CROSS-E: Re-initialization Protection | HAS_INITIALIZER=true (Phase 0 Step 4g) | TWO properties per initializer function (already-init, version check) |
| PATTERN 23-CROSS-F: Pause-Freeze Invariant | HAS_PAUSE=true (Phase 0 Step 4g) | ONE property (state frozen while paused) + DOOM pause guards |
| PATTERN 23-CROSS-G: Storage Slot Stability | USES_UPGRADEABLE_PROXY=true (Phase 0 Step 4g) | ONE property per proxy (impl + admin slot checks) |
| PATTERN 29: Fee Volume Conservation | Protocol has fee mechanism (feeRate, protocolFee, etc.) | ONE property (cumulative fees <= cumulative volume) |
| PRIV-AUTH-*: Auth Sweep | Access Control Inventory (Phase 0 Step 4h) | ONE property per non-PRIV-NEG access-controlled function |

---

## PROTOCOL-TYPE MANDATORY TEMPLATES (NEW in v3.5)

**Read `PROTOCOL_TYPE` from the PROTOCOL CHARACTERISTICS section of `magic/contracts-dependency-list.md`.** If present, inject the following protocol-specific property templates into existing tiers (these are NOT new tiers — they augment the tiers above with domain-specific properties).

**IMPORTANT:** Before adding a template property, check for duplicates against properties already generated from the tiers above. If a tier already covers the same invariant, skip the template. Add a `DUPLICATE_CHECK: Verified no overlap with [existing property ID]` note to each template property.

### AMM Templates (if PROTOCOL_TYPE=AMM)

- **PATTERN 23-AMM-A** → Tier 2: Constant Product Invariant
  `reserve0 * reserve1 >= k` after every swap (allowing for fee accumulation increasing k).
  ```solidity
  // After any swap: k must not decrease
  uint256 currentK = reserve0 * reserve1;
  gte(currentK, _lastK, "AMM-A: constant product violated");
  ```

- **PATTERN 23-AMM-B** → Tier 6: Slippage Bounds
  Output amount must be within expected range given input and reserves.
  ```solidity
  // Swap output should not exceed theoretical maximum (no-fee output)
  uint256 maxOut = (amountIn * reserveOut) / (reserveIn + amountIn);
  lte(actualOut, maxOut, "AMM-B: output exceeds theoretical max");
  ```

- **PATTERN 23-AMM-C** → Tier 6: Sandwich Resistance
  Two sequential swaps in opposite directions should not extract value.
  ```solidity
  // Swap A->B then B->A should result in net loss (fees consumed)
  t(finalAmountA <= initialAmountA, "AMM-C: round-trip swap extracted value");
  ```

- **PATTERN 23-AMM-D** → Tier 8: LP Token Value
  LP token value should be monotonically non-decreasing (fees accumulate).
  ```solidity
  // LP token should represent increasing share of reserves
  uint256 valuePerLP = (reserve0 + reserve1) * 1e18 / totalSupply;
  gte(valuePerLP, _lastValuePerLP, "AMM-D: LP token value decreased");
  ```

### LENDING Templates (if PROTOCOL_TYPE=LENDING)

- **PATTERN 23-LEND-A** → Tier 2: Collateralization Ratio
  Total collateral value must exceed total debt value (system-wide solvency).
  ```solidity
  uint256 totalCollateralValue = getTotalCollateralValue();
  uint256 totalDebtValue = getTotalDebtValue();
  gte(totalCollateralValue, totalDebtValue, "LEND-A: system undercollateralized");
  ```

- **PATTERN 23-LEND-B** → Tier 3: Bad Debt Accumulation
  Bad debt (debt without sufficient collateral) must not grow unboundedly.
  ```solidity
  uint256 badDebt = getTotalDebt() - min(getTotalDebt(), getTotalCollateral());
  lte(badDebt, _maxAcceptableBadDebt, "LEND-B: bad debt exceeds threshold");
  ```

- **PATTERN 23-LEND-C** → Tier 5: Interest Index Monotonicity
  Borrow/supply indexes must never decrease.
  ```solidity
  uint256 currentBorrowIndex = pool.getBorrowIndex();
  gte(currentBorrowIndex, _lastBorrowIndex, "LEND-C: borrow index decreased");
  ```

### VAULT Templates (if PROTOCOL_TYPE=VAULT)

- **PATTERN 23-VAULT-A** → Tier 6: Share Price Monotonicity
  Share price must not decrease (except from loss events).
  ```solidity
  uint256 pricePerShare = vault.convertToAssets(1e18);
  gte(pricePerShare, _lastPricePerShare, "VAULT-A: share price decreased");
  ```

- **PATTERN 23-VAULT-B** → Tier 7A: Deposit/Withdraw Symmetry
  Depositing X assets and immediately withdrawing should return <= X (rounding in protocol's favor).
  ```solidity
  uint256 shares = vault.convertToShares(assets);
  uint256 assetsBack = vault.convertToAssets(shares);
  lte(assetsBack, assets, "VAULT-B: deposit-withdraw round-trip inflates assets");
  ```

- **PATTERN 23-VAULT-C** → Tier 6: Rounding Direction
  `convertToShares` rounds down, `convertToAssets` rounds down — protocol never over-issues shares or over-returns assets.

### ERC20 Templates (if PROTOCOL_TYPE=ERC20)

- **PATTERN 23-ERC20-A** → Tier 2: Supply Conservation
  `totalSupply == sum(balanceOf(all holders))` — no tokens created from thin air.

- **PATTERN 23-ERC20-B** → Tier 7A: Transfer Conservation
  `sender_loss == receiver_gain + fee` for every transfer.

- **PATTERN 23-ERC20-C** → Tier 2: Strong Supply Conservation
  `totalSupply() == sum(balanceOf(holder))` for all tracked holders. Stronger than ERC20-A (mint/burn accounting) because it verifies actual balance summation.
  ```solidity
  // Strong supply conservation — iterates all tracked actors
  uint256 sumBalances = 0;
  address[] memory allActors = _getActors();
  for (uint256 i = 0; i < allActors.length; i++) {
      sumBalances += token.balanceOf(allActors[i]);
  }
  // Include protocol contract balance if it holds tokens
  sumBalances += token.balanceOf(address(token));
  eq(token.totalSupply(), sumBalances, "ERC20-C: totalSupply != sum of balances");
  ```

- **PATTERN 23-ERC20-D** → Tier 7A: Event-State Mismatch
  After Transfer-emitting calls, verify balanceOf deltas match. `senderDelta >= receiverDelta` (accounts for fee-on-transfer).
  ```solidity
  // After any Transfer-emitting call, verify balance deltas
  if (_before.sig == token.transfer.selector || _before.sig == token.transferFrom.selector) {
      int256 senderDelta = int256(_after.senderBalance) - int256(_before.senderBalance);
      int256 receiverDelta = int256(_after.receiverBalance) - int256(_before.receiverBalance);
      // Sender loss >= receiver gain (fee-on-transfer safe)
      t(-senderDelta >= receiverDelta, "ERC20-D: sender loss < receiver gain");
  }
  ```

### STAKING Templates (if PROTOCOL_TYPE=STAKING)

- **PATTERN 23-STAKE-A** → Tier 9: Reward Rate Consistency
  `earned(user)` should increase proportionally to time staked and stake amount.

- **PATTERN 23-STAKE-B** → Tier 7A: Stake/Unstake Symmetry
  Staking X and unstaking the resulting shares should return <= X.

### CROSS-PROTOCOL Templates (apply regardless of PROTOCOL_TYPE)

These templates detect vulnerability classes that can appear in ANY protocol type.

- **PATTERN 23-CROSS-A** → Tier 10: Locked Funds Detection
  If a user has a non-zero position, protocol is not paused, and sufficient liquidity exists, then `withdraw` (or the protocol's equivalent exit function) must not revert. Uses `vm.snapshot`/`vm.revertTo` to test without side effects.
  ```solidity
  // Locked funds detection — must be able to exit
  uint256 snapshotId = vm.snapshot();
  address actor = _getActor();
  uint256 position = protocol.balanceOf(actor);
  if (position > 0 && !protocol.paused()) {
      try protocol.withdraw(position) {
          // Success — funds not locked
      } catch {
          t(false, "CROSS-A: user with position cannot withdraw — funds locked");
      }
  }
  vm.revertTo(snapshotId);
  ```

- **PATTERN 23-CROSS-B** → Tier 7B: Delegatecall to Untrusted Address
  Static check: if `delegatecall` target comes from a function parameter or non-admin-writable storage, generate a NEGATIVE property verifying the call reverts for untrusted addresses.
  Detection: Scan the dependency list for `delegatecall` usage. If the target address is derived from a parameter or storage slot writable by non-admin roles, flag it.
  ```solidity
  // Delegatecall to untrusted address — should revert
  try protocol.executeDelegatecall(address(0xdead)) {
      t(false, "CROSS-B: delegatecall to untrusted address succeeded");
  } catch {
      t(true, "CROSS-B: delegatecall to untrusted address correctly reverted");
  }
  ```

- **PATTERN 23-CROSS-C** → Tier 7B: Unprotected Selfdestruct
  Static check: if `selfdestruct` exists without `onlyOwner`/`onlyAdmin` guard, generate a NEGATIVE property.
  Detection: Scan the dependency list for `selfdestruct` or `SELFDESTRUCT` opcode usage. Verify access control is present.
  ```solidity
  // Unprotected selfdestruct — unauthorized call should revert
  try protocol.destroy() {
      t(false, "CROSS-C: selfdestruct callable by non-admin");
  } catch {
      t(true, "CROSS-C: selfdestruct correctly protected");
  }
  ```

- **PATTERN 23-CROSS-D** → Tier 7A: Deposit-Withdraw Sandwich Resistance
  For ANY protocol with deposit+withdraw (not just AMMs): depositing X then immediately
  withdrawing must return <= X.
  ```solidity
  function property_CROSS_D_depositWithdrawNoProfit(uint256 amount) public {
      uint256 snap = vm.snapshot();
      uint256 balBefore = IERC20(asset).balanceOf(actor);
      uint256 shares = protocol.deposit(amount, actor);
      if (shares == 0) { vm.revertTo(snap); return; }
      protocol.withdraw(shares, actor, actor);
      uint256 balAfter = IERC20(asset).balanceOf(actor);
      t(balAfter <= balBefore + DUST, "CROSS-D: deposit-withdraw extracted value");
      vm.revertTo(snap);
  }
  ```

### State Machine Templates (apply when detected by Phase 0 Step 4g) (NEW in v4.2)

These templates detect state machine bugs (re-initialization, pause-freeze violations, storage slot corruption on upgrade) that remain top-5 on Immunefi with zero coverage in v4.1.

- **PATTERN 23-CROSS-E** → Tier 7B: Re-initialization Protection
  Condition: `HAS_INITIALIZER=true` (from Phase 0 Step 4g)
  Two properties:
  1. `initialize()` reverts when already initialized (try/catch NEGATIVE)
  2. `reinitialize()` reverts with same or lower version number (if applicable)
  NEVER_DISCARD category (critical safety).

  ```solidity
  // Property 1: initialize() reverts when already initialized
  function property_CROSS_E_01_initializeRevertsWhenInitialized() public {
      if (address(protocol) == address(0)) return;
      // Protocol should already be initialized from setUp()
      try protocol.initialize(initParams) {
          t(false, "CROSS-E-01: initialize() succeeded on already-initialized contract");
      } catch {
          // expected — re-initialization blocked
      }
  }

  // Property 2: reinitialize() reverts with same or lower version
  function property_CROSS_E_02_reinitializeVersionCheck(uint8 version) public {
      if (address(protocol) == address(0)) return;
      uint8 currentVersion = protocol.getInitializedVersion(); // or read _initialized slot
      if (version > currentVersion) return; // valid upgrade, skip
      try protocol.reinitializer(version) {
          t(false, "CROSS-E-02: reinitialize succeeded with same/lower version");
      } catch {
          // expected — version check works
      }
  }
  ```

  **ATTACK_SCENARIO:** "Attacker calls initialize() on an already-deployed contract to reset admin to their address. All protocol funds are now under attacker control. This is the #1 proxy vulnerability pattern."

- **PATTERN 23-CROSS-F** → Tier 12: Pause-Freeze Invariant
  Condition: `HAS_PAUSE=true` (from Phase 0 Step 4g)
  Property: When `paused() == true`, critical state (balances, accounting) does not change.
  Implementation: Snapshot critical state hash before/after any operation while paused.

  ```solidity
  function property_CROSS_F_pauseFreezeInvariant() public {
      if (address(protocol) == address(0)) return;
      if (!protocol.paused()) return; // only check while paused

      // Critical state should not change while paused
      // Use _before/_after ghosts — if paused, no state-changing op should alter them
      if (_before.totalAssets != 0 || _after.totalAssets != 0) {
          eq(_after.totalAssets, _before.totalAssets,
             "CROSS-F: totalAssets changed while paused");
      }
      if (_before.totalSupply != 0 || _after.totalSupply != 0) {
          eq(_after.totalSupply, _before.totalSupply,
             "CROSS-F: totalSupply changed while paused");
      }
  }
  ```

  **ATTACK_SCENARIO:** "Admin pauses protocol during emergency, but attacker finds a function missing the whenNotPaused modifier. Attacker drains funds while protocol is supposed to be frozen."

  **Implementation note:** The `_before.totalAssets` / `_after.totalSupply` references in the pseudocode are illustrative. Phase 3A MUST substitute the actual ghost variable names from the protocol's BeforeAfter.sol `Vars` struct. If those ghost variables don't exist, Phase 3A Step 0E must add them before implementing this property.

  **RULE: PAUSE_GUARD_ON_DOOM** — When `HAS_PAUSE=true`, ALL DOOM/liveness properties MUST include `if (protocol.paused()) return;` guard. Without it, admin pausing trivially falsifies the property (see AP-21 in Phase 2).

- **PATTERN 23-CROSS-G** → Tier 12: Storage Slot Stability
  Condition: `USES_UPGRADEABLE_PROXY=true` (from Phase 0 Step 4g)
  Property: Critical storage slots (admin, implementation, initialized) match expected values after any operation.
  Uses `vm.load(address(proxy), SLOT)` to read raw storage.

  ```solidity
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

  **ATTACK_SCENARIO:** "After an upgrade, a storage collision overwrites the admin slot with user data. The proxy admin is now a random address, and the real admin can never upgrade or recover the proxy. All funds locked permanently."

  **Implementation constraint:** `vm.load()` is a Foundry cheatcode. This property MUST be placed in CryticToFoundry only (or a separate FoundryProperties.sol). It cannot be included in CryticTester which runs under Echidna/Medusa.

### Token Compliance Templates (if ISSUES_TOKENS=true and overrides exist) (NEW in v4.1)

These test the protocol's OWN issued ERC20 tokens for standard compliance. Only generated when the protocol deploys custom ERC20 contracts with overrides on transfer/approve/transferFrom. Skip if protocol uses unmodified OpenZeppelin ERC20.

- **PATTERN 23-ERC20-E** → Tier 12: Transfer-to-Self Conservation
  `token.transfer(msg.sender, amount)` must not change msg.sender's balance.
  ```solidity
  // Transfer to self must preserve balance
  uint256 before = token.balanceOf(actor);
  vm.prank(actor);
  token.transfer(actor, amount);
  uint256 afterBal = token.balanceOf(actor);
  eq(afterBal, before, "ERC20-E: self-transfer changed balance");
  ```

- **PATTERN 23-ERC20-F** → Tier 12: Approve Overwrites (No Additive Behavior)
  After `approve(spender, X)` then `approve(spender, Y)`, allowance must be Y, not X+Y.
  ```solidity
  // Approve must overwrite, not add
  vm.startPrank(actor);
  token.approve(spender, amount1);
  token.approve(spender, amount2);
  vm.stopPrank();
  eq(token.allowance(actor, spender), amount2, "ERC20-F: approve is additive, not overwrite");
  ```

- **PATTERN 23-ERC20-G** → Tier 12: Zero-Amount Transfer Succeeds
  `token.transfer(to, 0)` must not revert (composability requirement).
  ```solidity
  // Zero transfer must succeed
  vm.prank(actor);
  try token.transfer(otherActor, 0) {
      t(true, "ERC20-G: zero transfer succeeded");
  } catch {
      t(false, "ERC20-G: zero transfer reverted — breaks composability");
  }
  ```

- **PATTERN 23-ERC20-H** → Tier 12: Max Approval Persistence
  If allowance == type(uint256).max, transferFrom must NOT decrease it.
  ```solidity
  // Max approval must stay infinite after transferFrom
  vm.prank(actor);
  token.approve(spender, type(uint256).max);
  vm.prank(spender);
  token.transferFrom(actor, otherActor, amount);
  eq(token.allowance(actor, spender), type(uint256).max,
     "ERC20-H: max allowance decreased after transferFrom");
  ```

---

### TIER 16: WEIRD TOKEN INTEGRATION (WTOK-*) (NEW in v4.1)
**PRIORITY: MEDIUM — External Token Compatibility**

**Check `TOKEN_ASSUMPTION` from PROTOCOL CHARACTERISTICS section of `magic/contracts-dependency-list.md`.**
- If `TOKEN_ASSUMPTION=RESTRICTED`: Skip this tier entirely.
- If `TOKEN_ASSUMPTION=OPEN` or `TOKEN_ASSUMPTION=UNSPECIFIED`: This tier is MANDATORY.

**Attack scenario template:** "Protocol accepts arbitrary ERC20 tokens but doesn't account for non-standard transfer behavior. A fee-on-transfer token causes internal accounting to exceed actual balance (solvency violation). A rebasing token changes balances without protocol interaction. A missing-return token causes silent transfer failures."

This tier does NOT create fundamentally new property assertions — it documents which mock tokens must be deployed in Setup.sol so that existing SOL/PROFIT/VT properties catch the bugs.

**PATTERN 28-WTOK-A** → Fee-on-Transfer Solvency
Detection: `TOKEN_ASSUMPTION=OPEN|UNSPECIFIED` AND `FEE_ON_TRANSFER != ALREADY_HANDLED`
Setup: Deploy `MockFeeOnTransferERC20(fee=100 bps)` INSTEAD of standard `MockERC20`
Assertion: Existing SOL-* (Tier 2) must still hold: `internalAccounting <= token.balanceOf(protocol)`
```
### WTOK-01: Fee-on-transfer solvency
- Pattern: PATTERN 28-WTOK-A
- Mock: MockFeeOnTransferERC20(fee=100 bps)
- Assertion: SOL-* properties still hold (internal accounting <= balanceOf)
- Category: SIMPLE (re-uses existing SOL properties)
- Tier: 16
ATTACK_SCENARIO: "Protocol calls transferFrom(user, protocol, 100) but only receives 99 due to 1% fee.
Internal accounting records 100 but balanceOf(protocol) only has 99. After enough operations, protocol
is insolvent — users cannot withdraw their full balance."
ANTI-PATTERN_CHECK: Not tautological — no require in the protocol checks for fee-on-transfer.
Not structurally impossible — the accounting slot IS written by deposit/transfer.
```

**PATTERN 28-WTOK-B** → Rebasing Accounting Integrity
Detection: `TOKEN_ASSUMPTION=OPEN|UNSPECIFIED` AND `REBASING != ALREADY_HANDLED`
Setup: Deploy `MockRebasingERC20` with `rebase()` as a handler target function
Assertion: After positive rebase, solvency holds. After negative rebase, solvency may break (valid finding).
```
### WTOK-02: Rebasing token accounting integrity
- Pattern: PATTERN 28-WTOK-B
- Mock: MockRebasingERC20 with adjustable rebaseFactor
- Handler target: rebase(uint256 newFactor) — fuzzer can trigger rebases
- Assertion: After any rebase, internal accounting should still be <= real balance for positive rebase.
  Negative rebase breaking solvency IS a valid finding (protocol should handle it).
- Category: SIMPLE (re-uses existing SOL properties)
- Tier: 16
ATTACK_SCENARIO: "After a negative rebase, token.balanceOf(protocol) decreases but internal accounting
stays the same. Protocol becomes insolvent — users who withdraw first get funds, later users get nothing."
```

**PATTERN 28-WTOK-C** → Missing Return Value Compatibility
Detection: `TOKEN_ASSUMPTION=OPEN|UNSPECIFIED` AND `MISSING_RETURN != ALREADY_HANDLED`
Note: This is primarily a STATIC flag — if the protocol uses raw `IERC20.transfer()` instead of
`SafeERC20.safeTransfer()`, the transfer will silently fail on tokens like USDT that don't return bool.
```
### WTOK-03: Missing return value compatibility
- Pattern: PATTERN 28-WTOK-C
- Detection: Static — grep for raw `.transfer()` and `.transferFrom()` without SafeERC20
- Category: FLAG (static detection, not a runtime property)
- Tier: 16
ATTACK_SCENARIO: "Protocol uses IERC20(token).transfer() on a token that doesn't return bool (USDT).
The call doesn't revert but returns empty data, which Solidity decodes as false/reverts depending on
version. Users cannot withdraw their funds."
```

**PATTERN 28-WTOK-D** → Low Decimals Precision
Detection: `TOKEN_ASSUMPTION=OPEN|UNSPECIFIED` AND `LOW_DECIMALS != ALREADY_HANDLED`
Setup: Deploy `MockERC20(decimals=2)` or `MockERC20(decimals=6)` as primary token
Assertion: Existing MATH-* (Tier 6) round-trip properties still hold. Share price calculations
don't lose significant precision with low decimal tokens.
```
### WTOK-04: Low decimals precision
- Pattern: PATTERN 28-WTOK-D
- Mock: MockERC20 with decimals=2 (GUSD-like) or decimals=6 (USDC-like)
- Assertion: MATH-* round-trip properties still hold, no zero-share minting for non-zero deposits
- Category: SIMPLE (re-uses existing MATH/ER properties)
- Tier: 16
ATTACK_SCENARIO: "With 2-decimal token, deposit(1) = 0.01 tokens. Share calculation:
shares = 1 * totalShares / totalAssets may round to 0. Depositor loses 0.01 tokens silently."
```

Minimum: 2 properties (if TOKEN_ASSUMPTION=OPEN|UNSPECIFIED; 0 if RESTRICTED)

---

### TIER 17: PRECISION LOSS ACCUMULATION (ACCUM-*) (NEW in v4.1)
**PRIORITY: MEDIUM — Accumulated Rounding Insolvency**

**Check `PRECISION_ACCUMULATION` from `magic/economic-oracles.md`.** If NOT_APPLICABLE, skip.

**Attack scenario template:** "Individual deposit-withdraw cycles pass round-trip checks, but after 1000+ cycles, rounding dust accumulates. Either (a) protocol becomes insolvent as accounting exceeds real balance, (b) users extract rounding dust via many small operations, or (c) small deposits round to zero shares causing silent value loss."

**PROPERTY_TYPE:** SIMPLE (checked after every operation using ghost counters)

**PATTERN 27-A — Deposit-Withdraw Precision Drift Bounded:**
Detection: Protocol has deposit + withdraw (or mint/redeem) with integer division.
Pattern: Per-actor drift stays proportional to operation count.
```
### ACCUM-01: Deposit-withdraw precision drift bounded
- Pattern: PATTERN 27-A
- Category: SIMPLE
- Tier: 17
- Ghost variables:
  - _accumulatedOps[actor]: count of deposit+withdraw operations by this actor
  - _actorNetDeposit[actor]: cumulative deposits minus withdrawals per actor

Pseudocode:
  // Drift = difference between what actor deposited net and what they could withdraw
  // Must stay proportional to operation count
  uint256 expectedBalance = _actorNetDeposit[currentActor];
  uint256 actualBalance = token.balanceOf(currentActor);
  if (expectedBalance > actualBalance) {
      uint256 drift = expectedBalance - actualBalance;
      uint256 allowedDrift = _accumulatedOps[currentActor] * MAX_DUST_PER_OP;
      lte(drift, allowedDrift, "ACCUM-01: precision drift exceeds bounded accumulation");
  }
  // MAX_DUST_PER_OP = 1 for 18-decimal tokens, 1 for 6-decimal tokens (1 unit of smallest denomination)

ATTACK_SCENARIO: "Attacker performs 10000 small deposit-withdraw cycles. Each cycle extracts
1 wei of rounding dust. After 10000 cycles, attacker has extracted 10000 wei from the protocol.
At scale with low-decimal tokens (USDC), this becomes 0.01 USDC per 10000 ops."
ANTI-PATTERN_CHECK: Not tautological — no require guards against accumulated drift.
Not AP-2 — deposit and withdraw both write to the accounting slot.
```

**PATTERN 27-B — Protocol-Side Solvency Gap Growth:**
Detection: Protocol has internal accounting variable + real token balance.
Pattern: Gap between real balance and accounting should not grow unboundedly with operations.
```
### ACCUM-02: Solvency gap does not grow unboundedly
- Pattern: PATTERN 27-B
- Category: SIMPLE
- Tier: 17
- Ghost variables:
  - _totalOps: count of all operations in this sequence
  - _previousSolvencyGap: gap between real balance and accounting at last check

Pseudocode:
  uint256 realBalance = token.balanceOf(address(protocol));
  uint256 accounting = protocol.totalAssets(); // or equivalent
  uint256 gap = realBalance > accounting ? realBalance - accounting : accounting - realBalance;
  if (_totalOps > 100) {
      // Gap should not grow faster than linearly with operations
      lte(gap, _previousSolvencyGap + MAX_DRIFT_PER_100_OPS,
          "ACCUM-02: solvency gap growing unboundedly");
  }
  _previousSolvencyGap = gap;

ATTACK_SCENARIO: "Each operation introduces 1 wei of rounding error in the same direction.
After 1M operations, the gap between real balance and accounting is 1M wei. For lending protocols
with compounding, this can be worse — each accrual compounds the previous rounding error."
ANTI-PATTERN_CHECK: Not tautological — protocol has no require preventing gap growth.
Distinct from SOL-* (Tier 2) which checks solvency at a point in time, not growth rate.
```

**PATTERN 27-C — Small Deposit Zero-Share Prevention:**
Detection: Protocol has share-based accounting (ERC4626 or similar).
Pattern: Non-zero deposit must either mint non-zero shares or revert.
```
### ACCUM-03: Small deposits don't round to zero shares
- Pattern: PATTERN 27-C
- Category: NEGATIVE
- Tier: 17

Pseudocode:
  uint256 amount = ...; // fuzzer-provided, clamped > 0
  if (amount == 0) return;
  uint256 sharesBefore = vault.balanceOf(actor);
  try vault.deposit(amount, actor) {
      uint256 sharesAfter = vault.balanceOf(actor);
      gt(sharesAfter, sharesBefore, "ACCUM-03: deposit minted 0 shares — silent value loss");
  } catch {
      // Revert is acceptable — protocol rejects too-small deposits
  }

ATTACK_SCENARIO: "User deposits 1 wei. Protocol calculates shares = 1 * totalShares / totalAssets
and rounds down to 0. User loses 1 wei permanently. Attacker front-runs with large deposit + donation
to inflate share price, then all subsequent small deposits mint 0 shares."
ANTI-PATTERN_CHECK: Distinct from PATTERN 25 (share inflation) which tests first-depositor attack.
ACCUM-03 tests ongoing zero-share minting at ANY totalSupply, not just first deposit.
```

Minimum: 3 properties (if PRECISION_ACCUMULATION=APPLICABLE; 0 if NOT_APPLICABLE)

---

## ECONOMIC ORACLE INTEGRATION (NEW in v3.5)

**Read `magic/economic-oracles.md`** (if it exists). This file contains per-vulnerability-class analysis from Phase 0 Step 6.

### Mapping Vulnerability Classes to Tiers

For each class marked APPLICABLE with HIGH or MEDIUM confidence, generate 1-3 concrete properties using the protocol's actual API:

| Vulnerability Class | Target Tier | Pattern ID | Property Focus |
|---------------------|-------------|------------|----------------|
| AMM_INVARIANT_VIOLATION | Tier 2 | PATTERN 24-A | Constant product / invariant preservation |
| SLIPPAGE_MANIPULATION | Tier 7A | PATTERN 24-B | Output bounds, sandwich resistance |
| ORACLE_MANIPULATION | Tier 8 | PATTERN 24-C | Price deviation bounds, TWAP consistency |
| FLASH_LOAN_ARBITRAGE | Tier 0 | PATTERN 24-D | Same-block profit extraction (covered by PROFIT-*) |
| COLLATERAL_RATIO_VIOLATION | Tier 3 | PATTERN 24-E | System-wide and per-position solvency |
| SHARE_INFLATION | Tier 8 | PATTERN 24-F | First-depositor attack, share price manipulation |
| FEE_EXTRACTION | Tier 9 | PATTERN 24-G | Fee bypass, fee accumulation correctness |
| GOVERNANCE_MANIPULATION | Tier 10B | PATTERN 24-H | Flash-loan voting, proposal manipulation |
| PRECISION_ACCUMULATION | Tier 17 | PATTERN 27 | Multi-operation rounding drift, solvency gap growth |

### Generation Rules

1. **Only generate for APPLICABLE classes** — skip NOT_APPLICABLE
2. **Use the monitoring variables** listed in economic-oracles.md for property assertions
3. **Check prerequisites** — if the class requires oracle infrastructure and it's BLOCKED_BY_INFRASTRUCTURE, mark the property accordingly
4. **Avoid duplicates** — if a tier already has a property covering the same invariant (from the templates above or from standard tier generation), add a cross-reference instead of a duplicate
5. **PATTERN 24-D (FLASH_LOAN_ARBITRAGE)** is typically covered by PROFIT-01/02 — only add explicit flash loan properties if the protocol has flash loan callbacks that need specific testing

6. **PATTERN 24-I (FLASH_LOAN_PROFITABILITY)** — Tier 0: Flash Loan Profitability Bounds. Protocol balance after a flash loan operation must be >= balance before. Applicable when FLASH_LOAN_ARBITRAGE class is APPLICABLE.
   ```solidity
   // Flash loan profitability bounds
   uint256 protocolBalanceBefore = IERC20(token).balanceOf(address(protocol));
   // ... flash loan operation executes ...
   uint256 protocolBalanceAfter = IERC20(token).balanceOf(address(protocol));
   gte(protocolBalanceAfter, protocolBalanceBefore, "PATTERN-24-I: protocol lost funds in flash loan");
   ```

7. **PATTERN 24-J (SANDWICH_RESISTANCE)** — Tier 7A: General Sandwich Resistance. For non-AMM protocols with reversible operations: snapshot state → execute operation A → reverse operation A → verify no profit exceeds DUST_TOLERANCE.
   ```solidity
   // General sandwich resistance
   uint256 snapshotId = vm.snapshot();
   uint256 balanceBefore = IERC20(token).balanceOf(actor);
   protocol.operationA(amount);
   protocol.reverseA(amount);
   uint256 balanceAfter = IERC20(token).balanceOf(actor);
   t(balanceAfter <= balanceBefore + DUST_TOLERANCE, "PATTERN-24-J: sandwich profit detected");
   vm.revertTo(snapshotId);
   ```

### If economic-oracles.md Does Not Exist

Skip this section entirely. The standard tier generation and protocol-type templates provide adequate coverage without it. Do NOT attempt to independently analyze economic vulnerabilities — that's Phase 0's job.

---

## VERIFICATION CHECKLIST (Phase 1A)

Before completing, verify:
- [ ] Tier 0 PROFIT oracle properties generated (PATTERN 22) — MANDATORY for all DeFi
- [ ] All multi-level accounting variables have aggregation properties (PATTERN 1)
- [ ] All indexes/rates have minimum bound properties (PATTERN 2)
- [ ] Balance solvency verified for all tracked tokens (PATTERN 3)
- [ ] All config fields with MAX_* constants have bounds properties (PATTERN 4)
- [ ] All stored beneficiaries/receivers have membership validation (PATTERN 5)
- [ ] Share->asset->share round-trip tested (PATTERN 6)
- [ ] Asset->share->asset round-trip tested (PATTERN 7)
- [ ] Critical values in custom uint types have range bounds (PATTERN 8)
- [ ] Health factor protection properties if protocol has liquidations (PATTERN 9)
- [ ] Liquidation blocking properties (PATTERN 10)
- [ ] Time-dependent monotonicity if TIME_BASED=true (PATTERN 13)
- [ ] Accrual proportionality if TIME_BASED=true (PATTERN 14)
- [ ] Zero-time no-op if TIME_BASED=true (PATTERN 15)
- [ ] Reentrancy atomicity if MULTI_ACTOR=true and external calls precede state updates (PATTERN 16)
- [ ] Shared resource integrity if MULTI_ACTOR=true and storage written by 2+ callers (PATTERN 17)
- [ ] CANARY properties cover at least the hardest-to-reach paths from reachability analysis
- [ ] Protocol-type templates applied if PROTOCOL_TYPE is set (PATTERN 23-*)
- [ ] Economic oracle properties generated for all APPLICABLE classes with HIGH/MEDIUM confidence (PATTERN 24-*)
- [ ] Cross-protocol templates applied: locked funds (CROSS-A), delegatecall safety (CROSS-B), selfdestruct protection (CROSS-C)
- [ ] Flash loan profitability bounds generated if FLASH_LOAN_ARBITRAGE is APPLICABLE (PATTERN 24-I)
- [ ] General sandwich resistance generated for non-AMM protocols with reversible operations (PATTERN 24-J)
- [ ] PRIV-NEG properties generated for all admin setter functions (Tier 7B-PRIV)
- [ ] Share inflation / first-depositor attack tested for vault/pool protocols (PATTERN 25)
- [ ] Math library inverse function pairs tested for round-trip inflation (PATTERN 26)
- [ ] Deposit-withdraw sandwich resistance tested for deposit/withdraw protocols (PATTERN 23-CROSS-D)
- [ ] Token compliance properties generated if ISSUES_TOKENS=true and overrides exist (PATTERN 23-ERC20-E through H)
- [ ] Weird token integration properties generated if TOKEN_ASSUMPTION=OPEN|UNSPECIFIED (PATTERN 28-WTOK-A through D)
- [ ] Precision accumulation properties generated if PRECISION_ACCUMULATION=APPLICABLE (PATTERN 27-A through C)
- [ ] State machine properties generated if HAS_INITIALIZER/HAS_PAUSE/USES_UPGRADEABLE_PROXY detected (PATTERN 23-CROSS-E/F/G)
- [ ] Re-initialization protection properties if HAS_INITIALIZER=true (PATTERN 23-CROSS-E)
- [ ] Pause-freeze invariant property if HAS_PAUSE=true (PATTERN 23-CROSS-F)
- [ ] All DOOM/liveness properties include pause guard when HAS_PAUSE=true (PAUSE_GUARD_ON_DOOM rule)
- [ ] Storage slot stability property if USES_UPGRADEABLE_PROXY=true (PATTERN 23-CROSS-G)
- [ ] Fee volume conservation property if protocol has fee mechanism (PATTERN 29)
- [ ] PRIV-AUTH auth sweep properties generated for all access-controlled functions not in PRIV-NEG (Phase 0 Step 4h)
- [ ] HIGH_TAINT functions have minimum 4 properties each (if taint analysis exists)
- [ ] MEDIUM_TAINT functions have minimum 2 properties each (if taint analysis exists)
- [ ] LOW_TAINT functions have CANARY coverage (if taint analysis exists)
- [ ] NO_TAINT functions skipped — no properties wasted on view/pure helpers (if taint analysis exists)
- [ ] Every property has an ATTACK_SCENARIO
- [ ] Every property has an ANTI-PATTERN_CHECK

If any applicable pattern is missing properties, ADD them before completing this phase.

---

## Important Filters (do NOT write properties that)

- Are tied to immutable values (e.g., "owner is immutable")
- Check something guaranteed by Solidity types (e.g., "uint >= 0")
- Restate the same condition as a `require`/`revert` (AP-1)
- Check that a function doesn't change a variable it never writes to (AP-2)
- Test trivially simple utility functions (AP-3)
- Depend on ghost variables without verifying updateGhosts (AP-4)
- Require infrastructure not present in the test harness (AP-5)
- Use positive assertions for negative tests (AP-6)
- Repeat the same math as in the contract without adding independent verification
- Depend only on EVM/gas limits
- Are only about event emission
