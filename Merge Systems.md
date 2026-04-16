# Merge Systems: Unified FUZZ + AI Runner

## The Big Picture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CURRENT STATE (3 Systems)                           │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                    express-repo-to-abi-data (Backend API)                   │
│  - Already has /claude/jobs routes!                                         │
│  - Launches ECS Fargate tasks                                               │
└─────────────────────────────────────────────────────────────────────────────┘
           │                                        │
           ▼                                        ▼
┌─────────────────────────┐          ┌─────────────────────────────────────┐
│      runner             │          │      recon-magic-framework          │
│  (TypeScript)           │          │  (Python)                           │
│  ubuntu:24.04           │          │  python:3.12-slim                   │
│  ~3GB image             │          │  ~1.8GB image                       │
│                         │          │                                     │
│  ECHIDNA, MEDUSA        │          │  CLAUDE_CODE, OPENCODE              │
│  HALMOS, FOUNDRY        │          │  PROGRAM                            │
└─────────────────────────┘          └─────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                         TARGET STATE (1 System)                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                    express-repo-to-abi-data (Backend API)                   │
│  - Same routes                                                              │
│  - Launches unified runner                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         UNIFIED RECON RUNNER                                │
│  ubuntu:24.04 | ~3.5GB image                                                │
│                                                                             │
│  ┌───────────────────┐  ┌───────────────────┐  ┌───────────────────┐       │
│  │    FUZZ TOOLS     │  │    AI TOOLS       │  │   SHARED TOOLS    │       │
│  │  echidna, medusa  │  │  claude-code      │  │  foundry, node    │       │
│  │  halmos, slither  │  │  opencode-ai      │  │  python, go       │       │
│  │  bitwuzla, yices  │  │                   │  │  git, aws-cli     │       │
│  └───────────────────┘  └───────────────────┘  └───────────────────┘       │
│                                                                             │
│  Dispatch: job.type → runFuzzJob() OR runAIJob()                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Why Merge?

### 1. Backend Already Supports AI Jobs
```
express-repo-to-abi-data/src/routes/claude/jobs.ts    ← exists!
express-repo-to-abi-data/src/routes/claude/invites.ts ← exists!
```

### 2. 70% Tool Overlap
| Tool | Runner | Magic | Both Need |
|------|--------|-------|-----------|
| Node 20 | ✅ | ✅ | ✅ |
| Python | ✅ | ✅ | ✅ |
| Go | ✅ | ✅ | ✅ |
| Foundry | ✅ | ✅ | ✅ |
| Echidna | ✅ | ✅ | ✅ |
| Medusa | ✅ | ✅ | ✅ |
| Halmos | ✅ | ❌ | ✅ |
| claude-code | ❌ | ✅ | ✅ |

### 3. Same Infrastructure Pattern
Both:
- Clone a repo
- Run commands in repo
- Upload results
- Update job status
- Need monorepo support (foundry root detection)

### 4. Hybrid Jobs Become Possible
- AI-guided fuzzing
- Fuzzer results → AI analysis
- AI writes handlers → Fuzzer tests them

---

## Unified Dockerfile (Draft)

```dockerfile
FROM ubuntu:24.04

# === SHARED BASE ===
RUN apt-get update && apt-get install -y \
    curl gcc make python3-pip python3-venv unzip jq wget tar \
    git build-essential cmake ninja-build ripgrep sudo \
    libboost-all-dev flex bison libffi-dev zlib1g-dev

# === NODE 20 ===
ENV NODE_VERSION=20.18.0
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.3/install.sh | bash
ENV NVM_DIR=/root/.nvm
ENV PATH="$NVM_DIR/versions/node/v${NODE_VERSION}/bin:${PATH}"
RUN . "$NVM_DIR/nvm.sh" && nvm install ${NODE_VERSION} && corepack enable

# === PYTHON ===
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip3 install solc-select hexbytes slither-analyzer uv

# === GO ===
RUN wget https://go.dev/dl/go1.22.5.linux-amd64.tar.gz && \
    tar -C /usr/local -xzf go1.22.5.linux-amd64.tar.gz
ENV PATH="$PATH:/usr/local/go/bin"

# === FOUNDRY ===
RUN curl -L https://foundry.paradigm.xyz | bash && foundryup
ENV PATH="$PATH:/root/.foundry/bin"

# === FUZZ TOOLS ===
# Echidna (binary release, NOT homebrew)
RUN wget https://github.com/crytic/echidna/releases/download/v2.3.0-RC2/echidna-2.3.0-RC2-x86_64-linux.tar.gz && \
    tar -xf echidna-*.tar.gz && mv echidna /usr/bin/

# Medusa
RUN git clone https://github.com/crytic/medusa /tmp/medusa && \
    cd /tmp/medusa && go build && mv medusa /usr/local/bin/

# Halmos + Solvers
RUN uv tool install --python 3.12 halmos
# Bitwuzla, Yices (see full Dockerfile)

# === AI TOOLS ===
RUN npm install -g @anthropic-ai/claude-code opencode-ai

# === AWS CLI ===
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && ./aws/install

# === APP ===
WORKDIR /app
COPY . .
RUN yarn install
RUN pip install -e ./magic  # Magic framework as library

ENTRYPOINT ["yarn", "start"]
```

