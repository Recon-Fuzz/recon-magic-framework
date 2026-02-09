# Stateful Fuzzing Campaign Deployment Configuration Generator

## Input

- Classification tables from Step 1 (FULL, MOCK, ABSORB, DISCARD) at: `magic/full-mock-absorb-spec.json`
- Contract data structure at `magic/recon-dictionary.json`

## Task

Generate deployment configuration for FULL and MOCK contracts at `magic/stateful-fuzzing-spec.json`

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

## Step 2: Process by Classification

### FULL Contracts
- Include all constructor parameters
- Include all configurable state variables
- Full coverage class analysis
- Full relations mapping

### MOCK Contracts
- Include only parameters that affect SUT's reads
- Minimal coverage classes (just what SUT observes)
- Relations only to FULL contracts

### ABSORB Contracts
- No configuration needed
- Output only the address/label for prank references

### DISCARD Contracts
- Omit entirely from output

---

## Step 3: Source Types

| Source | When to Use |
|--------|-------------|
| `Actor` | Any user address from the actor pool (unprivileged) |
| `Admin` | Privileged address (owner, admin, configurator) |
| `Asset` | Token/asset - created via `_newAsset(decimals)` |
| `Contract` | Another FULL or MOCK contract in the deployment |
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

Relations only between FULL and MOCK contracts:

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
    "FullContract": {
      "classification": "FULL",
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
        "paused": {
          "source": "Dictionary",
          "coverage_classes": [
            { "value": false, "unlocks": "Normal operations" },
            { "value": true, "unlocks": "Paused revert path" }
          ],
          "recommended": false,
          "reason": "Enables all operation paths"
        }
      }
    },

    "MockContract": {
      "classification": "MOCK",
      "influence": "input-only",
      "relations": {
        "FullContract": "ONE_TO_ONE"
      },
      "configuration": {
        "price": {
          "source": "Dictionary",
          "coverage_classes": [
            { "value": 0, "unlocks": "Zero price edge case" },
            { "value": "1e18", "unlocks": "Normal price" }
          ],
          "recommended": "1e18",
          "reason": "Non-zero required for calculations"
        }
      }
    }
  },

  "absorb": {
    "TroveManager": {
      "functions": ["offset"],
      "prank_as": "troveManager"
    },
    "User": {
      "functions": ["provideToSP", "withdrawFromSP", "claimAllCollGains"],
      "prank_as": "actor"
    }
  }
}
```

---

## Coverage Class Patterns

### Boolean Flags
| Pattern | Values | Coverage |
|---------|--------|----------|
| Gate | `false` | Normal path |
| | `true` | Revert path |
| **Recommend**: `false` unless testing reverts |

### Percentage/BPS Values
| Pattern | Values | Coverage |
|---------|--------|----------|
| Zero | `0` | Feature disabled |
| Normal | `1` - `9999` | Feature active |
| Max | `10000` | Edge case, 100% |
| **Recommend**: Mid-range for normal operation |

### Cap Values
| Pattern | Values | Coverage |
|---------|--------|----------|
| Zero | `0` | All operations blocked |
| Limited | `1e18` | Cap enforcement |
| Unlimited | `type(uint).max` | Cap bypassed |
| **Recommend**: `type(uint).max` for operation coverage |

### Address Values
| Pattern | Values | Coverage |
|---------|--------|----------|
| Zero | `address(0)` | Validation revert |
| Valid | `deployed contract` | Normal operation |
| **Recommend**: Valid address for operation coverage |

---

## Rules

1. Only FULL and MOCK contracts get full configuration
2. ABSORB contracts listed separately with functions and prank identity
3. DISCARD contracts omitted entirely
4. Every constructor parameter must be in configuration
5. Every state variable from input must be in configuration
6. `coverage_classes` required for Dictionary source with meaningful branches
7. `recommended` value must maximize operation coverage
8. `reason` explains why recommended value was chosen
9. Relations only reference FULL or MOCK contracts
10. Contract source type can only reference FULL or MOCK contracts

---

## Checklist

- [ ] All FULL contracts have complete configuration
- [ ] All MOCK contracts have configuration for SUT-observable parameters
- [ ] All ABSORB contracts listed with functions
- [ ] DISCARD contracts not present
- [ ] Every configuration has a valid source
- [ ] Dictionary values have coverage_classes analysis
- [ ] recommended value maximizes operational coverage
- [ ] Relations only between FULL/MOCK contracts
- [ ] absorb section includes prank identity for each