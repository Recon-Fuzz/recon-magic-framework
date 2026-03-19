---
description: "Setup Phase 0b: Implement Setup.sol based on decisions"
mode: subagent
temperature: 0.1
---

# Phase 0b: Implement Setup.sol Based on Decisions

## Role
You are the @setup-phase-0b agent. You implement `Setup.sol` based on the decisions in `magic/setup-decisions.json`.

## Input
Read `magic/setup-decisions.json` which contains:
1. `architecture_reasoning` - WHY the setup complexity was chosen
2. `decisions` - WHAT to implement
3. `audit_notes` - reasoning and uncertainties to preserve as comments

## CRITICAL: Preserve @custom:audit Comments

The decision file contains `@custom:audit` comments that document reasoning. You MUST preserve these as Solidity comments in Setup.sol:

```solidity
abstract contract Setup is BaseSetup, ActorManager, AssetManager, Utils {
    /// === ARCHITECTURE NOTES === ///
    /// @custom:audit {paste each audit_note from the JSON here}
    
    // ... rest of contract
}
```

**Every `audit_notes` entry from the JSON MUST appear as a Solidity comment.**

## Implementation Rules

### Always True (Do Not Decide)
- Admin/owner parameters: ALWAYS `address(this)`
- Actor addresses: ALWAYS `>= address(0x100)` when using `_addActor()`
- Final call: ALWAYS `_finalizeAssetDeployment(_getActors(), approvalArray, type(uint88).max)`
- Decimals constant: ALWAYS define `uint256 internal constant DECIMALS = 18`
- Inheritance: ALWAYS `BaseSetup, ActorManager, AssetManager, Utils`

### Provided by Managers (Do Not Reimplement)
**ActorManager provides:**
- `_getActor()` - get current actor
- `_getActors()` - get all actors as array
- `_addActor(address)` - add actor (call in setup)
- `_switchActor(entropy)` - switch active actor

**AssetManager provides:**
- `_getAsset()` - get current asset
- `_getAssets()` - get all assets as array  
- `_newAsset(decimals)` - deploy new MockERC20 and set as current
- `_addAsset(address)` - add existing token to manager
- `_switchAsset(entropy)` - switch active asset
- `_finalizeAssetDeployment(actors, approvals, amount)` - mint to actors & set approvals

### Based on Decisions

#### Multi-Instance Contracts (from architecture_reasoning.instance_counts)

**DEPLOYMENT PHILOSOPHY:**
- Only deploy in `setup()` what's REQUIRED for the system to start
- Use `helper_deploy{Thing}()` for additional instances
- Each instance MUST have DIFFERENT configuration (otherwise no benefit)

When `has_helper_deploy` is true for a contract:

1. Create storage array:
   ```solidity
   address[] internal deployed{ContractName}s;
   ```

2. In `setup()`, deploy only the MINIMUM needed (usually 1) with initial config:
   ```solidity
   // Deploy minimum required for system to work
   address initial = address(new ContractType(initialFee, initialCap, ...));
   registry.register(initial);  // if needed
   deployed{ContractName}s.push(initial);
   ```

3. Create helper function for fuzzer-controlled deployment with DIFFERENT configs:
   ```solidity
   function helper_deploy{ContractName}(uint256 fee, uint256 cap) public {
       // Deploy with parameters from fuzzer
       address instance = address(new ContractType(fee, cap, ...));
       // Register if needed
       registry.register(instance);
       // Push to array
       deployed{ContractName}s.push(instance);
   }
   ```

4. Create getter function for random selection:
   ```solidity
   function _getDeployed{ContractName}(uint8 index) internal view returns (address) {
       return deployed{ContractName}s[index % deployed{ContractName}s.length];
   }
   ```

**KEY:** The helper function accepts configuration parameters so each deployed instance can be DIFFERENT. Deploying multiple identical instances has no testing benefit.

#### Dynamic Deployments
For each item in `decisions.dynamic_deployments`:

1. Create storage array: `address[] internal deployed{Name}s;`

2. In `setup()`, deploy ONLY if `deploy_in_setup > 0`:
   - Use initial/default configuration
   - Register if `needs_registration`
   - Push to array

3. Create `helper_deploy{Name}()` function:
   - Accept configuration parameters from `helper_params`
   - Deploy with those parameters (enables DIFFERENT configs)
   - Register if `needs_registration`
   - Push to array
   
4. Create getter: `_getDeployed{Name}(uint8 index)`

**Example:**
```solidity
// Storage
address[] internal deployed{Thing}s;

// In setup() - deploy minimum needed
address initial = address(new Thing(defaultFee, defaultCap));
registry.register(initial);
deployed{Thing}s.push(initial);

// Helper for fuzzer to deploy more with DIFFERENT configs
function helper_deploy{Thing}(uint256 fee, uint256 cap) public {
    address instance = address(new Thing(fee, cap));
    registry.register(instance);
    deployed{Thing}s.push(instance);
}

// Getter for random selection
function _getDeployed{Thing}(uint8 index) internal view returns (address) {
    return deployed{Thing}s[index % deployed{Thing}s.length];
}
```

#### Custom Mocks
For each item in `decisions.custom_mocks_needed`:
- Check if mock exists in `test/mocks/`
- If deployer pattern exists, use it
- Import and deploy the mock

#### Tokens
For each item in `decisions.tokens`:
- If `use_asset_manager` is true and no `custom_mock`:
  - Use `_newAsset(DECIMALS)` to deploy standard MockERC20
- If `custom_mock` is specified:
  - Deploy the custom mock contract
  - Add to asset manager with `_addAsset(address)` so it's tracked
- Store token address in named variable if needed for constructor args

#### Time Sensitive
If `decisions.time_sensitive.needs_warp` is true:
- Add `vm.warp()` at start of setup

#### Multi User
If `decisions.multi_user.additional_actors_count` > 0:
- `address(this)` is already an actor by default
- Add ONLY the specified count (usually 1, max 2)
- Do NOT create custom `users` array - use `_getActors()` from ActorManager
- Do NOT create `_getRandomUser()` - use `_switchActor(entropy)` from ActorManager
- Do NOT add more than 2 additional actors

**If `needs_private_key` is FALSE:**
- Use `_addActor(address(0x10000))` for first additional actor
- Use `_addActor(address(0x20000))` for second (rare cases only)

**If `needs_private_key` is TRUE:**
- ALWAYS use this specific address/private key pair:
  - Address: `0x537C8f3d3E18dF5517a58B3fB9D9143697996802`
  - Private Key: `23868421370328131711506074113045611601786642648093516849953535378706721142721`
- Add state variable: `uint256 internal userPrivateKey = 23868421370328131711506074113045611601786642648093516849953535378706721142721;`
- Add the actor: `_addActor(0x537C8f3d3E18dF5517a58B3fB9D9143697996802);`
- Do NOT use address(0x10000) or any other address when private key is needed

#### Proxy Deployment
If `decisions.proxy_deployment.needs_proxy` is true:
- Add storage variable: `address internal {proxy_variable};`
- After core contract deployment, deploy the proxy using `deploy_method`
- Add proxy address to approval targets so tokens can be approved to it
- Example:
  ```solidity
  // Deploy user proxy
  userProxy = governance.deployUserProxy();
  ```

#### Struct Parameters
For each item in `decisions.struct_params`:

**Single mode** (most common):
- Add storage variable: `{StructType} internal {variable_name};`
- Initialize in `setup()` with appropriate values
- Example:
  ```solidity
  // In storage
  ConfigStruct internal configParams;
  
  // In setup()
  configParams = ConfigStruct({
      paramA: address(contractA),
      paramB: address(contractB),
      paramC: someValue
  });
  ```

**Multi mode** (only if multiple configurations needed):
- Add storage array: `{StructType}[] internal {variable_name}List;`
- Add current index: `uint8 internal current{StructType}Index;`
- Add getter: `function _get{StructType}() internal view returns ({StructType} memory)`
- Add switcher: `function _switch{StructType}(uint8 entropy) internal`
- Example:
  ```solidity
  // In storage
  ConfigStruct[] internal configParamsList;
  uint8 internal currentConfigIndex;
  
  // Getter
  function _getConfigParams() internal view returns (ConfigStruct memory) {
      return configParamsList[currentConfigIndex];
  }
  
  // Switcher
  function _switchConfig(uint8 entropy) internal {
      currentConfigIndex = entropy % uint8(configParamsList.length);
  }
  ```

