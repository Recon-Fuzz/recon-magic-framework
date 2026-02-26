# Runner Merge Plan: Unified FUZZ + AI Infrastructure

## Executive Summary

**Can we merge?** Yes, and we should. The three systems share 80% of their infrastructure needs and the backend (`express-repo-to-abi-data`) already has `/claude/jobs` routes, suggesting this merge was always the intended direction.

---

## Current Architecture

### Three Systems Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    express-repo-to-abi-data (Backend API)                   │
│  - Manages jobs, auth, organizations, recipes                               │
│  - Has /claude/jobs and /claude/invites routes (AI jobs!)                   │
│  - Launches ECS Fargate tasks for fuzzing                                   │
│  - Polls for QUEUED jobs, starts runner containers                          │
└─────────────────────────────────────────────────────────────────────────────┘
                │                                    │
                ▼                                    ▼
┌───────────────────────────────┐    ┌───────────────────────────────────────┐
│         runner                │    │      recon-magic-framework            │
│  (TypeScript, Dockerfile)     │    │  (Python, separate Dockerfile)        │
│                               │    │                                       │
│  Job Types:                   │    │  Job Types:                           │
│  - ECHIDNA                    │    │  - directPrompt                       │
│  - MEDUSA                     │    │  - workflowName                       │
│  - FOUNDRY                    │    │  - relativeWorkflow                   │
│  - HALMOS                     │    │                                       │
│  - KONTROL                    │    │  Models:                              │
│                               │    │  - PROGRAM                            │
│  Tools installed:             │    │  - CLAUDE_CODE                        │
│  - echidna, medusa            │    │  - OPENCODE                           │
│  - foundry, halmos            │    │                                       │
│  - bitwuzla, yices            │    │  Tools installed:                     │
│  - solc, slither              │    │  - echidna (brew), medusa             │
│  - AWS CLI                    │    │  - foundry                            │
│                               │    │  - claude-code, opencode-ai           │
│  Base: ubuntu:24.04           │    │  - Python, Node, Go                   │
│                               │    │                                       │
│  Output: S3 (logs, corpus)    │    │  Base: python:3.12-slim               │
│  DB: Prisma direct            │    │  Output: GitHub repo                  │
│                               │    │  DB: REST API polling                 │
└───────────────────────────────┘    └───────────────────────────────────────┘
```

### Key Insight: Backend Already Supports AI Jobs

The `express-repo-to-abi-data` has:
- `/claude/jobs` routes (src/routes/claude/jobs.ts)
- `/claude/invites` routes (src/routes/claude/invites.ts)

This means the infrastructure for AI jobs already exists in the backend!

---

## Dockerfile Comparison

### Runner Dockerfile (160 lines)
```
Base: ubuntu:24.04
├── Node 20 (via NVM)
├── Python 3 (venv)
├── Go 1.22.5
├── solc-select (solc 0.8.24)
├── slither
├── echidna 2.3.0-RC2
├── foundry
├── medusa (v1.4.1)
├── halmos
├── AWS CLI
├── bitwuzla, yices (SMT solvers)
└── App: TypeScript runner
```

### Magic Framework Dockerfile (81 lines)
```
Base: python:3.12-slim
├── Node 20 (via nodesource)
├── Python (native)
├── Go 1.21.5
├── echidna (via Homebrew - slow!)
├── foundry
├── medusa
├── claude-code (npm)
├── opencode-ai (npm)
├── UV (Python)
└── App: Python worker
```

### Tool Overlap Matrix

| Tool | Runner | Magic | Unified Need |
|------|--------|-------|--------------|
| Node 20 | ✅ | ✅ | ✅ |
| Python 3 | ✅ (venv) | ✅ (native) | ✅ |
| Go | ✅ 1.22.5 | ✅ 1.21.5 | ✅ (use 1.22) |
| Foundry | ✅ | ✅ | ✅ |
| Echidna | ✅ (binary) | ✅ (brew) | ✅ (use binary) |
| Medusa | ✅ | ✅ | ✅ |
| Halmos | ✅ | ❌ | ✅ |
| Slither | ✅ | ❌ | ✅ |
| solc-select | ✅ | ❌ | ✅ |
| Bitwuzla | ✅ | ❌ | ✅ (for FV) |
| Yices | ✅ | ❌ | ✅ (for FV) |
| claude-code | ❌ | ✅ | ✅ |
| opencode-ai | ❌ | ✅ | ✅ |
| AWS CLI | ✅ | ❌ | ✅ |

---

## Proposed Unified Architecture

### Option A: Single Unified Docker Image (Recommended)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         UNIFIED RECON RUNNER                                │
│                                                                             │
│  Base: ubuntu:24.04                                                         │
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │  FUZZ TOOLS     │  │  AI TOOLS       │  │  SHARED TOOLS   │             │
│  │  - echidna      │  │  - claude-code  │  │  - foundry      │             │
│  │  - medusa       │  │  - opencode-ai  │  │  - Node 20      │             │
│  │  - halmos       │  │  - UV/Python    │  │  - Go 1.22      │             │
│  │  - bitwuzla     │  │                 │  │  - git          │             │
│  │  - yices        │  │                 │  │  - AWS CLI      │             │
│  │  - slither      │  │                 │  │                 │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      UNIFIED RUNNER (TypeScript)                     │   │
│  │                                                                      │   │
│  │  switch (job.type) {                                                 │   │
│  │    case "ECHIDNA":                                                   │   │
│  │    case "MEDUSA":                                                    │   │
│  │    case "HALMOS":                                                    │   │
│  │    case "FOUNDRY":                                                   │   │
│  │      → runFuzzingJob(job)                                            │   │
│  │                                                                      │   │
│  │    case "AI_WORKFLOW":                                               │   │
│  │    case "AI_PROMPT":                                                 │   │
│  │      → runAIJob(job)  // calls python worker or claude-code          │   │
│  │  }                                                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Option B: Separate Images, Same Infrastructure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    express-repo-to-abi-data                                 │
│                                                                             │
│  startRunner() {                                                            │
│    if (job.type in ["ECHIDNA", "MEDUSA", "HALMOS"]) {                       │
│      taskDefinition = "recon-fuzz-runner"                                   │
│    } else if (job.type in ["AI_WORKFLOW", "AI_PROMPT"]) {                   │
│      taskDefinition = "recon-ai-runner"                                     │
│    }                                                                        │
│    ecs.runTask({ taskDefinition, ... })                                     │
│  }                                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                │                              │
                ▼                              ▼
┌───────────────────────────┐    ┌───────────────────────────────────────────┐
│  recon-fuzz-runner        │    │  recon-ai-runner                          │
│  (current runner)         │    │  (current magic-framework)                │
│  ~2GB image               │    │  ~1.5GB image                             │
└───────────────────────────┘    └───────────────────────────────────────────┘
```

---

## Recommended Approach: Option A (Single Image)

### Why Single Image?

1. **Shared 70% of tools** - echidna, medusa, foundry, Node, Python, Go
2. **Simpler infrastructure** - one image to build, push, maintain
3. **Cross-job capabilities** - AI can run fuzzing tools, fuzzers can use AI
4. **Future flexibility** - hybrid jobs that do both (AI-guided fuzzing)

### Estimated Image Size

```
Runner alone:     ~3.0 GB (echidna, medusa, halmos, solvers)
Magic alone:      ~1.8 GB (homebrew echidna is huge)
Unified (smart):  ~3.5 GB (deduplicated, no homebrew)
```

The unified image is only ~500MB larger than runner alone because we:
- Remove homebrew (~800MB saved)
- Add claude-code/opencode-ai (~200MB)
- Share foundry, go, node (no duplication)

---

## Implementation Plan

### Phase 1: Unified Dockerfile

```dockerfile
# Unified Recon Runner Dockerfile
FROM ubuntu:24.04

# === SHARED BASE ===
RUN apt-get update && apt-get install -y \
    curl gcc make python3-pip python3-venv unzip jq wget tar \
    git build-essential cmake ninja-build \
    libboost-all-dev flex bison libffi-dev zlib1g-dev \
    software-properties-common ripgrep sudo

# === NODE 20 ===
ENV NODE_VERSION=20.18.0
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.3/install.sh | bash && \
    export NVM_DIR=/root/.nvm && \
    . "$NVM_DIR/nvm.sh" && nvm install ${NODE_VERSION}
ENV PATH="/root/.nvm/versions/node/v${NODE_VERSION}/bin:${PATH}"
RUN corepack enable

# === PYTHON ===
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip3 install solc-select hexbytes slither-analyzer uv

# === GO ===
RUN wget https://go.dev/dl/go1.22.5.linux-amd64.tar.gz && \
    tar -C /usr/local -xzf go1.22.5.linux-amd64.tar.gz
ENV PATH="$PATH:/usr/local/go/bin"

# === FOUNDRY ===
RUN curl -L https://foundry.paradigm.xyz | bash && \
    export PATH="$PATH:/root/.foundry/bin" && foundryup
ENV PATH="$PATH:/root/.foundry/bin"

# === FUZZ TOOLS ===
# Echidna (binary, not homebrew)
RUN wget https://github.com/crytic/echidna/releases/download/v2.3.0-RC2/echidna-2.3.0-RC2-x86_64-linux.tar.gz && \
    tar -xvkf echidna-2.3.0-RC2-x86_64-linux.tar.gz && \
    mv echidna /usr/bin/ && rm echidna-*.tar.gz

# Medusa
RUN git clone https://github.com/crytic/medusa && \
    cd medusa && go build && mv medusa /usr/local/bin/ && rm -rf /medusa

# Halmos
RUN uv tool install --python 3.12 halmos && \
    ln -sf /root/.local/bin/halmos /usr/local/bin/halmos

# Bitwuzla
RUN pip3 install meson && \
    git clone https://github.com/bitwuzla/bitwuzla /bitwuzla && \
    cd /bitwuzla && ./configure.py && cd build && ninja install

# Yices
RUN wget https://github.com/SRI-CSL/yices2/releases/download/Yices-2.6.4/yices-2.6.4-x86_64-pc-linux-gnu.tar.gz && \
    tar -xzvf yices-*.tar.gz && mv yices-*/bin/* /usr/local/bin/ && rm -rf yices-*

# === AI TOOLS ===
RUN npm install -g @anthropic-ai/claude-code opencode-ai

# === AWS CLI ===
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && ./aws/install && rm -rf awscliv2.zip aws

# === APP ===
WORKDIR /app
COPY . .

# Install both TypeScript runner and Python magic framework
RUN yarn install --frozen-lockfile
RUN pip install -e /app/magic  # Install magic framework as package

ENTRYPOINT ["yarn", "start"]
```

