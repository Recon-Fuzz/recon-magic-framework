# Contract Test Configuration Framework

## Given

- Contract set (deployed contracts only; inheritance is inlined)
- Target contract(s) (SUT)
- Dependency graph with edge types:
  - **call**: A invokes B.method()
  - **state-write**: A modifies state that B reads
  - **state-read**: A reads state from B

## Derive Classification

Classify each contract by analyzing **direction of influence** relative to the SUT:

| Classification | Influence Pattern | Deployment |
|----------------|-------------------|------------|
| **FULL** | Bidirectional state dependency (SUT ↔ Contract) | Real implementation |
| **MOCK** | Contract influences SUT, SUT doesn't influence Contract (Contract → SUT) | Simplified, controlled inputs |
| **ABSORB** | Calls into SUT, no state dependency (call-only inbound) | Test contract impersonates via prank |
| **DISCARD** | No path to SUT | Nothing |

## Rules

1. SUT is always FULL
2. Contract has state read by SUT AND state written by SUT → FULL
3. Contract has state read by SUT, NOT written by SUT → MOCK
4. Contract only calls SUT, no state entanglement → ABSORB
5. No path to SUT → DISCARD

## Decision Flow
```
For each contract C:
  
  Does C have any path to SUT?
    No  → DISCARD
    Yes ↓
  
  Does SUT write state that C reads, OR does C hold state that SUT writes?
    Yes → FULL (bidirectional state)
    No  ↓
  
  Does SUT read state from C?
    Yes → MOCK (C is an input source)
    No  ↓
  
  Does C call SUT?
    Yes → ABSORB (impersonate caller)
    No  → DISCARD (no meaningful interaction)
```

## Output

JSON with exactly 4 keys matching the classification categories.

Save to `magic/full-mock-absorb-spec.json`
```json
{
  "sut": "<ContractName>",
  "focus": "<TestingFocus>",
  
  "FULL": {
    "description": "Bidirectional state dependency - requires real implementation",
    "contracts": [
      {
        "name": "<ContractName>",
        "reason": "<Why bidirectional>",
        "sutReads": ["<method()>"],
        "sutWrites": ["<method()>"]
      }
    ]
  },
  
  "MOCK": {
    "description": "Contract influences SUT (SUT reads), SUT doesn't influence contract",
    "contracts": [
      {
        "name": "<ContractName>",
        "reason": "<Why mock>",
        "sutReads": ["<method()>"],
        "sutWrites": []
      }
    ]
  },
  
  "ABSORB": {
    "description": "Calls into SUT, no state dependency - test harness impersonates",
    "contracts": [
      {
        "name": "<ContractName>",
        "reason": "<Why absorb>",
        "callsTo": ["<method()>"],
        "impersonate": "address(<contract>)"
      }
    ]
  },
  
  "DISCARD": {
    "description": "No path to SUT - not deployed",
    "contracts": [
      {
        "name": "<ContractName>",
        "reason": "<Why no path>"
      }
    ]
  }
}
```

## Notes

- ABSORB contracts are not deployed; test uses `vm.prank(address)`
- MOCK contracts need only satisfy the interface SUT reads from
- FULL contracts must preserve state invariants SUT depends on
- Multiple actors sharing same pattern (e.g., users) consolidated under one ABSORB entry
- For SUT entry in FULL, use `"-"` for sutReads/sutWrites since it's the system under test