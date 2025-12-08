# filter-build-info

Filter Forge build-info JSON files to remove sources without valid AST data.

## Purpose

This tool solves a common issue when using `sol-expand` with Forge build artifacts: Foundry generates internal preprocessor files (in the `foundry-pp/` directory) that lack AST data. When `sol-expand` tries to process these files, it fails with:

```
Error: Unable to detect reader configuration for entry "foundry-pp/DeployHelper*.sol"
```

This tool filters the build-info JSON to remove such problematic sources before passing it to `sol-expand`.

## Installation

Install with uv:

```bash
uv tool install --editable ./tools/filter_build_info
```

## Usage

### Basic Usage

```bash
filter-build-info out/build-info/abc123.json
```

This creates `out/build-info/abc123.filtered.json` with sources lacking AST data removed.

### Specify Output Path

```bash
filter-build-info out/build-info/abc123.json --output filtered.json
```

### Verbose Mode

```bash
filter-build-info out/build-info/abc123.json --verbose
```

### In Shell Pipelines

The tool outputs the filtered file path to stdout, making it easy to use in pipelines:

```bash
FILTERED=$(filter-build-info $(find out/build-info -name '*.json' | head -1))
sol-expand --extract-context "$FILTERED"
```

## What Gets Filtered

The tool removes sources that appear in the build-info's input sources but lack valid AST data in the output sources. This typically includes:

- **foundry-pp files**: Foundry's internal preprocessor files (e.g., `foundry-pp/DeployHelper*.sol`)
- **Library-only files**: Files that don't have complete AST representations

## Exit Codes

- `0`: Success
- `1`: Error (file not found, invalid JSON, etc.)
