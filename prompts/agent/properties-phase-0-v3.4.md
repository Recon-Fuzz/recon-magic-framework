---
description: "Phase 0 of the Efficient Properties Workflow v3.4. Performs dependency analysis, review prioritization, and reachability analysis for hard-to-reach branches."
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
3. **Multi-contract accounting**: Parent contract delegates funds to child contracts (vault→strategy, pool→market)
4. **Approval dependencies**: Protocol requires token approvals that could be revoked

For each cross-contract pair, note:
- Which internal variable tracks the external state
- Whether the values should be equal, or one should bound the other (≤ or ≥)
- How stale the external value can become

---

## Important Notes

- This analysis is based on **static review** of the source code. It identifies branches that LIKELY need special handling.
- Not every MULTI-STEP branch needs a shortcut — if the sequence is short (1-2 steps) and values aren't specific, the fuzzer may find it. But if the sequence is 3+ steps or requires very specific values, a shortcut is recommended.
- The reachability report will be used by Phase 1 to inform CANARY/DOOM property design and by post-echidna coverage analysis.
- The protocol characteristics section will be used by Phase 1A (multi-actor, time-based) and Phase 1B (cross-contract, impossible states) to generate targeted properties.
- You MUST NOT modify source contracts under `src/`. Only modify files under `test/recon/`.
- You MUST NOT modify Properties*.sol or BeforeAfter.sol — those are for later phases.
