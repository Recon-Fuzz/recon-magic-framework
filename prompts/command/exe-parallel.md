# Parallel Task Version Execution

## Variables
NUMER_OF_PARALLEL_WORKTREES: $ARGUMENTS
AGENT_TO_USE: $ARGUMENTS

## Instructions

We're going to create NUMER_OF_PARALLEL_WORKTREES AGENT_TO_USE agents to create NUMER_OF_PARALLEL_WORKTREES versions of the same `Setup` contract in parallel.

This allows us to concurrently implement different setups so we can test and validate each subagent's changes in isolation then pick the best changes. 

The first subagent will run in trees/setup-1/
The second subagent will run in trees/setup-2/
...
The last subagent will run in trees/setup-<NUMER_OF_PARALLEL_WORKTREES>/

The code in trees/setup<i> will be identical to the code in the current branch. It will be setup and ready for you to implement the setup end-to-end.
