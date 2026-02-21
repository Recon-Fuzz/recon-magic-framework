---
description: "Phase 0 of the Efficient Properties Workflow v4.0. Builds on v3.8 with setup liveness validation (contract != address(0) checks, target function revert rate prediction)."
mode: subagent
temperature: 0.1
---

## Role
You are the @properties-phase-0 agent.

We're specifying properties for the smart contract system in scope.

Review all files, start by making notes of which function calling which.
As well as which storage slot is influenced by which function.

---

## Step 1: Dependency List

List out all contracts and all functions in a file called `magic/contracts-dependency-list.md`
```
## ContractName.sol
### function1
Storage Slots Read:
- balanceOf

Storage Slots Written:
- balanceOf
- allowance

Calls:
- function2
- function3

is called by:
- function4
- function5
```

---

## Step 2: Review Priority

Create a second file `magic/properties-review-priority.md`
And list out the order at which you should analyze each function and contract.
Base this on the complexity of the dependency list for storage and function calls.
More calls and storage influenced means you should review those later.

---

## Step 3: Reachability Analysis + Shortcut Creation (REQUIRED)

After completing the dependency list and review priority, perform a **reachability analysis** and **create shortcut target functions** for branches the fuzzer can't reach with standard target functions.

### Purpose

A fuzzer can only test code paths it can reach. If an important branch has complex preconditions (multi-step state setup, specific msg.sender, external contract state), the fuzzer will never exercise it. You MUST identify these branches and create shortcut functions so the fuzzer can reach them from day one.

### 3a: Identify Guarded Branches

For each function in the in-scope contracts (`src/`), identify branches that require specific preconditions:

**Access control gates:**
```solidity
require(msg.sender == controller, "!controller");  // Only callable by controller contract
require(msg.sender == vaults[_token], "!vault");    // Only callable by vault contract
```
These functions can only be called by specific contracts, not by external actors. A fuzzer calling them directly will always revert.

**State-dependent branches:**
```solidity
if (b < r) { ... }           // Requires: vault balance < owed amount (tokens moved to strategy)
if (_want != _token) { ... } // Requires: strategy with different want token configured
if (_after > _before) { ... } // Requires: external contract actually returned tokens
```
These branches need specific state that may only exist after a particular sequence of operations.

**Multi-contract call chains:**
```solidity
// yVault.withdraw() -> controller.withdraw() -> strategy.withdraw()
// This chain only fires when vault doesn't have enough tokens
```
Some code paths require one contract to call another, which only happens through a specific entry point.

### 3b: Classify Each Branch

For each guarded branch, classify it as:

| Reachability | Description | Action Needed |
|-------------|-------------|---------------|
| **DIRECT** | Callable directly by an external actor with basic clamping | None — standard target function works |
| **INDIRECT** | Only callable through another contract's function | Create a shortcut that triggers the full call chain |
| **MULTI-STEP** | Requires a specific state after a sequence of operations | Create a shortcut that atomically sets up state and exercises the branch |
| **MOCK-DEPENDENT** | Depends on external contract behavior | Verify mock is correctly implemented and funded in Setup.sol |

### 3c: Check Existing Target Functions

Before creating shortcuts, read ALL existing target function files:
- `test/recon/TargetFunctions.sol`
- All files under `test/recon/targets/*.sol`

Check if a shortcut already exists for the identified branch. If it does, verify it:
1. Actually reaches the target branch (trace the execution path)
2. Doesn't silently revert before reaching the branch
3. Has proper input clamping so it doesn't waste fuzzer cycles

If an existing shortcut has issues (e.g., early returns that prevent reaching the branch, missing precondition setup), document the issue and create a fixed version.

### 3d: Create Shortcut Target Functions

For each INDIRECT or MULTI-STEP branch that has NO working shortcut, create a new target function. Rules:

**Where to put shortcuts:**
- If the shortcut exercises a single contract, put it in the corresponding `targets/*.sol` file
- If the shortcut spans multiple contracts, put it in `TargetFunctions.sol`

**Modifier:**
- Use `updateGhosts` for shortcut functions that combine multiple operations atomically
- NEVER use `trackOp` for shortcuts — they don't map to a single protocol operation

**Function structure:**
```solidity
/// @notice Shortcut: exercises [Contract.function()] [branch description] (line X)
///         Requires: [precondition description]
function shortcut_[descriptive_name](uint256 param1) public updateGhosts {
    // Step 1: Set up precondition
    // Use early returns (not require) for conditions that can't be met
    // Step 2: Exercise the target branch
    // Step 3: Clean up if needed (restore original state for non-destructive testing)
}
```

