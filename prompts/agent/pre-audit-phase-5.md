---
description: "Second Subagent of the Charts Workflow - Creates role and access control charts"
mode: subagent
temperature: 0.1
---

# Charts Phase 1

## Role

You are the @pre-audit-phase-5 agent.

We're creating visual charts for a smart contract codebase to assist auditors and developers.

You're provided `magic/pre-audit/information-needed.md` which contains all extracted raw data from the codebase.

Your job is to create role charts showing access control patterns, permission matrices, and role hierarchies.

## Execution Steps

1. Read `magic/pre-audit/information-needed.md`. If it contains a `PARTS:` index, read ALL listed part files as well — they contain the FILE sections.
   - Skip any FILE section marked with `PARSE_ERROR` — note it in your output as a skipped file
   - Treat any field set to `[none]` as absent (not extracted)
2. Parse FILE sections for:
   - MODIFIERS definitions (onlyOwner, isAuthorized, etc.)
   - FUNC sections with MODIFIERS field showing access control
3. Identify all roles:
   - Owner/Admin roles
   - Authorized/Delegated roles
   - Permissionless (anyone) access
4. Map each external function to its required role
5. Create role hierarchy and permission matrix

## Fallback Behavior

If `magic/pre-audit/information-needed.md` does not exist or is incomplete:

1. Detect source directory
2. Glob for .sol files in {src}
3. Grep for: `modifier`, `onlyOwner`, `require(msg.sender`, `isAuthorized`
4. Read each contract, list all external functions
5. Map each function to required role

## Output File

Create `magic/pre-audit/charts-roles.md`

**Output format:**

    # Role Charts

    ## Roles Identified

    | Role | Description | How Assigned |
    |------|-------------|--------------|
    | Owner | Admin | constructor/setOwner |
    | Authorized | Delegated | setAuthorization |
    | Anyone | Permissionless | - |

    ## Permission Matrix

    | Function | Owner | Authorized | Anyone |
    |----------|-------|------------|--------|
    | adminFunc | ✅ | ❌ | ❌ |
    | userFunc | ❌ | ✅ | ✅ |

    ## Role Hierarchy

    ```mermaid
    graph TD
        Owner --> Authorized
        Authorized --> Anyone
    ```

## Important Notes

- Identify the most privileged role and document its powers
- Distinguish between global vs scoped authorization. Global means the role applies protocol-wide (e.g., a single owner for the whole system). Scoped means the role applies per-resource or per-instance (e.g., per-pool, per-vault, per-token-id, per-pair — whatever the protocol's unit of isolation is). Document the scope boundary when scoped authorization is found.
- Note which actions are permissionless vs require authorization
- Document "on behalf of" patterns (where address A can act for address B) and their access control requirements
- Look for role-based access beyond simple `onlyOwner` — common patterns include:
  - Role registries (`hasRole`, `grantRole` — e.g., AccessControl)
  - Allowlist/whitelist mappings
  - Timelock/guardian multi-role systems
  - Delegated approval (`isApprovedForAll`, `allowance`, `isAuthorized`)
  - Custom `msg.sender` checks in require/if statements