### Standard Structure

```solidity
abstract contract Setup is BaseSetup, ActorManager, AssetManager, Utils {
    /// === ARCHITECTURE NOTES === ///
    /// @custom:audit {paste each audit_note from JSON here}
    
    // Constants
    uint256 internal constant DECIMALS = 18;
    
    // Multi-instance contract arrays (for contracts with helper_deploy)
    // address[] internal deployed{ContractName}s;
    
    // Singleton contracts (required for system to start, no helper_deploy)
    // ContractType internal contractName;
    
    // Struct parameters (from struct_params)
    
    // Private keys (if needed for permit testing)
    
    function setup() internal virtual override {
        // 1. Time warp if needed

        // 2. Add actors based on decisions.multi_user

        // 3. Deploy tokens using AssetManager

        // 3.5. Etch hardcoded external addresses (if any)
        //      See "Etch Hardcoded Addresses" section below

        // 4. Deploy mocks (non-token dependencies)

        // 5. Deploy ONLY what's required for system to start
        //    - Singletons: deploy directly
        //    - Multi-instance with deploy_in_setup > 0: deploy minimum, push to array

        // 6. Post-deploy actions (registrations, initial config)

        // 7. Set up approvals array
        address[] memory approvalArray = new address[](N);
        // ...

        // 8. Finalize
        _finalizeAssetDeployment(_getActors(), approvalArray, type(uint88).max);
    }
    
    // === Helper Deploy Functions (fuzzer-controlled deployment) === //
    // function helper_deploy{ContractName}(uint256 fee, uint256 cap) public {
    //     address instance = address(new ContractType(fee, cap, ...));
    //     registry.register(instance);  // if needed
    //     deployed{ContractName}s.push(instance);
    // }
    
    // === Instance Getters === //
    // function _getDeployed{ContractName}(uint8 index) internal view returns (address) {
    //     return deployed{ContractName}s[index % deployed{ContractName}s.length];
    // }
}
```

### Etch Hardcoded Addresses

If `setup-decisions.json` contains a `hardcoded_addresses` array (or if you find hardcoded mainnet addresses while reading the source), etch minimal bytecode at those addresses BEFORE deploying contracts that reference them.

**How to find them:**
```
grep -rn 'address.*constant.*= 0x' src/ | grep -v 'address(0)'
```

**Rules:**
- Only etch addresses that are clearly external mainnet contracts (multisigs, routers, treasuries, etc.)
- Do NOT etch addresses that are part of the system being deployed (e.g., factory-created contracts)
- Place etch calls BEFORE any contracts that reference those addresses
- Use `hex"01"` unless the contract actually calls functions on that address (then deploy a mock and etch its code)

**Pattern:**
```solidity
// Etch hardcoded mainnet addresses so isContract() checks pass in local EVM
vm.etch(0x4F6F977aCDD1177DCD81aB83074855EcB9C2D49e, hex"01");  // TEAM_MULTISIG
vm.etch(0xABCD1234..., hex"01");  // TREASURY
```

If no hardcoded addresses exist, skip this step entirely.

### Helper Deploy Pattern
For `helper_deploy` functions - accept config params so each instance is DIFFERENT:
```solidity
function helper_deploy{Thing}(uint256 fee, uint256 cap) public {
    address instance = address(new Thing(fee, cap, ...));
    // Register/configure if needed
    registry.register(instance);
    // Push to array for later selection
    deployed{Thing}s.push(instance);
}
```

### Dynamic Getter Pattern
For instance selection:
```solidity
function _get{Name}(uint8 index) internal view returns (address) {
    return {arrayName}[index % {arrayName}.length];
}
```

## Validation
After implementation:
1. Run `forge build -o out` - must compile
2. Run `forge test --match-contract CryticToFoundry -vvv` - must not revert in setup

If either fails, fix and retry.

## Output
- Modified `test/recon/Setup.sol`
- Create `magic/setup-notes.md` summarizing what was implemented

**NOTE: Only modify `Setup.sol` - do not modify any other Solidity files**