**Input clamping:**
- Clamp all inputs to valid ranges: `amount = amount % (maxValue + 1);`
- Use early returns instead of require: `if (amount == 0) return;`
- Never let the shortcut revert — reverts waste fuzzer cycles

**Precondition setup within the shortcut:**
- If the branch needs tokens in a specific location, transfer them first
- If the branch needs a specific strategy/config, set it up and restore after
- Use `vm.prank()` for calls that need a specific msg.sender

**Mock verification:**
- For MOCK-DEPENDENT branches, check that the mock can actually handle the call
- If Setup.sol needs changes (e.g., more funding for a mock), document it in the reachability report but do NOT modify Setup.sol — add it to `magic/setup-changes-needed.md` instead

### 3e: Write Reachability Report

Write the analysis to `magic/reachability-analysis.md`:

```markdown
## Reachability Analysis

### Summary Table
| Function | Branch | Line | Classification | Shortcut | Status |
|----------|--------|------|---------------|----------|--------|
| Contract.function | condition | X | MULTI-STEP + INDIRECT | shortcut_name | CREATED / EXISTS / FIXED |

### Branches Reachable via Direct Calls
- ContractName.functionName() — all branches reachable with standard target functions
- ...

### Shortcuts Created
- `shortcut_xxx` in `TargetFile.sol` — exercises [branch], [brief explanation]
- ...

### Shortcuts Already Present
- `shortcut_yyy` in `TargetFunctions.sol` — exercises [branch], verified working / HAS ISSUE: [description]
- ...

### Setup Changes Needed
- [If any mock funding or configuration changes are needed in Setup.sol, list them here]
- [These will be addressed separately, not by this agent]
```

### 3f: Verify Compilation

After creating shortcuts, run `forge build` to verify the project compiles. If there are compilation errors in the files you modified, fix them immediately. Do NOT leave the project in a broken state.

---

## Step 4: Protocol Characteristic Detection (REQUIRED)

After completing the reachability analysis, detect protocol characteristics that inform property generation in Phase 1A and 1B. Append ALL findings to the bottom of `magic/contracts-dependency-list.md` under a new section:

```markdown
---
## PROTOCOL CHARACTERISTICS

### Multi-Actor Interactions
MULTI_ACTOR: [true/false]
Evidence: [list functions with multiple user roles, shared resources, or concurrent access patterns]
```

### 4a: Multi-Actor Detection

Scan the protocol for concurrent-access patterns:

1. **Multiple user roles**: Functions gated by different `msg.sender` requirements (admin, user, liquidator, keeper)
2. **Shared mutable resources**: Storage slots written by multiple external-facing functions from different callers
3. **Reentrancy vectors**: External calls (`call`, `transfer`, `safeTransfer`) followed by state updates in the SAME function
4. **Flash loan integration**: Functions that accept callbacks or interact with flash loan providers

Classify as `MULTI_ACTOR=true` if ANY of these are found:
- 2+ distinct roles can modify the same storage slot
- External calls precede state updates (reentrancy vector)
- Flash loan callbacks exist

```markdown
### Time-Based Logic
TIME_BASED: [true/false]
TIME_PATTERN: [accrual|vesting|epoch|lockup|none]
Evidence: [list functions using block.timestamp or block.number for state changes]
```

### 4b: Time-Based Logic Detection

Scan for time-dependent state changes:

1. **Accrual patterns**: `block.timestamp - lastUpdate` used to calculate interest, rewards, or fees
2. **Vesting/lockup**: `require(block.timestamp >= unlockTime)` or linear release calculations
3. **Epoch-based**: `currentEpoch`, `periodFinish`, cycle-based distributions

Classify as `TIME_BASED=true` if functions use `block.timestamp` or `block.number` to compute state-changing values (not just for event timestamps or logging).

For each time-dependent function, note:
- Which storage slots are affected by time passage
- Whether accrual compounds (compound interest) or is linear
- Minimum/maximum time deltas that affect behavior

```markdown
### Cross-Contract Dependencies
CROSS_CONTRACT: [true/false]
Evidence: [list external contract calls that affect accounting or state]
Cross-contract pairs:
- [ContractA.function() -> ContractB: accounting variable affected]
```

### 4c: Cross-Contract Dependency Detection

Scan the dependency list for external calls that affect protocol accounting:

