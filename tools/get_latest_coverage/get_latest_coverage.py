"""Find the latest functions-missing-covg file and create a -latest.json copy."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def find_latest_coverage_file(magic_dir: Path) -> Path | None:
    """Find the most recent functions-missing-covg-{timestamp}.json file.

    Args:
        magic_dir: Path to the magic directory

    Returns:
        Path to the most recent coverage file, or None if not found
    """
    # Find all functions-missing-covg files (exclude -grouped- and -latest)
    pattern = "functions-missing-covg-*.json"
    all_matches = list(magic_dir.glob(pattern))

    # Filter out -grouped- and -latest files
    matches = [
        m for m in all_matches
        if '-grouped-' not in m.name and m.name != 'functions-missing-covg-latest.json'
    ]

    if not matches:
        return None

    # Extract timestamps and sort
    timestamped_files = []
    timestamp_pattern = re.compile(r'-(\d+)\.json$')

    for match in matches:
        ts_match = timestamp_pattern.search(match.name)
        if ts_match:
            timestamp = int(ts_match.group(1))
            timestamped_files.append((timestamp, match))

    if not timestamped_files:
        return None

    # Sort by timestamp descending (newest first)
    timestamped_files.sort(key=lambda x: x[0], reverse=True)

    return timestamped_files[0][1]


def main() -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Find the latest coverage file and create a -latest.json copy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  get-latest-coverage --return-json

This will:
  1. Find the most recent functions-missing-covg-{timestamp}.json file in magic/
  2. Create/update functions-missing-covg-latest.json with the same content
  3. Return JSON with metadata about the operation
        """,
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--return-json",
        action="store_true",
        help="Return JSON output to stdout",
    )

    args = parser.parse_args()

    # Find magic directory in current working directory
    magic_dir = Path.cwd() / "magic"
    if not magic_dir.is_dir():
        print(f"Error: Magic directory not found: {magic_dir}", file=sys.stderr)
        return 1

    # Find the latest coverage file
    latest_file = find_latest_coverage_file(magic_dir)

    if latest_file is None:
        print("Error: No coverage files found in magic/ directory", file=sys.stderr)
        return 1

    if args.verbose and not args.return_json:
        print(f"Found latest coverage file: {latest_file}")

    # Read the content
    try:
        with open(latest_file) as f:
            coverage_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {latest_file}: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        return 1

    if args.return_json:
        # Output the coverage data itself for workflow capture
        print(json.dumps(coverage_data, indent=2))
    else:
        # Write to -latest.json file
        latest_path = magic_dir / "functions-missing-covg-latest.json"
        try:
            with open(latest_path, "w") as f:
                json.dump(coverage_data, f, indent=2)
        except Exception as e:
            print(f"Error writing to {latest_path}: {e}", file=sys.stderr)
            return 1

        print(f"Created/updated: {latest_path}")
        if args.verbose:
            print(f"  Source: {latest_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