### Phase 2: Unified Runner Entry Point

```typescript
// src/index.ts (unified runner)
import { Job } from "@prisma/client";
import { runFuzzingJob } from "./fuzzing/runner";
import { runAIJob } from "./ai/runner";

async function main(job: Job) {
  // Dispatch based on job type
  switch (job.fuzzer) {
    case "ECHIDNA":
    case "MEDUSA":
    case "HALMOS":
    case "FOUNDRY":
    case "KONTROL":
      return runFuzzingJob(job);

    case "AI_WORKFLOW":
    case "AI_PROMPT":
      return runAIJob(job);

    default:
      throw new Error(`Unknown job type: ${job.fuzzer}`);
  }
}
```

### Phase 3: AI Job Runner

```typescript
// src/ai/runner.ts
import { Job } from "@prisma/client";
import { exec } from "../services/exec";

export async function runAIJob(job: Job) {
  const { repoUrl, workflowName, prompt, modelType } = job.aiConfig;

  // Clone repo
  await exec(`git clone ${repoUrl} repo`);

  // Run magic framework
  if (workflowName) {
    await exec(`cd repo && python -m magic --workflow ${workflowName}`);
  } else if (prompt) {
    // Direct prompt mode
    await exec(`cd repo && claude "${prompt}"`);
  }

  // Push results to GitHub (magic framework handles this)
  // Update job status
}
```

### Phase 4: Backend Changes (express-repo-to-abi-data)

```typescript
// src/runner-starter/starter.ts
export default async function startRunner() {
  const job = await prisma.job.findFirst({
    where: { status: "QUEUED" },
  });

  // Determine task definition based on job type
  // For now, use same image for both
  const taskDefinition = config.aws.ecs.runnerTaskDefinition;

  // Command differs based on job type
  let command: string[];
  if (["ECHIDNA", "MEDUSA", "HALMOS"].includes(job.fuzzer)) {
    command = ["--runner", "--job-id", job.id, "--url", url];
  } else if (["AI_WORKFLOW", "AI_PROMPT"].includes(job.fuzzer)) {
    command = ["--ai-runner", "--job-id", job.id];
  }

  await ecs.send(new RunTaskCommand({
    // ... same config
    overrides: {
      containerOverrides: [{
        command,
        // ... env vars
      }],
    },
  }));
}
```

---

## Migration Path

### Step 1: Create Unified Dockerfile
- Merge both Dockerfiles
- Test that existing fuzzing jobs still work
- Test that AI jobs work

### Step 2: Update Terraform
- Single task definition
- Different command overrides per job type

### Step 3: Update Backend
- Modify starter.ts to dispatch based on job type
- Ensure /claude/jobs routes work with new runner

### Step 4: Deprecate Old Magic Worker
- Magic framework becomes a library, not standalone worker
- Remove worker.py polling loop (use ECS task launch instead)

---

## Benefits of Merge

1. **Single Docker build/push pipeline**
2. **Same ECS cluster, VPC, security groups**
3. **Same logging (CloudWatch)**
4. **Same S3 bucket for artifacts**
5. **AI jobs can run fuzzing tools** (hybrid workflows)
6. **Fuzz jobs can use AI** (AI-assisted coverage improvement)
7. **Unified monitoring/alerting**

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Larger image size | Use multi-stage build, cache layers |
| AI tools break fuzzing | Separate entrypoints, same image |
| Longer build time | Layer caching, parallel builds |
| Complexity | Clear separation of concerns in code |

---

## Recommendation

**Start with the Dockerfile merge.** This is the lowest-risk change:

1. Create unified Dockerfile in `runner/`
2. Test fuzzing jobs still work
3. Add AI tools
4. Test AI jobs work
5. Then update backend and terraform

The shared problems (foundry root detection, monorepo support, job status handling) can be solved once and apply to both job types.