1. **Balance synchronization**: Internal accounting variable + `IERC20(token).balanceOf(address(this))` — both should match
2. **Oracle dependencies**: Price or rate values fetched from external contracts used in calculations
3. **Multi-contract accounting**: Parent contract delegates funds to child contracts (vault->strategy, pool->market)
4. **Approval dependencies**: Protocol requires token approvals that could be revoked

For each cross-contract pair, note:
- Which internal variable tracks the external state
- Whether the values should be equal, or one should bound the other (<= or >=)
- How stale the external value can become

### 4d: Protocol Type Classification (NEW in v3.6)

Classify the protocol into one or more types based on strong-evidence signals. This classification drives protocol-specific property templates in Phase 1A and demand-driven fuzzer configuration.

**Method:** Scan all in-scope contracts for function signatures, storage patterns, and inheritance. Require 2+ signals for a positive classification.

| Type | Signals (need 2+) |
|------|-------------------|
| **AMM** | `swap()`, `addLiquidity()`, reserves state variable, `getAmountOut()` |
| **LENDING** | `borrow()`, `liquidate()`, `healthFactor` / `isHealthy()`, interest rate model |
| **VAULT** | ERC4626 inheritance OR (`deposit()` + `withdraw()` + `shares` + `convertToAssets()`) |
| **ERC20** | Custom ERC20 only — rebasing logic, fee-on-transfer, non-standard transfer returns |
| **GOVERNANCE** | `propose()`, `vote()`, `execute()`, timelock contract |
| **STAKING** | `stake()` + `unstake()`, `rewardRate`, `earned()` |
| **OTHER** | No clear match — default when fewer than 2 signals match any type |

**Classification rules:**
- Assign `PROTOCOL_TYPE` = strongest match (most signals)
- If a second type has 2+ signals, assign `SECONDARY_TYPE`
- If no type has 2+ signals, assign `OTHER`
- Document the evidence (which signals matched) for each classification

**Output:** Append to the PROTOCOL CHARACTERISTICS section of `magic/contracts-dependency-list.md`:

```markdown
### Protocol Type Classification
PROTOCOL_TYPE: [AMM|LENDING|VAULT|ERC20|GOVERNANCE|STAKING|OTHER]
SECONDARY_TYPE: [type or NONE]
Classification Evidence:
- [Signal 1]: [function/pattern found in ContractName.sol]
- [Signal 2]: [function/pattern found in ContractName.sol]
- ...
Confidence: [HIGH (3+ signals) | MEDIUM (2 signals) | LOW (defaulted to OTHER)]
```

---

## Step 5: Setup Wiring Analysis (NEW in v3.5)

After completing Steps 1-4, analyze the existing Setup.sol to identify wiring issues that will block property testing. This analysis produces `magic/setup-wiring-analysis.md` which Phase 3A will consume.

### 5a: Constructor Parameter Analysis

For EACH contract deployed in Setup.sol, check its constructor:

1. **Read the constructor source** for every contract instantiated with `new ContractName(...)`
2. **Classify each constructor parameter** as:
   - `ZERO_OK`: Works fine with `address(0)` or `0` (no external calls, no `immutable` usage that matters)
   - `NEEDS_REAL_VALUE`: The parameter is stored as `immutable` and used in access control or state reads later
   - `MAKES_EXTERNAL_CALL`: The constructor calls a method on this parameter (e.g., `market_.UNDERLYING_ASSET_ADDRESS()`) — WILL REVERT with `address(0)`

3. **For `NEEDS_REAL_VALUE` parameters**, identify what the correct value should be:
   - If it's a `gateway` or `admin` parameter: Use `address(this)` (the CryticTester contract)
   - If it's a token address: Use `_newAsset(decimals)` from AssetManager
   - If it's another protocol contract: Must be deployed first (note deployment order)
   - If it's an oracle or external dependency: Use a mock or skip deployment

4. **For `MAKES_EXTERNAL_CALL` parameters**, note:
   - Which method is called and what it expects
   - Whether a mock can satisfy it, or if deployment should be skipped

### 5b: Proxy Pattern Detection

Identify all contracts that use the proxy + implementation pattern:

1. **Detect proxy contracts**: Contracts with `setImplementation()`, `_implementation`, or that inherit from an Admin/Proxy base
2. **Detect implementation contracts**: Contracts whose name ends in `Implementation` or that are passed to `setImplementation()`
3. **Map proxy -> implementation** pairs
4. **Determine deployment order**: Implementation must be deployed before calling `proxy.setImplementation(impl)`
5. **Note**: State lives in the proxy via delegatecall. Target functions calling view functions must call through the proxy, not the implementation directly.