---

## Unified Runner Logic

```typescript
// src/index.ts
import { Job } from "@prisma/client";

async function main(job: Job) {
  switch (job.type) {
    // Fuzzing jobs (existing)
    case "ECHIDNA":
    case "MEDUSA":
    case "HALMOS":
    case "FOUNDRY":
      return runFuzzingJob(job);

    // AI jobs (new)
    case "AI_WORKFLOW":
      return runWorkflowJob(job);  // Uses magic framework
    case "AI_PROMPT":
      return runPromptJob(job);    // Direct claude/opencode call

    default:
      throw new Error(`Unknown job type: ${job.type}`);
  }
}

async function runWorkflowJob(job: Job) {
  // Clone repo
  await exec(`git clone ${job.repoUrl} repo`);

  // Detect foundry root (shared problem!)
  const foundryRoot = await detectFoundryRoot("repo");

  // Run magic framework
  await exec(`cd repo && python -m magic \
    --workflow ${job.workflowName} \
    --foundry-root ${foundryRoot}`);
}
```

---

## Migration Steps

### Phase 1: Dockerfile Merge
1. Create unified Dockerfile in `runner/`
2. Add AI tools (claude-code, opencode-ai)
3. Remove homebrew from magic (use echidna binary)
4. Test fuzzing jobs still work
5. Test AI jobs work

### Phase 2: Runner Dispatch
1. Add job type dispatch logic
2. Import magic framework as library
3. Add `runWorkflowJob()` and `runPromptJob()`

### Phase 3: Backend Updates
1. Ensure `/claude/jobs` creates jobs with correct type
2. Update starter.ts command generation
3. Add AI-specific env vars to ECS task

### Phase 4: Deprecate Magic Worker
1. Remove standalone `worker.py` polling
2. Magic framework becomes library only
3. All jobs launch via ECS

---

## Shared Problems (Solve Once)

### 1. Foundry Root Detection
```python
def detect_foundry_root(repo_path):
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in ['.git', 'node_modules', 'lib']]
        if 'foundry.toml' in files:
            return os.path.relpath(root, repo_path)
    return "."
```

### 2. Job Failure Status
```typescript
await prisma.job.update({
  where: { id: job.id },
  data: {
    status: success ? "COMPLETED" : "FAILED",
    errorMessage: error?.message
  }
});
```

### 3. Monorepo Support
```typescript
const path = job.directory !== "." ? `repo/${job.directory}` : "repo";
// Used by BOTH fuzzing and AI jobs
```

---

## Benefits Summary

| Before (Separate) | After (Merged) |
|-------------------|----------------|
| 2 Docker images | 1 Docker image |
| 2 build pipelines | 1 build pipeline |
| 2 ECS task definitions | 1 task definition |
| Duplicate foundry/node/go | Shared tools |
| Can't mix AI + Fuzz | Hybrid jobs possible |
| 2 codebases to maintain | 1 unified runner |

---

## Image Size Comparison

```
Runner alone:           ~3.0 GB
Magic alone:            ~1.8 GB (homebrew bloat)
─────────────────────────────────
Separate total:         ~4.8 GB

Unified (optimized):    ~3.5 GB
─────────────────────────────────
Savings:                ~1.3 GB (27%)
```

---

## Next Action

**Start with Dockerfile merge** - lowest risk, highest impact:

```bash
cd ../runner
# 1. Add AI tools to existing Dockerfile
# 2. Build and test fuzzing still works
# 3. Test AI tools work
# 4. Push unified image
```
