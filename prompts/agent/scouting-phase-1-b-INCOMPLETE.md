# Stateful Fuzzing Campaign Handwavy Deployment Config Generator

## Input

I have this contract data structure at `magic/recon-dictionary.json`

## Task

Generate a stateful fuzzing campaign specification with coverage class analysis at `magic/stateful-fuzzing-spec.json`

---

## Step 1: Exploration

Before generating any output, explore the codebase:

### Source Files
- Read `src/` files to understand contract relationships
- Find interface definitions in `src/**/interfaces/*.sol`
- Identify struct definitions used in constructors and configuration
- Search for role/constant definitions (e.g., `uint64 constant`, `bytes32 constant`)

### Test Files
- Read `test/` or `tests/` directories
- Find existing mock implementations
- Extract default config values from test setup/helpers

### Coverage Analysis
For each configuration parameter, search for:
- `if` statements that check the parameter
- `require` / `revert` statements gated by the parameter
- Modifier checks
- Boundary comparisons (`<`, `>`, `==`, `!=`)

---

## Step 2: Filter Contracts

### REMOVE (mocked: true)
- OpenZeppelin dependencies
- Proxy infrastructure
- External dependencies (WETH9, tokens, oracles)
- Utility traits/libraries

### KEEP (mocked: false)
- Core protocol contracts that are deployed
- Contracts with meaningful state and configuration

---

## Step 3: Source Types

| Source | When to Use |
|--------|-------------|
| `Actor` | Any user address from the actor pool (unprivileged) |
| `Admin` | Privileged address (owner, admin, configurator) |
| `Asset` | Token/asset - created via `_newAsset(decimals)` |
| `Contract` | Another protocol contract in the list |
| `Dictionary` | Protocol constants, structs, roles, or fixed values |
| `UNABLE` | Cannot be resolved - requires external data |

---

## Step 4: Coverage Classes

A **Coverage Class** is a distinct code path unlocked by a specific parameter value.

For each configuration parameter:
1. Find all code locations that check this parameter
2. Identify distinct branches/paths each value enables
3. Select values that maximize coverage

### Boolean Parameters
```json
"paused": {
  "source": "Dictionary",
  "coverage_classes": [
    { "value": false, "unlocks": "Normal operation path" },
    { "value": true, "unlocks": "Reverts with Paused() error" }
  ],
  "recommended": false,
  "reason": "false enables all operations; true only tests revert path"
}
```

### Numeric Parameters - Thresholds
```json
"collateralFactor": {
  "source": "Dictionary",
  "coverage_classes": [
    { "value": 0, "unlocks": "Reserve not counted as collateral" },
    { "value": 8000, "unlocks": "Normal collateral contribution (80%)" },
    { "value": 9999, "unlocks": "Edge case near max" }
  ],
  "recommended": 8000,
  "reason": "Enables collateral path; 0 disables feature entirely"
}
```

### Numeric Parameters - Caps
```json
"addCap": {
  "source": "Dictionary",
  "coverage_classes": [
    { "value": 0, "unlocks": "Blocks all supply, cap exceeded" },
    { "value": "1e18", "unlocks": "Limited supply, cap enforced" },
    { "value": "type(uint128).max", "unlocks": "Unlimited supply, cap bypassed" }
  ],
  "recommended": "type(uint128).max",
  "reason": "Unlimited enables operations; limited tests cap enforcement"
}
```

### Address Parameters
```json
"authority_": {
  "source": "Contract",
  "value": "AccessManagerEnumerable",
  "coverage_classes": [
    { "value": "address(0)", "unlocks": "Reverts or disables access control" },
    { "value": "valid", "unlocks": "Access control enforced" }
  ],
  "recommended": "AccessManagerEnumerable",
  "reason": "Valid address required for restricted functions"
}
```

---

## Step 5: Configuration Output Format

For each parameter in configuration:

### Address - Admin
```json
"owner_": {
  "source": "Admin"
}
```

### Address - Actor
```json
"user_": {
  "source": "Actor"
}
```

### Address - Asset
```json
"underlying_": {
  "decimals": 18,
  "source": "Asset"
}
```

### Address - Contract
```json
"hub_": {
  "value": "Hub",
  "source": "Contract"
}
```