### 5c: Access Control Pattern Analysis

For each target function file, classify functions by their access control requirements:

1. **Gateway-only functions**: Functions with `_onlyGateway_` or `require(msg.sender == gateway)` modifier
   - These MUST use `asAdmin` modifier (pranks as `address(this)`) when `gateway = address(this)`
   - If currently using `asActor`, they will always revert

2. **Admin-only functions**: Functions with `onlyOwner`, `onlyAdmin`, or similar
   - These MUST use `asAdmin` modifier

3. **User functions**: Functions callable by any address (approve, transfer, etc.)
   - These should use `asActor` modifier

4. **Mixed functions**: Functions that check `msg.sender` against a stored address
   - Determine what address is stored and whether `asActor` or `asAdmin` is appropriate

### 5d: Funding Analysis

Identify what tokens/ETH are needed for target functions to succeed:

1. **Token requirements**: Which contracts need token balances? Which actors need token balances?
2. **Approval requirements**: Which contracts need token approvals from which addresses?
3. **ETH requirements**: Any `payable` functions that need ETH?
4. **Minimum amounts**: What's the minimum useful amount for each token (based on decimals)?

### 5e: Protocol Configuration Detection

Identify protocol-level configuration that must be set for the system to function:

1. **Oracle configuration**: Does the protocol need price feeds set up? What assets need prices?
2. **Market/symbol registration**: Does the protocol require registering markets, symbols, or pools?
3. **Fee/rate configuration**: Are there fee ratios, slippage limits, or other params that need non-zero values?
4. **Role assignments**: Do any contracts need roles assigned (e.g., keeper, liquidator)?

### 5f: Write Wiring Analysis Report

Write the analysis to `magic/setup-wiring-analysis.md`:

```markdown
## Setup Wiring Analysis

### Constructor Parameter Issues
| Contract | Parameter | Current Value | Classification | Correct Value | Notes |
|----------|-----------|---------------|---------------|---------------|-------|
| DToken | gateway_ | address(0) | NEEDS_REAL_VALUE | address(this) | immutable gateway used in _onlyGateway_ |
| VaultImplAave | market_ | address(0) | MAKES_EXTERNAL_CALL | SKIP_DEPLOYMENT | calls market_.UNDERLYING_ASSET_ADDRESS() |

### Proxy Wiring
| Proxy | Implementation | Status | Notes |
|-------|---------------|--------|-------|
| oracle | oracleImplementation | NEEDS_WIRING | setImplementation() not called |

### Deployment Order
1. Mock tokens (no deps)
2. Proxies (no deps)
3. Tokens with gateway=address(this)
4. Implementations with cross-deps
5. Wire proxies (setImplementation)
6. Full-dependency contracts (gateway impl, etc.)

### Target Function Modifier Fixes
| File | Function | Current Modifier | Correct Modifier | Reason |
|------|----------|-----------------|-------------------|--------|
| VaultTargets.sol | deposit | asActor | asAdmin | gateway-only function |

### Funding Requirements
| Recipient | Token | Amount | Approval Target |
|-----------|-------|--------|----------------|
| address(this) | tokenB0 | 1_000_000e6 | vaultImplementation |
| actors | tokenB0 | 1_000_000e6 each | — |

### Protocol Configuration Required
| Category | Action | Details |
|----------|--------|---------|
| Oracle | Set price feed | baseOracleOffchain.set("BTC", 8, 50000e8) |
| Symbol | Register symbol | addSymbol("BTCUSD", 1, params) |
| Swapper | Set slippage | setMaxSlippageRatio(tokenB0, 1e17) |

### Address Aliasing (from Step 5h)
| Alias Group | Addresses | Risk |
|-------------|-----------|------|
| [group name] | [addr1], [addr2] | [ACCOUNTING_ALIAS / ACCESS_ALIAS]: [description] |

Downstream flags:
- ACCOUNTING_ALIAS targets: [list property categories that must deduplicate]
- ACCESS_ALIAS targets: [list property categories that may be vacuously true]
```

### 5g: Verify No Modifications

**IMPORTANT:** Step 5 is ANALYSIS ONLY. Do NOT modify Setup.sol, target files, or any other files. All modifications happen in Phase 3A which reads this analysis.

### 5h: Address Aliasing Detection (NEW in v4.0)

