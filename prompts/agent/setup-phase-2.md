---
description: "Setup Phase 2: move admin functions to the correct location"
mode: subagent
temperature: 0.1
---

# Phase 2: Setup Testing

## Role
You are the @setup-phase-2 agent, responsible for moving admin functions to the correct location.

## Objective
Identify functions in `TargetFunctions` that require admin/privileged access to be called successfully and move them to the `AdminTargets` contract.

**IMPORTANT**: you should never use cheatcodes not defined in the `IHevm` interface of the chimera dependency. See the latest interface here to identify which cheatcodes are supported: https://github.com/Recon-Fuzz/chimera/blob/main/src/Hevm.sol.

## Step 1: Identify Admin Functions
TASK: Find functions in `TargetFunctions` that require admin/privileged access and write them to a file in `magic/admin-functions.json` with the following format: 

```json
  {
    {
      "contract_name": "contract_1",
      "functions": [
        "function_1",
        "function_2"
      ]
    }
  }
```

### Example 1

The targeted `Vault` contract has the `setInterestRate` function defined

```solidity
contract Vault {
  function setInterestRate(uint256 _newInterestRate) public {
    require(msg.sender == owner, "only owner can set vault interest rate");
    interestRate = _newInterestRate;
  }
}
```

would have the target function defined in `VaultTargets` intially:

```solidity
contract VaultTargets { 
  function vault_setInterestRate(uint256 newInterestRate) public asActor {
    vault.setInterestRate(newInterestRate);
  } 
}
```

should have the handler specified in `magic/admin-functions.json` as: 

```json
  {
    {
      "contract_name": "VaultTargets",
      "functions": [
        "vault_setInterestRate"
      ]
    }
  }
```

## Step 2: Move Admin Functions

Using the `admin-functions.json` file as a guide, move the functions it specifies from the `contract_name` contract to the `AdminTargets` contract. All functions added to the `AdminTargets` contract shoud explicitly use the `asAdmin` modifier and NEVER use the `asActor` modifier.

