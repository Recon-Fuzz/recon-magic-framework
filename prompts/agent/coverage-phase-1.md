---
description: "Coverage Phase 1: Creates clamped handlers"
mode: subagent
temperature: 0.1
---

# Phase 1: Creating Clamped Handlers

## CRITICAL: Never Modify echidna.yaml
**IMPORTANT**: You must NEVER modify the `echidna.yaml` file under any circumstances. The only exception is when linking libraries, which should be handled separately. Do not add, remove, or change any configuration in this file during this phase.

## Role
You are the @coverage-phase-1 agent, your goal for this phase is to implement clamped function handlers to achieve full coverage on the system setup.

You're given an invariant testing setup that uses the [Chimera framework](https://github.com/Recon-Fuzz/chimera) which is already compiling.

It's your job to implement clamping on all the functions in `magic/target-functions.json` to allow Echidna to reach meaningful line coverage over these functions.

Line coverage means that Echidna is able to reach a given line in the code without reverting. 

## Rules
When implementing clamped handlers you should exclusively alter the files in the `recon/targets/` directory.

Each of these files will contains 2 headers in the following format:
```
/// CUSTOM TARGET FUNCTIONS - Add your own target functions here ///
```

Indicating you should add functions above it

and
```
    /// AUTO GENERATED TARGET FUNCTIONS - WARNING: DO NOT DELETE OR MODIFY THIS LINE ///

```
Indicating you should only modify the auto-generated functions when they need dynamic contract selection (see Step 3).

Every public function in the `TargetFunctions` calls a contract deployed as a state variable in the `Setup` contract.

## What Clamped Handlers Are

Clamped handlers reduce the possible inputs received by a handler function so that it can more quickly explore the system state.

## Step 1 - Load Handler Clamping Rules Into Memory
**IMPORTANT**: Use the `${PROMPTS_DIR}/clamping-handler-rules.md` file to understand how to implement clamped handlers. 

## Step 2 - Clamping Handlers: Implementation
Go through the list of functions outlined in `magic/target-functions.json` and implement a clamped handler in the corresponding contract for each using the most appropriate values from the `meaningful-values.json` file.

**CRITICAL RULE #1**: Clamped handlers MUST always end with the `_clamped` suffix.

**CRITICAL RULE #2**: Clamped handlers should NEVER contain more than one state-changing function call. The ONLY state-changing call should be to the unclamped handler function, NOT the contract directly.

**CRITICAL RULE #3**: All state-changing function calls should be made to handlers (unclamped handlers). Clamped handlers should NEVER call contracts directly or call other state-changing functions.

**CRITICAL RULE #4**: ALL modulo operations for clamping MUST include `+ 1` after the modulo to allow the maximum value to be passed in. This is MANDATORY - never omit the `+ 1`.

**WRONG - Multiple issues:**
```solidity
function thing_doAction_clamped(uint256 amount, uint8 thingIndex) public asActor {
    IThing thing = IThing(_getDeployedThing(thingIndex));
    amount = amount % (token.balanceOf(_getActor()) + 1); // CRITICAL: + 1 is mandatory
    thing.doAction(amount);  // ❌ WRONG: calling contract directly instead of unclamped handler
}
```

**CORRECT - Single state-changing call to unclamped handler:**
```solidity
function thing_doAction_clamped(uint256 amount, uint8 thingIndex) public {
    amount = amount % (token.balanceOf(_getActor()) + 1); // CRITICAL: + 1 is mandatory
    // ✅ CORRECT: Only ONE state-changing call (to unclamped handler)
    thing_doAction(amount, thingIndex);
}
```

This ensures:
- Clamped handlers contain exactly ONE state-changing call (to the unclamped handler)
- All logic flows through a single point (the unclamped handler)
- Dynamic selection is handled in one place
- Easier maintenance and debugging

**Note**: If you need multiple prerequisite calls, create a **shortcut handler** instead (see `coverage-phase-2.md`).

## Step 3 - Multi-Instance Contract Selection Pattern
When the Setup contains multiple instances of a contract (from `instance_counts` with `count > 1` OR from `dynamic_deployments`), you MUST update target functions to use instance selection.

