# Contract Test Configuration Framework

## Given

- Contract set (deployed contracts only; inheritance is inlined)
- Target contract(s) (SUT)
- Testing goal (unit | integration | scenario)
- Dependency graph: calls + state writes (reads are passive, writes create transitive dependencies)

## Derive

- **CODE:** SUT + dependencies whose internal behavior matters for the test goal
- **MOCK:** Dependencies at boundary, deployed as simplified versions
- **THIS:** Contracts the test contract itself replaces (no deployment)
- **DISCARD:** No call or state-write path to SUT

## Rules

1. No dependency path to SUT → DISCARD
2. Caller with simple relationship, role agnostic → THIS
3. Dependency needing controlled behavior but not internal logic → MOCK
4. Dependency needing internal behavior → CODE

## Simplification Hierarchy

Most → least deployed complexity:

| Category | Deployment |
|----------|------------|
| CODE     | Full implementation deployed |
| MOCK     | Simplified implementation deployed |
| THIS     | Test contract replaces it (no deployment) |
| DISCARD  | Ignored entirely (no path to SUT) |

## Notes

- Omit contracts that cannot be deployed (libraries and abstract contracts)
- Multiple actors (e.g., admin vs user) handled via `prank`, not separate contracts
- Mocking removes internal behavior; if integration behavior matters → CODE, not MOCK

## Output

4 Tables:
- Contracts to CODE
- Contracts to MOCK
- Contracts to THIS
- Contracts to DISCARD

Write exclusively the 4 tables in `magic/deploy-table.md`

Do not code anything.

Current Goal: