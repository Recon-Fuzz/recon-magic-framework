## Style Guide

Always use AssetManager.sol for Assets

If you need to separate between collateral and debt, you can still use the AssetManager to deploy the tokens and toggle them, and then also store these hardcoded roles in storage.

Always use ActorManager.sol for Actors

address(this) can be used for privileged roles such as being the admin or the owner.

Other actors should be added

## CRITICAL: echidna.yaml Modification Policy

**IMPORTANT**: The `echidna.yaml` file must NEVER be modified except for one specific case:

**ONLY EXCEPTION**: Linking libraries with `external` or `public` functions

All coverage phase agents and setup agents must strictly avoid modifying `echidna.yaml` for any other purpose. Configuration changes, test mode adjustments, or any other modifications are strictly prohibited.

## How to Link Libraries

You will need to add Libraries with `external` or `public` functions to the `cryticArgs` and to the `deployedContracts` as follows:

Example echidna.yaml:
```yaml
... existing configs ...
cryticArgs: ["--foundry-compile-all", "--compile-libraries=(ActionHelper,0xf01),(LoanCalculator,0xf02)"]
deployContracts: [["0xf01", "ActionHelper"], ["0xf02", "LoanCalculator"]]
```

### How to Find ALL Libraries That Need Linking

  **CRITICAL**: When you encounter ANY library linking error, you must find and link ALL libraries in the
  codebase - not just the one mentioned in the error. Follow these steps:

  **Step 1: Search for all library declarations**
  Search the entire codebase for all Solidity library declarations. This includes:
  - The main source directories (`src/`, `contracts/`)
  - All dependencies in the `lib/` folder
  - Any other directories containing Solidity files

  Look for contracts declared with the `library` keyword (e.g., `library MathLib {`).

  **Step 2: Check each library for external or public functions**
  For each library found, examine its functions:
  - If a library contains ONLY `internal` functions → it does NOT need linking (these are inlined at compile
  time)
  - If a library contains ANY `external` or `public` function → it MUST be linked

  **Step 3: Add ALL matching libraries to echidna.yaml**
  Add every library that has external/public functions to both `cryticArgs` and `deployContracts`. Do not skip
  any. Do not try to determine if a library is "actually used" - if it has external/public functions, link it.

  **Step 4: Assign unique addresses**
  Each library needs a unique address:
  - First library: 0xf01
  - Second library: 0xf02
  - Third library: 0xf03
  - Continue incrementing for additional libraries

  **Common Mistake to Avoid**

  Do NOT only link the library mentioned in the error message. Echidna may only report one missing library at a time. You must proactively find and link ALL libraries with external/public functions to avoid repeated failures.


Example Medusa.json
```json
{
  ... existing configs ...

    "predeployedContracts": {
      "ActionHelper": "0xf01",
      "LoanCalculator": "0xf02"
    },
    ...... existing configs ...
  "compilation": {
    "platform": "crytic-compile",
    "platformConfig": {
      "target": ".",
      "solcVersion": "",
      "exportDirectory": "",
      "args": [
        "--compile-libraries=(ActionHelper,0xf01),(LoanCalculator,0xf02)", "--foundry-compile-all"
      ]
    }
  },
  "logging": {
    "level": "info",
    "logDirectory": ""
  }
}
```

## Echidna and Medusa compilation issues while foundry works

- Disable Dynamic Text Linking
`dynamic_test_linking = true` causes issues with the compilation for Echidna and Medusa

## Echidna compilation and running is slow

Please expect echidna to take multiple minutes to compile.

## AccessControl Role Fix

Make sure that every role in the system can be reached either via an Actor or a Contract

If you see reverts due to access control:
1. Identify the missing role hash in the contract
2. Determine caller: Actor, Contract, or Admin
3. Add role grant in Setup.sol:

```solidity
vm.prank(admin);
contractName.grantRole(contractName.ROLE_NAME(), appropriateAddress);
```

## Constructor

The constructor for Echidna and Medusa must be `payable`

## Echidna Default

A default echidna.yaml:

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

**Common patterns:**
- User functions → Grant to `_getActor()`
- System functions → Grant to system address (manager, allocatorService, etc.)
- Missing actor → `_addActor` with role in `setup()`
