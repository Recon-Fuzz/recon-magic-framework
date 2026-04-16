# Recon Pro Fuzzing Deep Integration

This document explores integrating Recon Magic (workflow framework) with the Recon Pro backend (express-repo-to-abi-data) to allow AI workflows to automatically trigger fuzzing jobs.

## Goal

Close the loop on the fuzzing workflow:
```
User creates Claude Job → AI workflow runs → generates fuzzing setup → triggers actual fuzzing job → results back to user
```

Currently, the Claude workflow can generate fuzzing configurations but cannot programmatically create a fuzzing job on the backend.

---

## Current Backend Architecture

### API Overview

The express-repo-to-abi-data backend exposes:

**User-Authenticated Routes:**
- `/jobs` - Fuzzing job management
- `/claude/jobs` - AI workflow job management
- `/claude/invites` - Invite users to generated repos
- `/installs` - GitHub app installations
- `/organizations` - Org management

**Service Routes:**
- `/claude/jobs/worker/*` - Claude worker endpoints (internal)

### Authentication Mechanisms

| Auth Type | Token Format | Use Case |
|-----------|--------------|----------|
| GitHub OAuth | `Bearer ghu_*` | Primary user auth |
| API Keys | `Bearer api_*` | Programmatic access |
| Claude Service | `CLAUDE_SECRET` env var | Claude background worker |
| Runner | JWT with `JSON_WEB_TOKEN_SECRET_RUNNER` | Job execution workers |
| Listener | Bearer = Listener ID | Webhook-triggered automation |

### Job Ownership Model

```typescript
model Organization {
  id: string
  name: string (GitHub org name)
  users: User[]
  jobs: Job[]
  claudeJobs: ClaudeJob[]
  billingStatus: PAID | TRIAL | UNPAID | REVOKED
}

model User {
  id: string (GitHub user ID)
  organizationId: string
}
```

Jobs are scoped to organizations. Most endpoints verify:
```
job.organizationId == req.user.userData.organizationId
```

---

## Authorization Challenges

### The Core Problem

We want Recon Magic (running as a Claude worker) to create a fuzzing job on behalf of the org that owns the Claude job.

**Current auth tiers don't support this:**
- **User auth** → tied to a specific user's org
- **Claude worker auth** (`CLAUDE_SECRET`) → global, not org-scoped
- **Runner auth** → for job execution, not job creation

### The Trust Chain Gap

```
User → creates Claude Job → Claude Worker picks it up → wants to create Fuzzing Job
        (org X)              (global auth)                  (needs org X auth)
```

The Claude worker has no way to prove it's acting on behalf of org X when calling `POST /jobs/:fuzzerType`.

### Solution Options

| Approach | Description | Pros | Cons |
|----------|-------------|------|------|
| **A. Service-to-service token** | New auth type for cross-service calls | Clean, explicit | New auth system to implement |
| **B. Embed org context in Claude job** | New endpoint that trusts Claude worker to specify org | Uses existing data | Need validation that Claude worker can only use orgs from its jobs |
| **C. API key per org** | Use org's API key | Already exists | API keys are user-bound; security risk if leaked |
| **D. Job inheritance** | Child job inherits parent's org | Elegant, auditable | New concept to implement |

### Recommended: Job Inheritance (Option D)

Add a new endpoint:
```
POST /jobs/:fuzzerType/from-claude-job/:claudeJobId
Auth: onlyClaude
```

This endpoint:
1. Validates the Claude worker token
2. Looks up the Claude job by ID
3. Extracts `organizationId` from the parent Claude job
4. Creates the fuzzing job with that org ownership
5. Links child job to parent for audit trail

**Benefits:**
- Clear ownership chain
- Auditable (can trace job lineage)
- No new auth tokens to manage
- Claude worker can only create jobs for orgs it has active Claude jobs for

---

## GitHub Permission Issues

### How GitHub App Installation Works

The Recon GitHub App must be installed to access private repos. Installation requires:
- User with admin access to the target org/repo
- Interactive OAuth flow or manual installation via GitHub UI
- **Cannot be automated via API** (GitHub security restriction)

### Current GitHub Integration

```typescript
// Token generation for repo access
getAppAccessTokenForRepo(orgName, repoName)

// User invitation to generated repos
inviteUserToRepo(orgName, repoName, userHandle)  // Uses hardcoded GHTOKEN

// Permission verification
verifyUserHasPermissionsForRepo()
```

### Repo Access Scenarios

| Scenario | GitHub App Needed On | Who Installs | Current Status |
|----------|---------------------|--------------|----------------|
| User's source repo | User's org | User (manual) | Working |
| Recon's generated output repo | Recon-Fuzz org | Recon | Already installed |
| Fuzzing user's repo | User's org | User (manual) | Working |
| Fuzzing Recon's generated repo | Recon-Fuzz org | Recon | Needs `GHTOKEN` |

### The Private Repo Problem

If Claude generates a private repo under Recon's namespace and we want to fuzz it:

**Problem:** The user's org doesn't have the GitHub App installed on Recon's repos.

**Solutions:**

1. **Use master token** - `GHTOKEN` already available to runners for Recon-owned repos
2. **Fork model** - Fork to user's org instead of creating in Recon's namespace
3. **Collaborator invite** - Already implemented via `inviteUserToRepo()`
4. **Public repos** - Make generated repos public (security tradeoff)

### Programmatic App Installation?

**Not possible.** GitHub requires interactive user consent for app installations.