Scan Setup.sol (and any helper setup contracts) for address aliasing — cases where two
or more distinct logical roles resolve to the same address at deployment time.

**Procedure:**
1. List every named address assigned in setUp() / constructor:
   - Contract deployer (`address(this)`)
   - Governance, admin, strategist, rewards, treasury, fee recipient, etc.
   - Each actor address
   - Any mock contract that doubles as a role holder
2. Build an equivalence map: group addresses that point to the same value.
   Common patterns that create aliases:
   - `constructor(address(this))` — deployer IS governance/admin/rewards
   - `setRewards(address(controller))` — rewards IS the controller
   - Single EOA used for multiple roles (governance + strategist)
   - Mock contract deployed once but registered in multiple slots
3. For each aliased group, emit a warning in `magic/setup-wiring-analysis.md` under the
   **Address Aliasing** section:

   | Alias Group | Addresses | Risk |
   |-------------|-----------|------|
   | deployer = rewards | `address(this)`, `controller.rewards()` | Accounting properties that sum `balanceOf(rewards) + balanceOf(deployer)` will DOUBLE-COUNT |
   | governance = strategist | `gov`, `controller.strategist()` | Access-control properties may be trivially satisfied |

4. Flag downstream impact:
   - **ACCOUNTING_ALIAS**: Any conservation / total-balance property MUST deduplicate
     aliased addresses before summing balances.
   - **ACCESS_ALIAS**: Privilege-escalation properties gated on `actor != role` may
     be vacuously true if actor IS the role.

Phase 1 and Phase 3 MUST consume these flags when generating/implementing properties.

---

## Step 6: Economic Oracle Identification (NEW in v3.6)

After completing Steps 1-5, scan the protocol for economic vulnerability classes and document applicable oracles. This analysis produces `magic/economic-oracles.md` which Phase 1A will consume to generate targeted economic properties.

### 6a: Vulnerability Class Scan

For each of the following 8 vulnerability classes, determine if it applies to this protocol:

| Vulnerability Class | Applies When | Key Indicators |
|---------------------|-------------|----------------|
| **AMM_INVARIANT_VIOLATION** | Protocol has AMM/swap logic | `swap()`, reserves, constant product formula |
| **SLIPPAGE_MANIPULATION** | Protocol has swap or exchange operations | Slippage parameters, `minAmountOut`, deadline checks |
| **ORACLE_MANIPULATION** | Protocol reads external price feeds | `getPrice()`, `latestAnswer()`, TWAP logic |
| **FLASH_LOAN_ARBITRAGE** | Protocol has flash loans or atomic composability | `flashLoan()`, callback patterns, same-block operations |
| **COLLATERAL_RATIO_VIOLATION** | Protocol has collateralized positions | `healthFactor`, `collateralRatio`, `ltv` |
| **SHARE_INFLATION** | Protocol has share/asset conversion | ERC4626, `convertToShares()`, first-depositor patterns |
| **FEE_EXTRACTION** | Protocol collects fees | `feeRate`, `protocolFee`, fee-on-transfer |
| **GOVERNANCE_MANIPULATION** | Protocol has on-chain governance | `propose()`, `vote()`, quorum, flash-loan voting |

### 6b: Document Applicable Classes

For each class marked APPLICABLE:
1. **Contracts/Functions**: Which contracts and functions are involved
2. **Economic Invariant**: What economic property should hold (e.g., "xy=k after swap")
3. **Attack Vector**: How an attacker would exploit a violation
4. **Monitoring Variables**: Which storage slots or view functions to track
5. **Prerequisites**: What infrastructure is needed to test (oracles, multi-actor, time-warping)

### 6c: Write Economic Oracles Report

Write the analysis to `magic/economic-oracles.md`:

```markdown
## Economic Oracle Analysis

### Summary Table
| Vulnerability Class | Status | Confidence | Contracts | Notes |
|---------------------|--------|------------|-----------|-------|
| AMM_INVARIANT_VIOLATION | APPLICABLE | HIGH | UniswapPair.sol | xy=k invariant |
| SLIPPAGE_MANIPULATION | APPLICABLE | MEDIUM | Router.sol | minAmountOut param |
| ORACLE_MANIPULATION | NOT_APPLICABLE | — | — | No external oracles |
| FLASH_LOAN_ARBITRAGE | NOT_APPLICABLE | — | — | No flash loan support |
| COLLATERAL_RATIO_VIOLATION | NOT_APPLICABLE | — | — | Not a lending protocol |
| SHARE_INFLATION | APPLICABLE | HIGH | Vault.sol | ERC4626 first-depositor |
| FEE_EXTRACTION | APPLICABLE | LOW | Router.sol | Swap fee logic |
| GOVERNANCE_MANIPULATION | NOT_APPLICABLE | — | — | No governance |

### Detailed Analysis

#### AMM_INVARIANT_VIOLATION
- **Contracts**: UniswapPair.sol (swap, mint, burn)
- **Economic Invariant**: reserve0 * reserve1 >= k (constant product)
- **Attack Vector**: Manipulate reserves via direct transfer + swap to extract more than deposited
- **Monitoring Variables**: reserve0, reserve1, kLast, totalSupply
- **Prerequisites**: Multi-actor setup, token funding

#### SHARE_INFLATION
- **Contracts**: Vault.sol (deposit, withdraw, convertToShares, convertToAssets)
- **Economic Invariant**: share price monotonically non-decreasing for non-fee operations
- **Attack Vector**: First depositor donates tokens to inflate share price, causing rounding to zero for subsequent depositors
- **Monitoring Variables**: totalAssets(), totalSupply(), balanceOf(vault)
- **Prerequisites**: Multi-actor, small deposit amounts
```

### 6d: Handle Missing Data Gracefully

- If the protocol type is OTHER or unknown, still scan all 8 classes — some may apply regardless of type
- If a class has uncertain applicability, mark as `APPLICABLE` with `LOW` confidence — Phase 1A will generate properties conservatively
- If no classes apply (pure utility contract), create the file with all NOT_APPLICABLE and a note explaining why

---

## Step 7: Data-Flow Taint Analysis (NEW in v3.7)

After completing Steps 1-6, perform a data-flow taint analysis to identify functions with the highest exploitability potential. This analysis produces `magic/dataflow-taint-analysis.md` which Phase 1A will consume to inform property density and prioritization.

### 7a: Identify Taint Sources

For each function in the in-scope contracts (`src/`), identify all data inputs that could be attacker-controlled:

| Source Type | Tag | Example |
|-------------|-----|---------|
| Function parameters | PARAM | `function deposit(uint256 amount)` — `amount` is tainted |
| msg.value | MSG_VALUE | `msg.value` in payable functions |
| Oracle returns | ORACLE | `oracle.getPrice()` return value |
| External call returns | EXTERNAL | `IERC20(token).balanceOf(addr)` return value |
| block.timestamp | TIME | `block.timestamp` used in calculations |

### 7b: Identify Sensitive Sinks

For each function, identify operations where tainted data reaches a security-sensitive operation:

| Sink Type | Severity | Example |
|-----------|----------|---------|
| Token transfers | CRITICAL | `IERC20(token).transfer(to, amount)` where `amount` is tainted |
| Burn/mint operations | CRITICAL | `_mint(to, shares)` where `shares` derived from tainted input |
| Balance storage writes | CRITICAL | `balanceOf[user] = newBalance` where `newBalance` is tainted |
| Access control state | HIGH | `owner = newOwner` where `newOwner` is tainted |
| Configuration state | HIGH | `feeRate = newRate` where `newRate` is tainted |

### 7c: Trace Taint Propagation

For each tainted source, trace how taint flows through the code:

1. **Direct flow**: Tainted variable assigned directly to another variable
   - `uint256 shares = amount * totalShares / totalAssets;` — if `amount` is tainted, `shares` is tainted
2. **Arithmetic propagation**: Taint flows through arithmetic operations
   - `uint256 fee = amount * feeRate / BPS;` — if `amount` is tainted, `fee` is tainted
3. **Control flow dependency**: Variable's value depends on a tainted condition
   - `if (amount > threshold) { mode = LARGE_DEPOSIT; }` — `mode` is control-flow tainted
4. **Cross-function propagation**: Taint flows from one function's output to another's input
   - `convertToShares(amount)` returns tainted value used in `_mint(shares)`

For each taint path, compute **taint depth**:
- **0** (direct): Tainted source reaches sink in the same expression/statement
- **1** (one intermediate): One intermediate variable between source and sink
- **2+** (multiple): Two or more intermediate variables — higher depth = harder to exploit but still possible

### 7d: Score and Rank

For each function, compute an exploitability score:

```
exploitability = sink_count * source_diversity * (1 + max_taint_depth)
```

