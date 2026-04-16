---
description: "Scout V2 Phase 2: Deep parameter analysis for Setup configuration"
mode: subagent
temperature: 0.1
---

# Scout V2 Phase 2: Deep Parameter Analysis

## Role
You are the @scout-v2-phase-2 agent. Your job is to deeply analyze FULL and MOCK contracts to determine how they should be configured in Setup.sol. You do NOT write Solidity code.

## Input

1. Read `magic/scope.md` for testing context and goals (if it exists — it's optional)
2. Read `magic/deployment-classification.json` from Phase 0

## Task

For each FULL and MOCK contract:
1. Analyze constructor parameters
2. Identify configurable state variables
3. Determine parameter sources (Admin, Actor, Asset, Contract, Dictionary)
4. Analyze coverage classes for Dictionary values
5. Determine deployment order based on dependencies

## Output File

Create `magic/setup-config-spec.json`

---

## Step 1: Analyze Each FULL Contract

For each contract in FULL classification:

### 1.1 Constructor Parameters
Read the contract source and extract constructor signature:
```solidity
constructor(address owner_, address oracle_, uint256 fee_) { ... }
```

For each parameter, determine:
- **source**: Where the value comes from
- **value**: Specific value if known
- **coverage_classes**: If Dictionary source, what code paths different values unlock

### 1.2 Source Types

| Source | When to Use | Setup.sol Value |
|--------|-------------|-----------------|
| `Admin` | Owner, admin, governance addresses | `address(this)` |
| `Actor` | User addresses that interact with system | `_getActor()` |
| `Asset` | Token addresses | `_getAsset()` or `_newAsset(decimals)` |
| `Contract` | Another deployed contract | `address(deployedContract)` |
| `Dictionary` | Constants, fees, thresholds | Literal value |
| `UNABLE` | Cannot determine, needs user input | Mark for user |

### 1.3 Coverage Class Analysis

For Dictionary parameters, search the contract code for:
- `if` statements checking the parameter
- `require` statements gated by the parameter
- Threshold comparisons (`<`, `>`, `==`, `!=`)

Document what code paths each value unlocks:

```json
"fee_": {
  "source": "Dictionary",
  "coverage_classes": [
    { "value": 0, "unlocks": "Zero fee path, no fee collection" },
    { "value": 100, "unlocks": "Normal fee path (1%)" },
    { "value": 10000, "unlocks": "Max fee edge case (100%)" }
  ],
  "recommended": 100,
  "reason": "Non-zero enables fee collection without edge case issues"
}
```

---

## Step 2: Analyze Each MOCK Contract

For MOCK contracts, only analyze:
- Interface methods that SUT reads (from classification)
- State variables needed to implement those methods
- Setter functions needed to control mock state

```json
"OracleMock": {
  "classification": "MOCK",
  "interface": [
    {
      "method": "price()",
      "returns": "uint256",
      "stateVar": "_price",
      "setter": "setPrice(uint256)"
    }
  ],
  "initialValues": {
    "_price": {
      "source": "Dictionary",
      "recommended": "1e18",
      "reason": "Non-zero price for normal operation"
    }
  }
}
```

---

## Step 3: Determine Deployment Order

Build deployment order based on constructor dependencies:

1. Contracts with no Contract-type dependencies deploy first
2. Contracts depending on (1) deploy second
3. Continue until all contracts ordered
4. **If circular dependency detected** → apply resolution strategy

```json
"deploymentOrder": [
  { "order": 1, "contract": "OracleMock", "reason": "No dependencies" },
  { "order": 2, "contract": "Token", "reason": "No dependencies" },
  { "order": 3, "contract": "Vault", "reason": "Depends on Oracle, Token" }
]
```

---

## Step 3b: Resolve Circular Dependencies

### Detecting Circular Dependencies

A circular dependency exists when:
- Contract A constructor requires Contract B address
- Contract B constructor requires Contract A address

Example:
```solidity
contract Pool {
    constructor(address _router) { router = _router; }
}
contract Router {
    constructor(address _pool) { pool = _pool; }
}
```

### Resolution Strategies

When a cycle is detected, choose ONE strategy based on the contract patterns:

#### Strategy 1: Setter Pattern (Most Common)
**Use when:** Contract has a setter function for the dependency

```json
{
  "circular": ["Pool", "Router"],
  "strategy": "setter",
  "resolution": {
    "deployFirst": "Pool",
    "deploySecond": "Router",
    "constructorPlaceholder": {
      "Pool._router": "address(0)"
    },
    "postDeployLink": {
      "call": "Pool.setRouter(address(Router))",
      "reason": "Link Pool to Router after both deployed"
    }
  }
}
```

Implementation in Setup.sol:
```solidity
// Deploy with placeholder
pool = new Pool(address(0));
router = new Router(address(pool));
// Link after deployment
pool.setRouter(address(router));
```

#### Strategy 2: Initialization Pattern
**Use when:** Contract uses initialize() instead of constructor

```json
{
  "circular": ["VaultImpl", "ControllerImpl"],
  "strategy": "initialization",
  "resolution": {
    "deployFirst": "VaultImpl",
    "deploySecond": "ControllerImpl",
    "initializeOrder": [
      { "contract": "VaultImpl", "call": "initialize(address(ControllerImpl))" },
      { "contract": "ControllerImpl", "call": "initialize(address(VaultImpl))" }
    ]
  }
}
```

Implementation in Setup.sol:
```solidity
// Deploy implementations (no constructor deps)
vaultImpl = new VaultImpl();
controllerImpl = new ControllerImpl();
// Initialize with cross-references
vaultImpl.initialize(address(controllerImpl));
controllerImpl.initialize(address(vaultImpl));
```

#### Strategy 3: Factory/Registry Pattern
**Use when:** System uses a central registry that contracts query

```json
{
  "circular": ["LendingPool", "Oracle", "RiskManager"],
  "strategy": "registry",
  "resolution": {
    "deployFirst": "Registry",
    "deployOthers": ["LendingPool", "Oracle", "RiskManager"],
    "registration": [
      "Registry.setAddress('POOL', address(LendingPool))",
      "Registry.setAddress('ORACLE', address(Oracle))",
      "Registry.setAddress('RISK', address(RiskManager))"
    ],
    "note": "Contracts lookup addresses from Registry at runtime"
  }
}
```

Implementation in Setup.sol:
```solidity
// Deploy registry first
registry = new Registry();
// Deploy others with registry reference
lendingPool = new LendingPool(address(registry));
oracle = new Oracle(address(registry));
riskManager = new RiskManager(address(registry));
// Register addresses
registry.setAddress("POOL", address(lendingPool));
registry.setAddress("ORACLE", address(oracle));
registry.setAddress("RISK", address(riskManager));
```

#### Strategy 4: CREATE2 Precomputed Addresses
**Use when:** No setters available, addresses must be known at construction

```json
{
  "circular": ["TokenA", "TokenB"],
  "strategy": "create2",
  "resolution": {
    "precompute": {
      "TokenA": "computeAddress(salt_a, bytecode_a)",
      "TokenB": "computeAddress(salt_b, bytecode_b)"
    },
    "deployOrder": ["TokenA", "TokenB"],
    "note": "Use CREATE2 to deploy at precomputed addresses"
  }
}
```

Implementation in Setup.sol:
```solidity
// Precompute addresses
bytes32 saltA = keccak256("TokenA");
bytes32 saltB = keccak256("TokenB");
address precomputedA = computeCreate2Address(saltA, type(TokenA).creationCode);
address precomputedB = computeCreate2Address(saltB, type(TokenB).creationCode);

// Deploy with precomputed addresses
tokenA = new TokenA{salt: saltA}(precomputedB);
tokenB = new TokenB{salt: saltB}(precomputedA);
```

#### Strategy 5: Mock Breaker
**Use when:** One side of the cycle can be mocked for testing purposes

```json
{
  "circular": ["Core", "Periphery"],
  "strategy": "mock_breaker",
  "resolution": {
    "breakAt": "Periphery",
    "mockWith": "PeripheryMock",
    "reason": "Periphery only provides view functions to Core, can be mocked",
    "deployOrder": ["PeripheryMock", "Core"],
    "note": "Real Periphery not needed for Core testing"
  }
}
```

### Choosing a Strategy

| Condition | Recommended Strategy |
|-----------|---------------------|
| Contract has `setX()` function | **Setter** |
| Contract uses `initialize()` | **Initialization** |
| System has central registry | **Registry** |
| Must know address at construction, no setters | **CREATE2** |
| One contract not critical for SUT testing | **Mock Breaker** |

### Output Format for Circular Dependencies

Add to `setup-config-spec.json`:

```json
"circularDependencies": [
  {
    "cycle": ["Pool", "Router"],
    "detected": "Pool.constructor needs Router, Router.constructor needs Pool",
    "strategy": "setter",
    "resolution": {
      "deployFirst": "Pool",
      "constructorPlaceholder": { "Pool._router": "address(0)" },
      "postDeployLink": "pool.setRouter(address(router))"
    }
  }
]
```

---

## Step 4: Identify Post-Deploy Actions

Some contracts need configuration after deployment:
- `initialize()` calls for upgradeable contracts
- Role grants (`grantRole`, `rely`, `authorize`)
- Token approvals
- Registration with registries

```json
"postDeployActions": [
  {
    "contract": "Vault",
    "action": "initialize()",
    "params": [],
    "reason": "Upgradeable pattern requires initialization"
  },
  {
    "contract": "Vault",
    "action": "grantRole(MANAGER_ROLE, address(this))",
    "params": ["MANAGER_ROLE", "Admin"],
    "reason": "Test contract needs manager permissions"
  }
]
```

---

## Step 5: Actor and Asset Requirements

Analyze the system to determine:

### Actors
- How many distinct users does the system need?
- Do any functions require signatures (needs private key)?
- `address(this)` is already an actor by default — only count ADDITIONAL actors
- Most cases need 1 additional actor (total 2). Rarely 2 additional (3-party interactions). **NEVER** more than 2 additional

```json
"actors": {
  "count": 1,
  "needsPrivateKey": false,
  "reason": "System has depositor and liquidator roles"
}
```

**If permit/signature functionality is detected**, set `needsPrivateKey: true`. Setup will use a hardcoded key/address pair for deterministic signing.

### Assets
- What tokens does the system use?
- Do any need custom mocks (not standard ERC20)?
- If main tokens have a different implementation than standard `MockERC20`, flag `customMock`

```json
"assets": [
  {
    "name": "collateralToken",
    "decimals": 18,
    "role": "collateral",
    "customMock": null
  },
  {
    "name": "debtToken",
    "decimals": 6,
    "role": "debt",
    "customMock": null
  }
]
```

---

## Step 6: Time Sensitivity Detection

Search all FULL contracts for time-dependent logic:

**Look for:**
- `block.timestamp` usage
- Epoch/period-based logic
- Vesting, lockups, delays, cooldowns
- `require(block.timestamp > ...)` patterns

```json
"timeSensitive": {
  "detected": true,
  "reason": "Vault.withdraw() has a 7-day lockup period",
  "warpTo": 1_000_000
}
```

If no time-dependent logic found:
```json
"timeSensitive": {
  "detected": false
}
```

**NOTE:** `warpTo` should be a large enough value that time-gated logic can be tested. Default to `1_000_000` if specific value is unclear.

---

## Step 7: Struct Parameter Detection

Identify struct types that are passed as parameters to multiple handler functions. Fuzzers struggle to generate valid struct values, so these should be pre-built in Setup and reused.

**Look for:**
- Struct types passed to 2+ functions as parameters
- Complex structs with address/contract fields the fuzzer can't guess

For each struct, determine the mode:
- **single**: One configuration needed (most common) — store one struct in Setup
- **multi**: Multiple configurations must be tested — store array + getter + switcher

```json
"structParams": [
  {
    "structType": "MarketParams",
    "variableName": "defaultMarketParams",
    "mode": "single",
    "fields": {
      "loanToken": { "source": "Asset" },
      "collateralToken": { "source": "Asset" },
      "oracle": { "source": "Contract", "value": "OracleMock" },
      "irm": { "source": "Contract", "value": "IrmMock" },
      "lltv": { "source": "Dictionary", "recommended": "860000000000000000" }
    },
    "reason": "All vault functions take MarketParams — store in Setup for clamping"
  }
]
```

If no struct params detected, use empty array: `"structParams": []`

---

## Step 8: Dynamic Deployment Detection

Identify contracts where the fuzzer should control deployment of additional instances, rather than deploying everything in `setup()`.

**Deployment philosophy:**
- Only deploy in `setup()` what's REQUIRED for the system to start working
- Use `helper_deploy{Thing}()` for additional instances the fuzzer can create
- Each instance MUST have DIFFERENT configuration (identical instances have no testing benefit)

**When to flag a contract as dynamic:**

| Question | If YES → dynamic | If NO → static |
|----------|------------------|----------------|
| Can have multiple instances? | Flag it | Single instance only |
| Instances interact with each other? | Worth having multiple | One is enough |
| Different configs make sense? | Create varied configs | Same config = no benefit |
| System has a factory/registry for it? | Natural fit for helper | Deploy directly |

```json
"dynamicDeployments": [
  {
    "contract": "Market",
    "deployInSetup": 1,
    "hasHelperDeploy": true,
    "helperParams": ["loanToken", "collateralToken", "oracle", "irm", "lltv"],
    "needsRegistration": true,
    "registrationCall": "factory.createMarket(params)",
    "reason": "Protocol supports multiple markets with different configurations"
  }
]
```

If no dynamic deployments needed, use empty array: `"dynamicDeployments": []`

---

## Step 9: Proxy Deployment Detection

Identify if the system uses proxy patterns (upgradeable contracts or user proxies):

**Look for:**
- `TransparentUpgradeableProxy`, `ERC1967Proxy`, `UUPSUpgradeable`
- `UserProxy` or `deployUserProxy()` patterns
- `initialize()` instead of constructor logic
- OpenZeppelin `Initializable` inheritance

```json
"proxyDeployments": [
  {
    "implementation": "VaultImpl",
    "proxyType": "TransparentUpgradeableProxy",
    "initializeCall": "initialize(address(token), address(oracle))",
    "proxyAdmin": "Admin",
    "reason": "Vault uses upgradeable proxy pattern"
  }
]
```

If no proxies detected, use empty array: `"proxyDeployments": []`

---

## Output Format

Create `magic/setup-config-spec.json`:

```json
{
  "contracts": {
    "Vault": {
      "classification": "FULL",
      "path": "src/Vault.sol",
      "constructor": {
        "owner_": {
          "source": "Admin"
        },
        "oracle_": {
          "source": "Contract",
          "value": "OracleMock"
        },
        "fee_": {
          "source": "Dictionary",
          "coverage_classes": [
            { "value": 0, "unlocks": "Zero fee path" },
            { "value": 100, "unlocks": "Normal fee (1%)" }
          ],
          "recommended": 100,
          "reason": "Enables fee collection"
        }
      }
    },
    "OracleMock": {
      "classification": "MOCK",
      "interface": [
        {
          "method": "price()",
          "returns": "uint256",
          "stateVar": "_price",
          "setter": "setPrice(uint256)"
        }
      ],
      "initialValues": {
        "_price": {
          "recommended": "1e18",
          "reason": "Non-zero for normal operation"
        }
      }
    }
  },

  "deploymentOrder": [
    { "order": 1, "contract": "OracleMock" },
    { "order": 2, "contract": "Vault" }
  ],

  "circularDependencies": [
    {
      "cycle": ["Pool", "Router"],
      "strategy": "setter",
      "resolution": {
        "deployFirst": "Pool",
        "constructorPlaceholder": { "_router": "address(0)" },
        "postDeployLink": "pool.setRouter(address(router))"
      }
    }
  ],

  "postDeployActions": [
    {
      "contract": "Vault",
      "action": "initialize()",
      "reason": "Required for upgradeable"
    }
  ],

  "actors": {
    "count": 2,
    "needsPrivateKey": false,
    "reason": "Depositor and liquidator roles"
  },

  "assets": [
    {
      "name": "token",
      "decimals": 18,
      "role": "collateral",
      "customMock": null
    }
  ],

  "timeSensitive": {
    "detected": true,
    "reason": "Vault.withdraw() has 7-day lockup",
    "warpTo": 1000000
  },

  "structParams": [
    {
      "structType": "MarketParams",
      "variableName": "defaultMarketParams",
      "mode": "single",
      "fields": {
        "loanToken": { "source": "Asset" },
        "oracle": { "source": "Contract", "value": "OracleMock" },
        "lltv": { "source": "Dictionary", "recommended": "860000000000000000" }
      },
      "reason": "All vault functions take MarketParams"
    }
  ],

  "dynamicDeployments": [
    {
      "contract": "Market",
      "deployInSetup": 1,
      "hasHelperDeploy": true,
      "helperParams": ["loanToken", "oracle", "lltv"],
      "needsRegistration": true,
      "registrationCall": "factory.createMarket(params)",
      "reason": "Protocol supports multiple markets"
    }
  ],

  "proxyDeployments": [],

  "unable": [
    {
      "contract": "Vault",
      "parameter": "externalOracle_",
      "reason": "Requires mainnet oracle address - needs user input"
    }
  ]
}
```

---

## Validation Checklist

- [ ] Every FULL contract has constructor analysis
- [ ] Every MOCK contract has interface analysis
- [ ] Deployment order is valid (linear OR circular deps have resolution)
- [ ] All circular dependencies have a resolution strategy
- [ ] All Contract sources reference contracts that exist
- [ ] Dictionary values have coverage_classes where meaningful
- [ ] UNABLE parameters are clearly documented
- [ ] `timeSensitive` is set (detected true/false)
- [ ] Struct types passed to multiple functions are in `structParams`
- [ ] Contracts with factory/registry patterns checked for `dynamicDeployments`
- [ ] Proxy patterns detected and documented in `proxyDeployments`

---

## Output

1. Write `magic/setup-config-spec.json`
2. Report:
   - Contracts analyzed
   - Parameters with coverage classes
   - Any UNABLE parameters needing user input
   - Ready for Setup Phase

**STOP** after creating the file. Scout V2 is complete.