### Value with Coverage Analysis
```json
"paused": {
  "source": "Dictionary",
  "coverage_classes": [
    { "value": false, "unlocks": "All operations allowed" },
    { "value": true, "unlocks": "ReservePaused() revert" }
  ],
  "recommended": false,
  "reason": "Enables full operation coverage"
}
```

### Unable to Resolve
```json
"externalOracle_": {
  "source": "UNABLE",
  "reason": "Requires mainnet oracle address"
}
```

---

## Step 6: Relations

| Relation | Meaning |
|----------|---------|
| `ONE_TO_ONE` | Exactly one instance references exactly one other |
| `ONE_TO_MANY` | One instance references multiple others |
| `MANY_TO_MANY` | Multiple instances reference multiple others |

---

## Output Format

```json
{
  "dictionary": {
    "Roles": {
      "ADMIN_ROLE": 0,
      "CONFIGURATOR_ROLE": 1
    },
    "Constants": {
      "PERCENTAGE_FACTOR": 10000,
      "MAX_CAP": "type(uint128).max"
    }
  },

  "contracts": {
    "ContractName": {
      "mocked": false,
      "relations": {
        "OtherContract": "ONE_TO_ONE"
      },
      "configuration": {
        "owner_": {
          "source": "Admin"
        },
        "hub_": {
          "value": "Hub",
          "source": "Contract"
        },
        "underlying_": {
          "decimals": 18,
          "source": "Asset"
        },
        "paused": {
          "source": "Dictionary",
          "coverage_classes": [
            { "value": false, "unlocks": "Normal operations" },
            { "value": true, "unlocks": "Paused revert path" }
          ],
          "recommended": false,
          "reason": "Enables all operation paths"
        },
        "cap": {
          "source": "Dictionary",
          "coverage_classes": [
            { "value": 0, "unlocks": "Cap exceeded revert" },
            { "value": "1e18", "unlocks": "Cap enforcement logic" },
            { "value": "type(uint128).max", "unlocks": "Cap bypass" }
          ],
          "recommended": "type(uint128).max",
          "reason": "Unlimited allows operations; can fuzz cap separately"
        }
      }
    },

    "MockedContract": {
      "mocked": true,
      "relations": {},
      "configuration": {}
    }
  }
}
```

---

## Coverage Class Patterns

### Boolean Flags
| Pattern | Values | Coverage |
|---------|--------|----------|
| Gate (blocks action) | `false` | Normal path |
| | `true` | Revert path |
| **Recommend**: `false` unless testing reverts |

### Percentage/BPS Values
| Pattern | Values | Coverage |
|---------|--------|----------|
| Zero | `0` | Feature disabled |
| Normal | `1` - `9999` | Feature active, calculations |
| Max | `10000` | Edge case, 100% |
| **Recommend**: Mid-range (e.g., `8000`) for normal operation |

### Cap Values
| Pattern | Values | Coverage |
|---------|--------|----------|
| Zero | `0` | All operations blocked |
| Limited | `1e18` | Cap enforcement checked |
| Unlimited | `type(uint).max` | Cap bypassed |
| **Recommend**: `type(uint).max` for operation coverage |

### Address Values
| Pattern | Values | Coverage |
|---------|--------|----------|
| Zero | `address(0)` | Validation revert or disabled |
| Valid | `deployed contract` | Normal operation |
| **Recommend**: Valid address for operation coverage |

---

## Rules

1. **Every contract** from input must appear in output
2. **Every constructor parameter** must be in configuration
3. **Every state variable** from input must be in configuration
4. **coverage_classes** required for Dictionary source with meaningful branches
5. **recommended** value must maximize operation coverage (not revert coverage)
6. **reason** explains why recommended value was chosen
7. **Admin** = privileged, **Actor** = unprivileged
8. **Asset** only needs `decimals`
9. **Contract** needs `value` with exact contract name
10. **mocked: true** contracts have empty relations and configuration

---

## Checklist

- [ ] All input contracts are in output
- [ ] All constructor params have configuration entries
- [ ] All state variables have configuration entries
- [ ] Every configuration has a valid source
- [ ] Dictionary values have coverage_classes analysis
- [ ] Each coverage_class has value + unlocks description
- [ ] recommended value maximizes operational coverage
- [ ] reason explains the recommendation
- [ ] Relations only reference other contracts in the list
- [ ] Mocked contracts are dependencies/externals