**Workarounds:**
- Generate one-click installation URL for user
- Detect missing installation and prompt user
- Use collaborator invites as fallback access method

---

## Recommended Implementation Path

### Phase 1: Job Inheritance Endpoint

**Backend changes (express-repo-to-abi-data):**

```typescript
// New route: POST /jobs/:fuzzerType/from-claude-job/:claudeJobId
// Middleware: onlyClaude

async function createJobFromClaudeJob(req, res) {
  const { fuzzerType, claudeJobId } = req.params;

  // 1. Fetch parent Claude job
  const claudeJob = await getClaudeJob(claudeJobId);
  if (!claudeJob) return res.status(404).json({ error: "Claude job not found" });

  // 2. Validate Claude job is complete
  if (claudeJob.status !== "DONE") {
    return res.status(400).json({ error: "Claude job not complete" });
  }

  // 3. Extract org from parent job
  const organizationId = claudeJob.organizationId;

  // 4. Create child fuzzing job with inherited org
  const job = await createJob({
    ...req.body,
    organizationId,
    metadata: {
      ...req.body.metadata,
      parentClaudeJobId: claudeJobId,
      method: "claude-workflow"
    }
  });

  return res.json(job);
}
```

### Phase 2: Recon Magic Integration

**Workflow framework changes:**

Add a new step type or program that calls the inheritance endpoint:

```json
{
  "type": "task",
  "name": "Trigger Fuzzing Job",
  "model": { "type": "PROGRAM" },
  "prompt": "create-fuzzing-job --claude-job-id ${CLAUDE_JOB_ID} --fuzzer echidna --duration 1800"
}
```

The `create-fuzzing-job` tool would:
1. Read `CLAUDE_JOB_ID` from environment (set by runner)
2. Call `POST /jobs/echidna/from-claude-job/{claudeJobId}`
3. Authenticate with `CLAUDE_SECRET`
4. Return the new job ID

### Phase 3: Repo Access Strategy

**For fuzzing the user's original repo:**
- Should work as-is (user already has app installed)

**For fuzzing Recon's generated repo:**
- Store `installation_id` in Claude job result data
- Runner uses `GHTOKEN` for Recon-owned repos
- Pass repo coordinates (org/repo/ref) from Claude job results

```typescript
// In Claude job resultData
{
  generatedRepo: {
    orgName: "Recon-Fuzz",
    repoName: "audit-output-xyz",
    ref: "main",
    installationId: "12345"  // For downstream access
  }
}
```

### Phase 4: User Notification

After fuzzing job completes:
1. Notify user via existing channels (webhook, email, Telegram)
2. Include link to results
3. If app installation needed, provide installation URL

---

## Security Considerations

### Validation Requirements

1. **Claude job must exist** - Prevent arbitrary org spoofing
2. **Claude job must be DONE** - Prevent race conditions
3. **TTL on inheritance** - Only allow child job creation within X hours of completion
4. **Rate limiting** - Prevent abuse of job creation
5. **Audit logging** - Track full job lineage chain

### Attack Vectors to Mitigate

| Attack | Mitigation |
|--------|------------|
| Spoofing org via fake Claude job ID | Validate job exists and is owned by real org |
| Creating jobs for orgs without billing | Inherit billing check from parent org |
| DoS via mass job creation | Rate limit per Claude job (1 child per parent?) |
| Accessing repos without permission | Validate repo access at job execution time |

### Secrets Management

Required environment variables:
- `CLAUDE_SECRET` - Already exists, used for worker auth
- `GHTOKEN` - Already exists, used for Recon repo operations
- No new secrets needed if using job inheritance model

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           USER FLOW                                      │
└─────────────────────────────────────────────────────────────────────────┘

User (Org X)
    │
    ▼
┌─────────────────┐
│ Create Claude   │  POST /claude/jobs
│ Job             │  Auth: User token
│ (orgId: X)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Claude Worker   │  GET /claude/jobs/worker/
│ Picks Up Job    │  Auth: CLAUDE_SECRET
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Recon Magic     │  Runs workflow steps
│ Executes        │  Generates fuzzing config
│ Workflow        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Create Fuzzing  │  POST /jobs/echidna/from-claude-job/{claudeJobId}
│ Job             │  Auth: CLAUDE_SECRET
│ (inherits orgX) │  Inherits organizationId from parent
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Runner Executes │  Fuzzes target repo
│ Fuzzing Job     │  Uses GHTOKEN for Recon repos
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Results to User │  Webhook / notification
│ (Org X)         │
└─────────────────┘
```

---

## Open Questions

1. **Should child jobs count against org's billing?** Probably yes - they consume compute resources.

2. **Can one Claude job create multiple fuzzing jobs?** Maybe limit to 1, or require explicit allowance.

3. **What if Claude job's org billing expires before fuzzing completes?** Check billing at fuzzing job creation, not execution.

4. **Should we support other job types?** Start with fuzzing, extend to ABI jobs later if needed.

5. **How to handle monorepos?** Pass `foundryRoot` from Claude job to fuzzing job.

---

## Summary

The integration requires:

1. **New backend endpoint** for job inheritance (`POST /jobs/:fuzzerType/from-claude-job/:claudeJobId`)
2. **Recon Magic tooling** to call the endpoint after workflow completion
3. **Proper repo access handling** using existing `GHTOKEN` for Recon-owned repos
4. **Security validations** to prevent org spoofing and abuse

The key insight is that **job inheritance** provides a clean authorization model without requiring new token types or complex permission systems. The parent Claude job serves as proof of org membership.
