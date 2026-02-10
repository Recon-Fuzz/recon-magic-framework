# Stateful Fuzzing Campaign Dictionary Creation

## Input

I'm reviewing the code so I can perform stateful fuzzing with echidna and foundry on it using the Chimera framework.

I need to run a tool to populate a dictionary of contracts and variables.

Please do the following:
1) Clean up the out folder for foundry
2) Build with --build-info (`forge build --build-info`)
3) Run the tool `npx recon-generate dictionary`

## Output

`recon-dictionary.json` is created.

Move it to `magic/recon-dictionary.json`