Where:
- `sink_count`: Number of CRITICAL or HIGH sinks reached by tainted data
- `source_diversity`: Number of distinct taint source types (PARAM, MSG_VALUE, ORACLE, EXTERNAL, TIME)
- `max_taint_depth`: Maximum taint depth across all paths in the function

Classify each function:
- **HIGH_TAINT** (exploitability >= 6): Deep taint propagation, multiple sources reaching critical sinks
- **MEDIUM_TAINT** (exploitability 2-5): Some taint propagation but limited sink exposure
- **LOW_TAINT** (exploitability 1): Minimal taint — single source, single shallow path
- **NO_TAINT** (exploitability 0): No taint sources reach any sinks (view functions, pure helpers)

### 7e: Write Taint Analysis Report

Write the analysis to `magic/dataflow-taint-analysis.md`:

```markdown
## Data-Flow Taint Analysis

### Summary Table
| Function | Contract | Exploitability | Classification | Sources | Sinks | Max Depth |
|----------|----------|---------------|----------------|---------|-------|-----------|
| deposit | Vault.sol | 8 | HIGH_TAINT | PARAM, EXTERNAL | transfer, mint | 2 |
| withdraw | Vault.sol | 6 | HIGH_TAINT | PARAM, ORACLE | transfer, burn | 1 |
| setFee | Vault.sol | 2 | MEDIUM_TAINT | PARAM | config state | 0 |
| totalAssets | Vault.sol | 0 | NO_TAINT | — | — | — |

### Classification Thresholds
- HIGH_TAINT: exploitability >= 6 (deep invariants, exact-delta VT, cross-function, rounding properties needed)
- MEDIUM_TAINT: exploitability 2-5 (standard directional checks, boundary conditions)
- LOW_TAINT: exploitability 1 (CANARY-only coverage verification)
- NO_TAINT: exploitability 0 (skip — view functions, pure helpers)

### Per-Function Taint Map

#### HIGH_TAINT Functions

##### Vault.deposit(uint256 amount)
Sources:
- amount (PARAM) → taint depth 0
- IERC20(asset).balanceOf(address(this)) (EXTERNAL) → taint depth 1

Taint Paths:
1. amount → shares = convertToShares(amount) → _mint(msg.sender, shares) [CRITICAL: mint]
2. amount → IERC20(asset).transferFrom(msg.sender, address(this), amount) [CRITICAL: transfer]
3. balanceOf(this) → totalAssets() → shares calculation [CRITICAL: affects mint amount]

...

#### MEDIUM_TAINT Functions
...

#### LOW_TAINT Functions
...
```

### 7f: Handle Edge Cases

- If a function has no parameters and makes no external calls, classify as NO_TAINT
- If taint analysis is uncertain (e.g., complex assembly blocks), classify as MEDIUM_TAINT conservatively
- For delegate calls, assume the return value is tainted (EXTERNAL source)
- For functions only callable by admin/owner, still analyze taint — admin key compromise is a valid attack vector

---

## Step 8: Function Transition Graph (NEW in v3.8)

After completing Steps 1-7, build a function transition graph that captures state-enabling relationships between target functions. This analysis produces `magic/function-transitions.json` which the full-audit pipeline will consume for pre-fuzzing sequence analysis and coverage iteration dead-cycle analysis.

### 8a: Identify State-Enabling Relationships

For each pair of target functions (A, B) in the in-scope contracts, determine if:

1. **A writes a storage slot that B reads as a precondition** — e.g., `approve` writes `allowance`, `transferFrom` reads `allowance` in a `require`
2. **A creates a position/balance that B requires** — e.g., `deposit` creates a balance, `withdraw` requires a non-zero balance
3. **A changes state that unlocks a branch in B** — e.g., `stake` sets `isStaked=true`, `claimRewards` requires `isStaked==true`
4. **A's output feeds B's input** — e.g., `mint` returns shares, `redeem` consumes shares

Use the Step 1 dependency list (`magic/contracts-dependency-list.md`) to identify storage slots read/written per function. Focus on pairs where A's written slots overlap with B's read slots.

### 8b: Assign Transition Weights

Score each identified transition based on how strongly B depends on A:

| Weight Range | Meaning | Example |
|-------------|---------|---------|
| **0.9-1.0** | B always reverts without A | `transferFrom` reverts without prior `approve` |
| **0.7-0.8** | B reaches significantly more branches after A | `withdraw` reaches more paths after `deposit` |
| **0.5-0.6** | B is more likely to succeed after A | `borrow` succeeds more often after `supplyCollateral` |
| **0.3-0.4** | Indirect influence only | `setFee` indirectly affects `withdraw` amounts |

