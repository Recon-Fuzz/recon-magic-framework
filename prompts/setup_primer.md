# Claude Setup Primer: Chimera Framework Test Suite Setup

## Overview
The objective of this phase is to create a realistic setup that allows all targeted contracts to be called successfully.

### Files to Modify
- `Setup.sol`

**No other contracts should be modified**

## Core Architecture Components

### 1. Setup Contract
- **Purpose**: Deploys and initializes target contracts before fuzzing begins
- **Key Role**: Serves as the deployer for all contracts used in fuzzing

## Setup Contract Best Practices

### Initial Assessment
Before modifying the existing Setup.sol contract, agents should:

1. **Review Existing Setup.sol**: 
   - The project's existing `Setup.sol` contract will only have deployed contracts (**target contracts**) for which there are corresponding target function handlers in `TargetFunctions` or inherited by `TargetFunctions`

2. **Review Existing Tests**: Examine the project's existing test suite outside the `/recon` folder to understand:
   - What parameters are typically used in contract deployment/initialization
   - Common initialization patterns
   - **Use of proxies in deployments**

4. **Understand Dependencies**: Map out contract relationships and initialization order

### Token and Actor Configuration
Agents should:
- **Determine Token Count**: Analyze the contract to determine a logical number of tokens to deploy using the `_newAsset()` function. If this cannot be determined default to deploying a single token.
- **Decimal Precision**: Deployed tokens should default to 18 decimals
- **Actor Management**: Add a default of 2 actors using the `_addActor()` function
- **Automatic Distribution**: Use `_finalizeAssetDeployment()` to mint tokens to actors at the end of the `setup()` function

### Setup Structure Example

Modify the existing Setup.sol contract to follow this pattern:

```solidity

abstract contract Setup is BaseSetup, ActorManager, AssetManager {
    // Configuration constants
    uint256 internal constant DECIMALS = 18;
    
    function setup() internal virtual override {
      // 1. Add additional actors
      _addActor(address(0x100)); // Actor 1
      _addActor(address(0x200)); // Actor 2

      // 2. Create assets using AssetManager
      _newAsset(DECIMALS); // Deploy token with specified decimals
      
      // 3. Deploy core contracts
      counter = new Counter();

      // 4. Configure/Initialize core contracts
      myContract.setToken(_getAsset());
      // set authorizations
      myContract.rely(_getAsset());
      
      // 4. Set up approval array for contracts that need token access
      address[] memory approvalArray = new address[](1);
      approvalArray[0] = address(myContract);
      
      // 5. Finalize asset deployment (mints to actors and sets approvals)
      _finalizeAssetDeployment(_getActors(), approvalArray, type(uint88).max);
   }
}
```

NOTE: 
- always pass `type(uint88).max` as the last parameter to `_finalizeAssetDeployment`
- always use addresses >= `address(0x100)` for actor setups

#### Transparent Upgradeable Proxy Example

When deploying contracts with upgradeable proxies:

```solidity
abstract contract Setup is BaseSetup, ActorManager, AssetManager {
    // Configuration constants
    uint256 internal constant DECIMALS = 18;
    
    Counter counter;
    TransparentUpgradeableProxy counterProxy;
    
    function setup() internal virtual override {
        // 1. Add additional actors
        _addActor(address(0x100)); // Actor 1
        _addActor(address(0x200)); // Actor 2

        // 2. Create assets using AssetManager
        _newAsset(DECIMALS); // Deploy token with specified decimals
        
        // 3. Deploy implementation contract
        Counter counterImpl = new Counter();

        // 4. Deploy transparent upgradeable proxy with address(this) as admin
        counterProxy = new TransparentUpgradeableProxy(
            address(counterImpl),
            address(this), // proxy admin
            ""
        );
        
        // 5. Initialize proxy contract
        counter = Counter(address(counterProxy));
        counter.initialize(_getAsset());
        
        // 6. Set up approval array for contracts that need token access
        address[] memory approvalArray = new address[](1);
        approvalArray[0] = address(counter);
        
        // 7. Finalize asset deployment (mints to actors and sets approvals)
        _finalizeAssetDeployment(_getActors(), approvalArray, type(uint88).max);
    }
}
```

### Key Implementation Guidelines

#### 1. Admin Actor Configuration
- **Configuration Parameters**: Any constructor/intialization arguments named `owner`, `admin` or similar should receive the `address(this)` actor as a parameter

#### 2. Configuration Parameter Documentation
- **Inline Comments**: Add comments highlighting parameters that are set in constructor or initialization function but also can be modified by target function handlers
- **Differentiate Parameters**: Distinguish between:
  - Construction/initialization-only parameters
  - Runtime-configurable parameters accessible via target functions
- **Example Comment Format**: `// CONFIGURABLE: This parameter can be modified via setParameter() target function`

## Compilation and Validation

### Compilation Requirements
Agents MUST:
1. **Compile All Contracts**: Ensure the entire test suite compiles successfully
2. **Error Handling**: Address compilation errors systematically

#### Success Criteria
1. Running `forge build` logs the compiled successfully message
2. Running the `forge test --match-contract CryticToFoundry -vvv` should also succeed
   - If this command fails with a revert in the `setup` function, the agent should identify the source of the issue and modify the `setup` function until the command no longer causes a revert. 

**This phase is only complete is success criteria 1 and 2 are met**
