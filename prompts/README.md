# AI Agent Primers 
Inspired by [this repo](https://github.com/devdacian/ai-auditor-primers/tree/main), this repo hosts primers that can be used to give AI agents context that allows them to perform specific tasks. 

## Usage

You can add this repo as a submodule inside your existing project to have access to all of the workflows provided in it:

```bash
git submodule add https://github.com/Recon-Fuzz/ai-agent-primers .claude
```

## Workflows

[Slash commands](https://docs.anthropic.com/en/docs/claude-code/slash-commands) are used for running individual workflows.

Because the current setup workflow requires a human in the loop for scaffolding the suite setup, the setup workflow is broken into two parts. 
Currently the following two commands are used for the invariant testing setup process:

```bash
# Start the setup workflow up to the point of scaffolding
/initial_setup

# Start the setup workflow to expand and confirm that the setup works correctly
/continued_setup
```

> **Note**: You must run the slash commands from the directory containing the `.claude` directory for slash commands to work.

Additional workflows can be created by defining an additional master prompt in a file in the `commands/` directory.  

## Agent-Based Workflows

The `/init-setup` and `/exe-setup` commands break their workflows into subtasks performed by different agents to minimize context bloat. 

Agents can also be invoked directly using a prompt that explicitly mentions the name of the agent to use. 

**When adding additional agents you MUST use the recommended methods from Anthropic either directly through the [`/agents`]((https://docs.anthropic.com/en/docs/claude-code/sub-agents#managing-subagents)) command or using [`echo`](https://docs.anthropic.com/en/docs/claude-code/sub-agents#direct-file-management.** Creating agent configuration files through other means will usually cause claude code to not end up recognizing them.
- Once you've added a new subagent configuration file you need to restart claude code for it to recognize the new agent

The command orchestrate sequential workflows using specialized subagents located in `.claude/agents/` directory. Each phase must be completed successfully before proceeding to the next:

### Phase 0: Target Repo Compilation
- **Agent**: `coverage-phase-0` 
- **Purpose**: Convert Hardhat smart contract projects to Foundry or set up new Foundry projects from scratch
- **Target**: Foundry-based projects (converts Hardhat projects if needed)
- **Success Criteria**: `forge build` compiles successfully and artifacts are generated
- **Key Actions**: Analyze project structure, convert Hardhat to Foundry following official migration guide, configure foundry.toml, troubleshoot compilation issues

### Phase 1: Scaffolding
- **Agent**: `coverage-phase-0`
- **Purpose**: Identify and prepare contracts for invariant testing scaffolding
- **Requirements**: Manual scaffolding using the [Recon Invariant Testing Extension](https://getrecon.substack.com/p/the-recon-invariant-testing-extension)
- **Key Actions**: Analyze codebase to identify core contracts for testing and dependency contracts for mocking, create target_contracts.md file with scaffolding requirements
- **Output**: Structured target_contracts.md file ready for scaffolding process

### Phase 2: Setup & Compilation
- **Agent**: `coverage-phase-1` 
- **Purpose**: Modify Setup.sol contract to deploy and configure all target contracts for fuzzing
- **Focus Files**: `Setup.sol`
- **Success Criteria**: 
  - `forge build` succeeds
  - `forge test --match-contract CryticToFoundry -vvv` runs without reverts
  - `echidna . --contract CryticTester --config echidna.yaml --format text --test-limit 50000 --disable-slither --test-mode exploration` runs successfully
- **Key Actions**: Configure contract deployment with proper initialization, add actors and assets, set up approval arrays

### Phase 3: Setup & Feasibility
- **Agent**: `coverage-phase-2`
- **Purpose**: Identify functions to test and create a prioritized testing list
- **Focus Files**: `testing_priority.md`
- **Key Actions**: 
  - Identify all public functions in `/targets` (excluding AdminTargets, ManagersTargets, DoomsdayTargets)
  - Create unordered list with function prerequisites
  - Order functions by complexity (least prerequisites first)
- **Success Criteria**: Structured testing_priority.md file with ordered function list

### Phase 4: Setup & Feasibility Testing
- **Agent**: `coverage-phase-3`
- **Purpose**: Implement tests from testing_priority.md and confirm setup allows all target functions to be called correctly
- **Focus Files**: `CryticToFoundry.sol`, `AdminTargets.sol`, `Setup.sol`
- **Key Actions**: 
  - Move admin/privileged functions to AdminTargets with asAdmin modifier
  - Create Foundry unit tests for each function in testing_priority.md
  - Handle test failures by adding prerequisites or fixing setup issues
- **Success Criteria**: All tests pass OR failing tests have documented acceptable revert reasons, Echidna runs successfully with test limit reached

### Phase 5: Initial Coverage Assessment
- **Agent**: `coverage-phase-3` 
- **Purpose**: Run initial Echidna fuzzing and assess base coverage levels
- **Runtime**: 30-minute initial fuzzing session
- **Command**: `echidna . --contract CryticTester --config echidna.yaml --format text --timeout 1800 --test-limit 99999999999999999999 --disable-slither`
- **Key Actions**: 
  - Run initial 30-minute Echidna session
  - Check coverage report for basic function coverage
  - Assess if Phase 2.1 setup was successful
- **Success Criteria**: Return "Phase 2.1 was a success" if basic functions are covered, or "Phase 2.1 was incorrect" with specific issues

### Phase 6: Coverage Optimization
- **Agent**: `coverage-phase-4` 
- **Purpose**: Write clamped handlers to improve coverage efficiency
- **Focus Files**: Files in `recon/targets/` directory
- **Key Actions**: 
  - Review latest Echidna coverage report
  - Write clamped handlers with reduced, hardcoded inputs for hard-to-reach code
  - Only add handlers for genuinely difficult coverage areas
- **Success Criteria**: 
  - `forge test` runs successfully
  - 4-hour Echidna run completes: `echidna . --contract CryticTester --config echidna.yaml --format text --timeout 14400 --test-limit 99999999999999999999 --disable-slither`

## Multi-Agent Workflows 

The current configuration allows running 3 agents in parallel and is initialized using the `/init-parallel` slash command. The number of agents to run in parallel can be configured by modifying the number of working trees that are setup in the `init-parallel.md` file. 

To run the agents in parallel for a given agent defined in the `agents/` directory use the `/exe-parallel 3 <agent-to-use>` command with the `<agent-to-use>` argument specifying which of the agents to use from the `agents/` directory.


