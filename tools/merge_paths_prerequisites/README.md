# merge-paths-prerequisites

Tool to merge paths and prerequisites for target functions. Combines output from `recon-generate@latest paths` and `setup-phase-1` agent.

## Installation

```bash
uv tool install -e .
```

## Usage

```bash
# Default usage (reads from magic/ directory)
merge-paths-prerequisites

# Custom paths
merge-paths-prerequisites \
  --paths-file magic/recon-paths.json \
  --prerequisites-file magic/function-sequences.json \
  --output-file magic/merged-paths-prerequisites.json

# Output to stdout as JSON
merge-paths-prerequisites --return-json
```

## Output Format

The tool produces a unified JSON structure combining paths and prerequisites:

```json
{
  "function_name": {
    "prerequisite_functions": ["func1", "func2"],
    "paths": [
      "condition1 && condition2 && ...",
      "condition3 && condition4 && ..."
    ]
  }
}
```

## Parameters

- `--paths-file`: Path to the recon-paths.json file (default: `magic/recon-paths.json`)
- `--prerequisites-file`: Path to the function-sequences.json file (default: `magic/function-sequences.json`)
- `--output-file`: Path to write merged output (default: `magic/merged-paths-prerequisites.json`)
- `--return-json`: Return JSON output to stdout instead of writing to file
