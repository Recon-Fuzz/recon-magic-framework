"""CLI entry point for the build-info filter tool."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def filter_build_info_file(input_path: Path, output_path: Path | None = None, verbose: bool = False) -> tuple[Path, dict]:
    """
    Filter build-info JSON to only include sources with valid AST data.

    Args:
        input_path: Path to the input build-info JSON file
        output_path: Optional path to the output filtered JSON file
        verbose: If True, print detailed information to stderr

    Returns:
        Tuple of (output_path, stats_dict)

    Raises:
        FileNotFoundError: If input file doesn't exist
        json.JSONDecodeError: If input file is not valid JSON
    """
    # Read the build-info JSON
    with open(input_path, 'r') as f:
        data = json.load(f)

    # Get input and output sources
    input_sources = data.get('input', {}).get('sources', {})
    ast_output = data.get('output', {}).get('sources', {})

    # Filter to only include sources that have valid AST data
    filtered_input_sources = {}
    filtered_output_sources = {}
    removed_sources = []

    for source_path, source_data in input_sources.items():
        # Check if this source has valid AST data
        if source_path in ast_output:
            ast = ast_output[source_path].get('ast', {})
            if ast and 'nodeType' in ast:
                filtered_input_sources[source_path] = source_data
                filtered_output_sources[source_path] = ast_output[source_path]
            else:
                removed_sources.append(source_path)
        else:
            removed_sources.append(source_path)

    # Update the data
    data['input']['sources'] = filtered_input_sources
    data['output']['sources'] = filtered_output_sources

    # Determine output path
    if output_path is None:
        output_path = input_path.parent / f"{input_path.stem}.filtered{input_path.suffix}"

    # Save filtered version
    with open(output_path, 'w') as f:
        json.dump(data, f)

    # Prepare stats
    stats = {
        'input_sources': len(input_sources),
        'output_sources': len(filtered_input_sources),
        'removed_sources': len(removed_sources),
        'removed_files': removed_sources
    }

    # Print summary to stderr
    if verbose:
        print(f"✅ Filtered build-info: {len(removed_sources)} sources removed", file=sys.stderr)
        print(f"   Input:  {len(input_sources)} sources", file=sys.stderr)
        print(f"   Output: {len(filtered_input_sources)} sources", file=sys.stderr)

        if removed_sources and len(removed_sources) <= 15:
            print(f"   Removed: {', '.join(removed_sources)}", file=sys.stderr)

    return output_path, stats


def main() -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Filter Forge build-info JSON to remove sources without AST data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  filter-build-info out/build-info/abc123.json
  filter-build-info out/build-info/abc123.json --output filtered.json
  filter-build-info out/build-info/abc123.json --verbose

This tool removes sources without valid AST data (like foundry-pp preprocessor files)
to prevent sol-expand from failing during context extraction.
        """,
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="Path to the input build-info JSON file",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Path to the output filtered JSON file (default: <input>.filtered.json)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output to stderr",
    )

    args = parser.parse_args()

    # Validate input file exists
    if not args.input_file.exists():
        print(f"Error: Input file not found: {args.input_file}", file=sys.stderr)
        return 1

    if not args.input_file.is_file():
        print(f"Error: Input path is not a file: {args.input_file}", file=sys.stderr)
        return 1

    # Process the file
    try:
        output_path, stats = filter_build_info_file(args.input_file, args.output, args.verbose)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in input file: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Print output path to stdout (for use in shell pipelines)
    print(output_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
