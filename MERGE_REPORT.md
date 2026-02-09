# Merge Report: recon-magic-framework + runner → Unified Monorepo

## 1. What Changed and Why

### 1.1 Repository Structure

The `Recon-Fuzz/runner` repository was imported into `recon-magic-framework` as a subdirectory via `git subtree add`. The framework repo is the base.

```
recon-magic-framework/           (base — unchanged)
├── cli.py, main.py, worker.py
├── core/, server/, tools/, ...
├── Dockerfile                   (REPLACED — merged version)
├── entrypoint.sh                (NEW — mode dispatcher)
├── .dockerignore                (NEW)
├── .gitignore                   (MERGED — Python + Node + Terraform)
├── .env.example                 (MERGED — framework + runner vars)
├── .github/workflows/
│   ├── docker-build-push.yml    (MODIFIED — BuildKit secrets, runner path triggers)
│   ├── runner-ci.yml            (NEW — runner production CI, from runner repo)
│   └── runner-staging-ci.yml    (NEW — runner staging CI, from runner repo)
└── runner/                      (NEW — imported from Recon-Fuzz/runner)
    ├── src/
    ├── infrastructure/
    ├── prisma/
    ├── package.json
    ├── tsconfig.json
    ├── yarn.lock
    └── run_halmos.sh
```

### 1.2 Files Modified (with rationale)

| File | Change | Why |
|------|--------|-----|
| **`Dockerfile`** | Replaced entirely | Merged both Dockerfiles into one image. Runner's Ubuntu 24.04 base (with full Solidity toolchain) + framework's Python/Claude Code deps. Single image serves both use cases via `MODE` env var. |
| **`.gitignore`** | Merged contents | Combined Python patterns (framework) + Node/Terraform patterns (runner) into one file. Removed duplicates. |
| **`.env.example`** | Merged contents | Combined framework env vars (API keys, workflow config) + runner env vars (DATABASE_URL, S3_BUCKET, AWS creds) with section headers. |
| **`.github/workflows/docker-build-push.yml`** | Updated | Added `DOCKER_BUILDKIT=1` + `--secret id=npm_token` (required for runner's private `@recon-fuzz/log-parser` dep). Added `runner/**` and `entrypoint.sh` to path triggers. |

### 1.3 Files Added

| File | Why |
|------|-----|
| **`entrypoint.sh`** | Dispatches container startup based on `MODE` env var: `runner` → `yarn start`, `framework` → `python3 cli.py`, `worker` → `python3 worker.py`. |
| **`.dockerignore`** | Excludes `.git/`, `.env`, `.claude/`, build artifacts, IDE files from Docker build context. Reduces context size and prevents leaking secrets into the image. |
| **`.github/workflows/runner-ci.yml`** | Runner's production CI pipeline (build/test, Docker push to ECR, Terraform validate, deploy). Paths updated from repo root to `runner/` subdirectory. |
| **`.github/workflows/runner-staging-ci.yml`** | Runner's staging CI pipeline. Same updates as above but targeting staging branch and staging AWS resources. |
| **`runner/`** (subtree) | The entire runner codebase imported via `git subtree add --squash`. |

### 1.4 Files Removed from `runner/`

These were hoisted to the monorepo root or replaced by merged versions:

| Removed | Replaced by |
|---------|-------------|
| `runner/Dockerfile` | Root `Dockerfile` (merged) |
| `runner/.gitignore` | Root `.gitignore` (merged) |
| `runner/.env.example` | Root `.env.example` (merged) |
| `runner/README.md` | Will be covered by root README |
| `runner/.github/workflows/ci.yml` | `.github/workflows/runner-ci.yml` |
| `runner/.github/workflows/staging-ci.yml` | `.github/workflows/runner-staging-ci.yml` |

### 1.5 Key Technical Decisions

| Decision | Rationale |
|----------|-----------|
| **Run as root + `IS_SANDBOX=1`** | Runner has hard dependencies on root (`/root/.nvm`, `/root/.foundry/bin`, `/root/.local/bin` all hardcoded in PATH). Claude Code blocks `--dangerously-skip-permissions` as root, but `IS_SANDBOX=1` is the official Anthropic-endorsed escape hatch. Eliminates the reconuser/linuxbrew/Homebrew complexity. |
| **Runner's Echidna fork** over framework's Homebrew Echidna | Runner uses `Recon-Fuzz/echidna-exp` (custom fork). This is the binary used in production. Dropped Homebrew entirely (~500MB saved). |
| **Runner's pinned Medusa** over framework's `@latest` | Runner pins commit `3857153` (v1.4.1) for reproducibility. Framework used `go install @latest` which is non-deterministic. |
| **Runner's Go 1.22.5** over framework's 1.21.5 | Newer version, backwards compatible. |
| **Runner's NVM Node 20.18.0** over framework's nodesource | Explicit version pinning. |
| **Single `COPY . /app/`** | Avoids the bug where a second COPY overwrites `node_modules/` installed by `yarn install`. Runner deps are installed LAST. |
| **Ubuntu 24.04 base** over `python:3.12-slim` | Runner needs the full OS for building SMT solvers (Bitwuzla), Go toolchain, and C/C++ deps from source. |

---

## 2. Potential Issues

### 2.1 Known Issues (pre-existing, not introduced by merge)

| Issue | Severity | Detail |
|-------|----------|--------|
| `RUN set -eux` is a no-op | Low | Each RUN gets a fresh shell. Was in original runner Dockerfile. |
| Duplicate Go PATH exports | Low | Lines 107-111 in Dockerfile. Redundant but harmless. Was in original runner Dockerfile. |
| `setup.py` naming confusion | Low | Framework's `setup.py` is NOT a setuptools file (it's application code). `pyproject.toml` is the real build config. Pre-existing. |
| `pyproject.toml` `packages=["."]` | Low | Bundles entire root into Python wheel. Pre-existing. |
| Runner's `src/` path aliases are CWD-dependent | Medium | Imports like `from "src/utils/utils"` rely on `tsconfig-paths/register` + correct working directory. Works inside Docker (entrypoint sets `cd /app/runner`). Would break if invoked from repo root during local dev. Pre-existing. |

### 2.2 Issues Introduced by Merge (and mitigated)

| Issue | Status | Detail |
|-------|--------|--------|
| `COPY . /app/` overwrites `node_modules/` | **Fixed** | Reordered: single COPY first, `pip install` second, `yarn install` last. |
| `.dockerignore` blocking runner COPY | **Fixed** | Removed `runner/` from `.dockerignore`. |
| `rm -rf /medusa` wrong path | **Fixed** | Changed to `cd .. && rm -rf medusa`. |
| Missing `.dockerignore` | **Fixed** | Created one. |

### 2.3 Issues to Watch

| Issue | Risk | Mitigation |
|-------|------|------------|
| **Docker image size** | The merged image will be large (~6-10GB). Includes full Solidity toolchain + Python + Node + Claude Code + SMT solvers. | Acceptable tradeoff for single-image simplicity. Can optimize later with multi-stage build if needed. |
| **Build time** | ~30-40 min for full rebuild. | Docker layer caching mitigates this — toolchain layers rarely change. Only application code layers rebuild frequently. |
| **CI path triggers are broad** | `docker-build-push.yml` triggers on `**/*.py` which matches Python files everywhere (including `runner/` tools). `runner-ci.yml` triggers on root `Dockerfile` changes even if only framework code changed. | Acceptable for now. Both images should rebuild when the shared Dockerfile changes. Can tighten later. |
| **Runner's `package.json` `repository` field** | Still points to `git@github.com:Recon-Fuzz/runner.git`. | Cosmetic. Update if/when the standalone runner repo is archived. |
| **No root-level `package.json` workspaces** | If yarn workspaces are ever added, runner's `postinstall` (prisma generate) and dependency hoisting could break. | Don't add workspaces without updating runner's prisma config. |

---

## 3. Advantages

| Advantage | Detail |
|-----------|--------|
| **Single Docker image** | One ECR repo, one image tag, one ECS task definition. Drastically simpler AWS infrastructure. |
| **No version drift** | Framework and runner are always deployed together. Eliminates "runner v0.3 is incompatible with framework v0.5" issues. |
| **Simpler CI** | One Dockerfile to maintain. One build context. Docker layer cache is shared between both components. |
| **Simpler Terraform** | One ECS service, one task definition, one set of IAM roles. `MODE` env var selects behavior at runtime. |
| **Eliminated Homebrew** | Dropped the entire Homebrew/linuxbrew dependency (~500MB, slow install). Echidna now comes from the custom fork binary (which is what production actually uses). |
| **Eliminated reconuser complexity** | No more `useradd`, `chown`, `sudoers`, or permission hacks. Single root user with `IS_SANDBOX=1` for Claude Code compatibility. |
| **Shared toolchain** | Both framework and runner need Foundry, Echidna, Medusa. Previously installed twice (differently). Now installed once with the runner's production-pinned versions. |
| **Unified `.env.example`** | One file documents all env vars for both components. |
| **Atomic deploys** | Infrastructure changes (Terraform) and application code ship together. No more coordinating deploys across two repos. |

---

## 4. How to Use the Docker Image

### 4.1 Building

```bash
# From the repo root
DOCKER_BUILDKIT=1 docker build \
  --secret id=npm_token,src=.npm_token \
  -t recon .
```

The `--secret` is required because runner depends on the private `@recon-fuzz/log-parser` npm package.

### 4.2 Running

The `MODE` environment variable controls what the container does:

```bash
# Framework CLI (default) — run a workflow against a local repo
docker run -it \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -v ./my-project:/workspace \
  recon \
  --workflow workflow-fuzzing-setup.json --repo /workspace

# Framework Worker — long-running poller that picks up jobs from backend API
docker run -d \
  -e MODE=worker \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -e WORKER_API_URL=https://api.getrecon.xyz \
  -e WORKER_API_TOKEN=... \
  recon

# Runner — execute a single fuzzing job
docker run -d \
  -e MODE=runner \
  -e DATABASE_URL=postgresql://... \
  -e S3_BUCKET=recon-fuzzing \
  -e AWS_ACCESS_KEY_ID=... \
  -e AWS_SECRET_ACCESS_KEY=... \
  recon \
  --jobId abc123 --url https://github.com/org/repo

# Interactive shell (debugging)
docker run -it --entrypoint /bin/bash recon
```

### 4.3 ECS/Fargate Usage

A single ECS task definition serves all three modes. Use the `MODE` environment variable override in the container definition:

| Use Case | `MODE` | Container Command Override |
|----------|--------|---------------------------|
| AI workflow orchestrator | `worker` | (none — entrypoint handles it) |
| Fuzzing job execution | `runner` | `--jobId <id> --url <repo>` |
| One-off CLI audit | `framework` | `--workflow <file> --repo /workspace` |

### 4.4 Local Development

For local development, the two codebases are still independent:

```bash
# Framework (Python)
cd /path/to/recon-magic-framework
pip install -e .
python cli.py --workflow workflows/audit.json --repo /path/to/target

# Runner (TypeScript)
cd /path/to/recon-magic-framework/runner
yarn install
yarn start --jobId test123 --url https://github.com/org/repo
```

---

## 5. How Framework and Runner Interact

### 5.1 Architecture

Framework and runner are **completely independent processes**. They share no code, no imports, and no direct communication. They are connected through **external intermediaries**:

```
┌──────────────┐         HTTP POST          ┌──────────────┐
│   Framework  │  ───────────────────────►  │  Backend API │
│   (Python)   │  dispatch-fuzzing request  │  (external)  │
│              │                            │              │
│  Polls API   │  ◄──── HTTP GET ────────── │  Stores jobs │
│  for jobs    │  fetch-pending-jobs        │  in Postgres │
└──────────────┘                            └──────┬───────┘
                                                   │
                                            Creates job record
                                            Spawns ECS task
                                                   │
                                                   ▼
                                            ┌──────────────┐
                                            │    Runner    │
                                            │ (TypeScript) │
                                            │              │
                                            │ Reads job    │
                                            │ from Postgres│
                                            │ via Prisma   │
                                            │              │
                                            │ Runs fuzzer  │
                                            │ Uploads to S3│
                                            └──────────────┘
```

### 5.2 The Full Job Lifecycle

1. **User submits a job** via web UI or API → Backend creates a "ClaudeJob" record.

2. **Framework worker picks it up** — `worker.py` polls the backend API every 60 seconds via `fetch_pending_jobs()`. When it finds one, it:
   - Clones the target repo
   - Sets up Claude Code / OpenCode agent configs
   - Creates a GitHub repo for output
   - Runs the multi-step AI workflow (defined in a JSON workflow file)

3. **Workflow steps execute sequentially** — each step can be:
   - `CLAUDE_CODE` — shells out to `claude --dangerously-skip-permissions`
   - `OPENCODE` — shells out to `opencode run`
   - `PROGRAM` — runs a shell command
   - `DISPATCH_FUZZING_JOB` — **this is the bridge to the runner**

4. **`DISPATCH_FUZZING_JOB` fires an HTTP POST** to `{WORKER_API_URL}/{WORKER_JOB_ID}/dispatch-fuzzing` with fuzzer type, duration, directory, and args. The **backend API** receives this and creates a fuzzing Job record in PostgreSQL.

5. **Backend spawns a runner** (via ECS RunTask or equivalent) with `--jobId` and `--url` CLI args, `MODE=runner`.

6. **Runner executes** — reads the job from PostgreSQL via Prisma, clones the repo, runs the fuzzer (Echidna/Medusa/Halmos/Foundry), streams logs to S3, and updates the job status in the database.

7. **Framework workflow may continue** with post-fuzzing steps (coverage analysis, report generation, etc.) while or after the runner finishes.

### 5.3 Key Point

The framework and runner **never talk to each other directly**. The backend API is the coordinator. This means:
- They can run on different machines, different ECS tasks, different regions.
- The merge into one Docker image is purely an **operational convenience** — it does not change the runtime architecture.
- In the merged image, both components are present but only one runs at a time (determined by `MODE`).

---

## 6. Summary of Changes

| Metric | Before (2 repos) | After (monorepo) |
|--------|-------------------|-------------------|
| Repos to maintain | 2 | 1 |
| Docker images | 2 | 1 |
| ECR repositories | 2 | 1 |
| CI pipelines | 3 (framework: 1, runner: 2) | 3 (same count, unified repo) |
| Dockerfiles | 2 | 1 |
| `.gitignore` files | 2 | 1 |
| `.env.example` files | 2 | 1 |
| Homebrew dependency | Yes (framework) | No (eliminated) |
| reconuser complexity | Yes (framework) | No (root + IS_SANDBOX=1) |
| Toolchain duplication | Yes (both installed foundry, echidna, medusa separately) | No (installed once) |
