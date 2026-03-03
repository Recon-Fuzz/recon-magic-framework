# Fuzzing Scouting Workflow - Input/Output Specification

## Step 1: Phase 0 - Foundry Migration & Compilation

**Type:** Task (OPENCODE - Agent)

**Inputs:**
- Agent: `./.opencode/agent/scouting-phase-0.md`
- Files: Project structure, `package.json`, `hardhat.config.js/ts`, `foundry.toml`, contract source files

**Outputs:**
- File: `foundry.toml` (created if migrating from Hardhat)
- Directory: `out/` (Forge build artifacts)
- File: `COMPILATION_FAILED.md` (created only if compilation fails)

---

## Step 2: Compilation Check Decision

**Type:** Decision (READ_FILE)

**Inputs:**
- Pattern: `COMPILATION_FAILED.md`

**Decision Logic:**
- If file exists (value = 1): STOP workflow
- If file does not exist (value = 0): Continue to Step 3

---

## Step 3: Phase 1 - Contract Analysis & Scaffolding Preparation

**Type:** Task (OPENCODE - Agent)

**Inputs:**
- Agent: `./.opencode/agent/scouting-phase-1.md`
- Directory: `out/` (build artifacts)
- Files: `src/**/*.sol`, `contracts/**/*.sol`

**Outputs:**
- File: `magic/contracts-to-scaffold.json`

**Output JSON Structure:**
```json
{
  "source_contracts": [
    "Vault",
    "LendingPool",
    "InterestRateModel",
    "PriceOracle"
  ],
  "mocked_contracts": [
    "ERC20",
    "ChainlinkOracle",
    "UniswapRouter"
  ]
}
```