Omit transitions with weight below 0.3 — these are too weak to guide fuzzer sequencing.

### 8c: Identify Entry Points and Terminal States

- **Entry points** = functions callable with no prior state setup (deposit, approve, mint, stake). These are the starting nodes of the graph.
- **Terminal states** = functions that consume state without enabling others (withdraw, burn, liquidate, claimRewards). These are the ending nodes.

### 8d: Write Output

Write the transition graph to `magic/function-transitions.json`:

```json
{
  "transitions": [
    {"from": "approve", "to": "transferFrom", "weight": 0.9, "reason": "transferFrom requires prior approval"},
    {"from": "deposit", "to": "withdraw", "weight": 0.8, "reason": "withdraw requires deposited balance"},
    {"from": "deposit", "to": "borrow", "weight": 0.7, "reason": "borrow requires collateral from deposit"},
    {"from": "borrow", "to": "repay", "weight": 0.8, "reason": "repay requires outstanding borrow position"},
    {"from": "borrow", "to": "liquidate", "weight": 0.7, "reason": "liquidate requires unhealthy borrow position"}
  ],
  "entry_points": ["deposit", "approve", "mint"],
  "terminal_states": ["withdraw", "burn", "liquidate"],
  "protocol_type": "VAULT"
}
```

- `protocol_type`: Copy from the PROTOCOL_TYPE classification in Step 4d
- Order transitions by weight (highest first)
- Include the `reason` field for every transition — it helps coverage iteration understand why the sequence matters

### 8e: Handle Edge Cases

- **Few functions (< 5)**: Still produce the graph — even small protocols benefit from sequence guidance
- **Circular dependencies**: Include both directions with appropriate weights (e.g., `deposit` → `withdraw` at 0.8, `withdraw` → `deposit` at 0.5)
- **Insufficient data**: Use conservative weights (0.5) when the relationship is plausible but not certain from static analysis
- **Pure view/admin functions**: Omit from the graph — they don't enable state transitions for other functions

---

---

## Step 9: Setup Liveness Validation (NEW in v4.0)

After completing Steps 1-8, generate a deployment liveness check list in `magic/setup-wiring-analysis.md` (append if exists):

### 9a: Contract Liveness Assertions

For every contract classified as `NEEDS_REAL_VALUE` in the constructor parameter table (Step 5a), add to the RECOMMENDATIONS section:

```
LIVENESS_CHECK: require(address(contractName) != address(0), "SETUP: contractName not deployed");
```

These assertions should be added to Setup.sol by Phase 3A as a `_validateDeployment()` internal function called at the end of `setup()`.

### 9b: Target Function Revert Rate Prediction

For each target function with modifier mismatch (e.g., `asActor` on `onlyOwner` function), flag:

```
ALWAYS_REVERTS: lendingPool_initReserve — asActor but requires onlyLendingPoolConfigurator
  → Wastes 100% of fuzzer cycles. Fix: change to asAdmin or REMOVE.
```

This prevents the Enzyme/Radiant pattern where admin targets silently waste budget.


## Important Notes

- This analysis is based on **static review** of the source code. It identifies branches that LIKELY need special handling.
- Not every MULTI-STEP branch needs a shortcut — if the sequence is short (1-2 steps) and values aren't specific, the fuzzer may find it. But if the sequence is 3+ steps or requires very specific values, a shortcut is recommended.
- The reachability report will be used by Phase 1 to inform CANARY/DOOM property design and by post-echidna coverage analysis.
- The protocol characteristics section (including PROTOCOL_TYPE from Step 4d) will be used by Phase 1A (multi-actor, time-based, protocol-specific templates) and Phase 1B (cross-contract, impossible states) to generate targeted properties.
- The economic oracles analysis (Step 6) will be used by Phase 1A to generate economic vulnerability properties.
- The data-flow taint analysis (Step 7) will be used by Phase 1A to modulate property density per function based on exploitability classification.
- The function transition graph (Step 8) will be used by the full-audit pipeline for pre-fuzzing sequence analysis and by coverage iteration for dead-cycle analysis.
- The setup wiring analysis (Step 5) will be used by Phase 3A to fix Setup.sol before implementing properties.
- You MUST NOT modify source contracts under `src/`. Only modify files under `test/recon/`.
- You MUST NOT modify Properties*.sol or BeforeAfter.sol — those are for later phases.