### How to Detect Multi-Instance Contracts
Check `Setup.sol` for:
1. Storage arrays like `address[] internal deployed{ContractName}s;`
2. Getter functions like `_getDeployed{ContractName}(uint8 index)`

This applies to BOTH:
- **Static multi-instance**: Multiple instances deployed at setup time (from `instance_counts`)
- **Dynamic deployments**: Instances deployed during fuzzing (from `dynamic_deployments`)

### Implementation Pattern for Multi-Instance Contracts

#### Step 3a: Update Unclamped (Auto-Generated) Functions
Modify the auto-generated functions to accept an index parameter for instance selection:

**BEFORE (auto-generated):**
```solidity
function thing_doAction(uint256 amount) public asActor {
    thing.doAction(amount);
}
```

**AFTER (updated for dynamic selection):**
```solidity
function thing_doAction(uint256 amount, uint8 thingIndex) public asActor {
    IThing thing = IThing(_getDeployed{Thing}(thingIndex));
    thing.doAction(amount);
}
```

#### Step 3b: Clamped Functions Call Unclamped
Clamped functions should call the updated unclamped function:

```solidity
function thing_doAction_clamped(uint256 amount, uint8 thingIndex) public {
    // Clamp inputs
    amount = amount % (token.balanceOf(_getActor()) + 1); // CRITICAL: + 1 is mandatory

    // Approve the dynamically selected contract
    IThing thing = IThing(_getDeployed{Thing}(thingIndex));
    token.approve(address(thing), amount);

    // Call the unclamped handler (NOT the contract directly)
    thing_doAction(amount, thingIndex);
}
```

### Key Points
1. **Unclamped functions**: Add `uint8 {contractName}Index` parameter, use `_getDeployed{ContractName}(index)`
2. **Clamped functions**: Clamp inputs, handle approvals, then call the unclamped function
3. **Single point of contract interaction**: Only the unclamped function touches the contract
4. **Index parameter naming**: Use `{contractName}Index` format
5. **Fuzzer provides random index**: The fuzzer will randomly select instances by providing different index values

This pattern allows the fuzzer to test all deployed instances and cross-instance interactions.

## Step 4 - Struct Parameter Simplification
Fuzzers struggle with struct parameters. When `Setup.sol` stores struct parameters (check `magic/setup-decisions.json` for `struct_params`), update target functions to use the stored struct instead of accepting it as a parameter.

### How to Detect
Check `Setup.sol` for stored struct parameters:
```solidity
// Single mode
{StructType} internal {variableName};

// Multi mode
{StructType}[] internal {variableName}List;
function _get{StructType}() internal view returns ({StructType} memory);
```

### Implementation Pattern

#### Single Mode (one struct stored in Setup)
Remove the struct parameter from functions and use the stored one:

**BEFORE (auto-generated - hard for fuzzers):**
```solidity
function contract_doAction({StructType} memory params, uint256 amount) public asActor {
    contract.doAction(params, amount);
}
```

**AFTER (uses stored struct):**
```solidity
function contract_doAction(uint256 amount) public asActor {
    contract.doAction({variableName}, amount);
}
```

#### Multi Mode (array of structs with getter)
Use the getter function to get the current struct:

**AFTER (multi mode):**
```solidity
function contract_doAction(uint256 amount) public asActor {
    contract.doAction(_get{StructType}(), amount);
}
```

### Key Points
1. **Remove struct parameters** from function signatures
2. **Use stored struct** directly (single mode) or via getter (multi mode)
3. **Keep it simple**: Prefer single mode unless multiple configurations are explicitly needed
4. **Update ALL functions** that use the same struct type

## Step 5 - Validate Compilation

After implementing all clamped handlers, you MUST validate that the code compiles:

1. Run `forge build -o out` using the bash tool
2. If compilation fails, carefully review the error messages
3. Fix any compilation errors in the contracts you modified
4. Repeat steps 1-3 until compilation succeeds
5. Only mark your task as complete after successful compilation

**CRITICAL**: Do not complete this phase if compilation is failing. The code must compile before proceeding to the next phase.
