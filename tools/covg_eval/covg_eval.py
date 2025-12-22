"""CLI entry point for the coverage evaluation tool."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def find_latest_lcov(echidna_dir: Path) -> tuple[Path, str]:
    """Find the most recent LCOV file in the echidna directory.

    Returns:
        A tuple of (lcov_path, timestamp_string).

    Raises:
        FileNotFoundError: If no LCOV files are found.
    """
    lcov_files = list(echidna_dir.glob("covered.*.lcov"))
    if not lcov_files:
        raise FileNotFoundError(f"No LCOV files found in {echidna_dir}")

    # Extract timestamps and find the maximum
    pattern = re.compile(r"covered\.(\d+)\.lcov$")
    timestamped_files: list[tuple[int, Path]] = []

    for f in lcov_files:
        match = pattern.search(f.name)
        if match:
            timestamp = int(match.group(1))
            timestamped_files.append((timestamp, f))

    if not timestamped_files:
        raise FileNotFoundError(f"No valid LCOV files with timestamps found in {echidna_dir}")

    # Sort by timestamp descending and get the most recent
    timestamped_files.sort(key=lambda x: x[0], reverse=True)
    timestamp, lcov_path = timestamped_files[0]
    return lcov_path, str(timestamp)


def parse_lcov_file(lcov_path: Path) -> dict[str, dict]:
    """Parse an LCOV file and extract coverage data per source file.

    Returns:
        A dict mapping source file paths to their coverage data.
    """
    sources: dict[str, dict] = {}
    current_source: str | None = None
    current_data: dict | None = None

    with open(lcov_path) as f:
        for line in f:
            line = line.strip()

            if line.startswith("SF:"):
                # Source file path
                current_source = line[3:]
                current_data = {
                    "line_coverage": {},  # line_number -> hit_count
                }
                sources[current_source] = current_data

            elif line.startswith("DA:") and current_data is not None:
                # Line coverage: DA:line_number,hit_count
                parts = line[3:].split(",")
                if len(parts) >= 2:
                    line_num = int(parts[0])
                    hits = int(parts[1])
                    current_data["line_coverage"][line_num] = hits

            elif line == "end_of_record":
                current_source = None
                current_data = None

    return sources


def find_functions_in_source(source_path: str) -> dict[str, tuple[int, int]]:
    """Parse a Solidity source file to find function definitions and their line ranges.

    Args:
        source_path: Path to the Solidity source file.

    Returns:
        Dict mapping function names to (start_line, end_line) tuples.
    """
    try:
        with open(source_path) as f:
            lines = f.readlines()
    except FileNotFoundError:
        return {}

    functions: dict[str, tuple[int, int]] = {}

    # Regex to match Solidity function definitions
    # Matches: function functionName(...) with various modifiers
    func_pattern = re.compile(
        r'^\s*function\s+(\w+)\s*\('
    )

    # Also match modifier definitions
    modifier_pattern = re.compile(
        r'^\s*modifier\s+(\w+)\s*[\(\{]'
    )

    i = 0
    while i < len(lines):
        line = lines[i]
        line_num = i + 1  # 1-indexed

        # Check for function definition
        func_match = func_pattern.match(line)
        modifier_match = modifier_pattern.match(line)

        match = func_match or modifier_match
        if match:
            func_name = match.group(1)
            start_line = line_num

            # Find the function body by looking for opening brace
            # Function might span multiple lines before the body starts
            brace_count = 0
            body_started = False
            end_line = start_line

            for j in range(i, len(lines)):
                check_line = lines[j]

                for char in check_line:
                    if char == "{":
                        brace_count += 1
                        body_started = True
                    elif char == "}":
                        brace_count -= 1
                        if body_started and brace_count == 0:
                            end_line = j + 1  # 1-indexed
                            break

                if body_started and brace_count == 0:
                    break

            functions[func_name] = (start_line, end_line)

        i += 1

    return functions


def is_internal_or_private_function(source_path: str, func_name: str, start_line: int) -> bool:
    """Check if a function is internal or private by examining its visibility modifier.

    Args:
        source_path: Path to the Solidity source file.
        func_name: Name of the function.
        start_line: Starting line number of the function (1-indexed).

    Returns:
        True if the function is internal or private, False otherwise.
    """
    try:
        with open(source_path) as f:
            lines = f.readlines()
    except FileNotFoundError:
        return False

    # Read the function signature (may span multiple lines until we hit '{')
    signature = ""
    for i in range(start_line - 1, len(lines)):
        line = lines[i]
        signature += " " + line.strip()
        if "{" in line:
            break

    # Check for visibility modifiers
    # Internal or private functions are marked with 'internal' or 'private' keywords
    # Common pattern: function name(...) <visibility> <modifiers> { ... }
    if re.search(r'\b(internal|private)\b', signature):
        return True

    return False


def find_function_body_start(source_path: str, start_line: int) -> int:
    """Find the line where the function body starts (after the opening brace).

    Args:
        source_path: Path to the Solidity source file.
        start_line: Function definition start line (1-indexed).

    Returns:
        Line number where the function body starts (line after '{'), or start_line if not found.
    """
    try:
        with open(source_path) as f:
            lines = f.readlines()
    except FileNotFoundError:
        return start_line

    # Search for the first opening brace starting from start_line
    for i in range(start_line - 1, len(lines)):
        if '{' in lines[i]:
            # Return the line AFTER the opening brace (i + 2 because i is 0-indexed)
            # This excludes both the signature and the line with the opening brace
            return i + 2  # Return 1-indexed line number of the line after '{'

    # If no opening brace found, return start_line
    return start_line


def analyze_function_coverage(
    line_coverage: dict[int, int],
    start_line: int,
    end_line: int,
    source_path: str | None = None,
) -> tuple[float, list[int]]:
    """Analyze line coverage for a specific function.

    Args:
        line_coverage: Dict mapping line numbers to hit counts.
        start_line: Function start line (1-indexed).
        end_line: Function end line (1-indexed).
        source_path: Optional path to the source file (used to exclude signature lines).

    Returns:
        A tuple of (coverage_percentage, list_of_uncovered_lines).
    """
    # Find where the function body actually starts (first '{')
    # This excludes the function signature from coverage analysis
    body_start_line = start_line
    if source_path:
        body_start_line = find_function_body_start(source_path, start_line)

    # Extract lines within function body range that have coverage data
    # Exclude signature lines (before the opening brace)
    function_lines = {
        ln: hits
        for ln, hits in line_coverage.items()
        if body_start_line <= ln <= end_line
    }

    if not function_lines:
        # No instrumented lines in this function range
        return 100.0, []

    total_lines = len(function_lines)
    covered_lines = sum(1 for hits in function_lines.values() if hits > 0)
    uncovered = [ln for ln, hits in function_lines.items() if hits == 0]

    percentage = (covered_lines / total_lines) * 100 if total_lines > 0 else 100.0

    return percentage, sorted(uncovered)


def group_consecutive_lines(lines: list[int]) -> list[str]:
    """Group consecutive line numbers into ranges.

    Args:
        lines: Sorted list of line numbers.

    Returns:
        List of range strings like "10-15" or "20" for single lines.
    """
    if not lines:
        return []

    ranges: list[str] = []
    start = lines[0]
    end = lines[0]

    for line in lines[1:]:
        if line == end + 1:
            end = line
        else:
            if start == end:
                ranges.append(str(start))
            else:
                ranges.append(f"{start}-{end}")
            start = line
            end = line

    # Don't forget the last range
    if start == end:
        ranges.append(str(start))
    else:
        ranges.append(f"{start}-{end}")

    return ranges


def extract_code_snippets(
    source_path: str,
    uncovered_lines: list[int],
    line_coverage: dict[int, int],
) -> list[dict[str, str | int | list[str]]]:
    """Extract code snippets for uncovered lines, grouped by chunks separated by covered lines.

    A new chunk starts whenever there's a covered line between uncovered lines.
    This means if there are uncovered lines 10, 11, 12 (covered), 13, 14, this will create
    two chunks: [10, 11] and [13, 14].

    Args:
        source_path: Path to the Solidity source file.
        uncovered_lines: Sorted list of uncovered line numbers.
        line_coverage: Dict mapping line numbers to hit counts.

    Returns:
        List of dicts, each containing:
            - "line_range": string like "10-15" or "20"
            - "last_covered_line": int or None, the last covered line before this group
            - "code": list of strings formatted as "lineNum: code content"
                     (skips empty/whitespace-only lines)
                     Includes the last covered line with [LAST COVERED] prefix if found
    """
    if not uncovered_lines:
        return []

    try:
        with open(source_path) as f:
            lines = f.readlines()
    except FileNotFoundError:
        return []

    # Group uncovered lines into chunks separated by covered lines
    # A new chunk starts when there's a covered line between uncovered lines
    groups: list[list[int]] = []
    current_group = [uncovered_lines[0]]

    for line_num in uncovered_lines[1:]:
        # Check if there are any covered lines between the last uncovered line and this one
        has_covered_line_between = False
        for check_line in range(current_group[-1] + 1, line_num):
            # A line is covered if it exists in line_coverage and has hits > 0
            if check_line in line_coverage and line_coverage[check_line] > 0:
                has_covered_line_between = True
                break

        if has_covered_line_between:
            # Start a new chunk because there's a covered line in between
            groups.append(current_group)
            current_group = [line_num]
        else:
            # Continue the current chunk
            current_group.append(line_num)

    groups.append(current_group)

    # Extract code for each group
    result = []
    for group in groups:
        # Create line range string
        if len(group) == 1:
            line_range = str(group[0])
        else:
            line_range = f"{group[0]}-{group[-1]}"

        # Find the last covered line before this group
        first_uncovered = group[0]
        last_covered_line = None

        # Search backwards from the first uncovered line to find the last covered line
        for line_num in range(first_uncovered - 1, 0, -1):
            if line_num in line_coverage and line_coverage[line_num] > 0:
                last_covered_line = line_num
                break

        # Extract code, including the last covered line if found
        code_lines = []

        # Add the last covered line first, if found
        if last_covered_line is not None and last_covered_line <= len(lines):
            code = lines[last_covered_line - 1].rstrip()
            if code.strip():
                code_lines.append(f"{last_covered_line}: [LAST COVERED] {code}")

        # Add the uncovered lines
        for line_num in group:
            if line_num <= len(lines):
                code = lines[line_num - 1].rstrip()  # Remove trailing whitespace
                # Only include non-empty lines
                if code.strip():
                    code_lines.append(f"{line_num}: {code}")

        # Only add this group if it has code (not all whitespace)
        if code_lines:
            result.append({
                "line_range": line_range,
                "last_covered_line": last_covered_line,
                "code": code_lines,
            })

    return result


def parse_line_range(line_range: str) -> tuple[int, int]:
    """Parse a line range string like '66-130' or '17' into (start, end) tuple.

    Args:
        line_range: String like "66-130" or "17"

    Returns:
        Tuple of (start_line, end_line)
    """
    if '-' in line_range:
        start, end = line_range.split('-')
        return int(start), int(end)
    else:
        line = int(line_range)
        return line, line


def load_functions_to_cover(magic_dir: Path) -> dict[str, list[str]]:
    """Load the recon-coverage.json file and extract function names from line ranges.

    The recon-coverage.json format is:
    {
      "src/hub/Hub.sol": ["66-130", "133-173", ...],
      ...
    }

    This function parses the source files to find which functions are in those line ranges.

    Args:
        magic_dir: Path to the magic directory.

    Returns:
        Dict mapping contract names to lists of function names.

    Raises:
        FileNotFoundError: If the JSON file doesn't exist.
        json.JSONDecodeError: If the JSON is invalid.
    """
    json_path = magic_dir / "recon-coverage.json"
    with open(json_path) as f:
        data = json.load(f)

    result: dict[str, list[str]] = {}

    # data maps source_path -> list of line ranges
    for source_path, line_ranges in data.items():
        # Extract contract name from path (e.g., "src/hub/Hub.sol" -> "Hub")
        contract_name = Path(source_path).stem

        # Find all functions in this source file
        all_functions = find_functions_in_source(source_path)

        # Determine which functions overlap with the specified line ranges
        functions_to_cover = set()

        for line_range_str in line_ranges:
            range_start, range_end = parse_line_range(line_range_str)

            # Check which functions overlap with this range
            for func_name, (func_start, func_end) in all_functions.items():
                # Check if there's any overlap between the range and the function
                if not (range_end < func_start or range_start > func_end):
                    functions_to_cover.add(func_name)

        if functions_to_cover:
            result[contract_name] = sorted(list(functions_to_cover))

    return result


def is_interface_file(source_path: str) -> bool:
    """Check if a source path is an interface file.

    Interface files are identified by:
    1. Being in a directory named 'interfaces' or 'Interfaces' (case-insensitive)
    2. Having a filename starting with 'I' followed by an uppercase letter (e.g., IStabilityPool.sol)

    Args:
        source_path: Path to the source file.

    Returns:
        True if the file is an interface, False otherwise.
    """
    # Normalize path separators and convert to lowercase for case-insensitive checks
    path_lower = source_path.lower()

    # Check if path contains 'interfaces' directory
    if "/interfaces/" in path_lower or "\\interfaces\\" in path_lower:
        return True

    # Check if filename starts with 'I' followed by uppercase (common interface naming convention)
    # e.g., IStabilityPool.sol, IBorrowerOperations.sol
    filename = source_path.split("/")[-1].split("\\")[-1]  # Get filename from path
    if filename.startswith("I") and len(filename) > 1 and filename[1].isupper():
        return True

    return False


def find_source_for_contract(
    contract_name: str,
    lcov_sources: dict[str, dict],
) -> str | None:
    """Find the source file path for a given contract name.

    This function looks for implementation files only, ignoring interface files.
    It searches for files ending with the contract name, excluding:
    - Files in 'interfaces' or 'Interfaces' directories
    - Files with names starting with 'I' followed by uppercase (e.g., IContractName.sol)

    Args:
        contract_name: Name of the contract (without .sol extension).
        lcov_sources: Dict of source paths from LCOV parsing.

    Returns:
        The full source path if found, None otherwise.
    """
    # Look for exact filename match: /{ContractName}.sol
    # The leading slash ensures we match the exact filename, not a substring.
    # This automatically excludes:
    #   - Interface files (e.g., IStabilityPool.sol won't match /StabilityPool.sol)
    #   - Test helpers (e.g., StabilityPoolTargets.sol won't match /StabilityPool.sol)
    target = f"/{contract_name}.sol"

    for source_path in lcov_sources:
        if source_path.endswith(target):
            return source_path

    return None


def main() -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Evaluate function coverage from Echidna LCOV reports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  covg-eval magic/ echidna/

This will:
  1. Read recon-coverage.json from the magic/ directory
  2. Parse source files to identify functions in the specified line ranges
  3. Find the most recent LCOV file in echidna/
  4. Evaluate coverage for each identified function
  5. Write results to magic/functions-missing-covg-N.json
        """,
    )
    parser.add_argument(
        "magic_dir",
        type=Path,
        help="Path to the magic directory containing recon-coverage.json",
    )
    parser.add_argument(
        "echidna_dir",
        type=Path,
        help="Path to the echidna directory containing LCOV files",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--return-json",
        action="store_true",
        help="Return JSON output to stdout instead of writing to file",
    )

    args = parser.parse_args()

    magic_dir: Path = args.magic_dir
    echidna_dir: Path = args.echidna_dir
    verbose: bool = args.verbose

    # Validate directories
    if not magic_dir.is_dir():
        print(f"Error: Magic directory not found: {magic_dir}", file=sys.stderr)
        return 1

    if not echidna_dir.is_dir():
        print(f"Error: Echidna directory not found: {echidna_dir}", file=sys.stderr)
        return 1

    # Load functions to cover
    try:
        functions_to_cover = load_functions_to_cover(magic_dir)
    except FileNotFoundError:
        print(
            f"Error: recon-coverage.json not found in {magic_dir}",
            file=sys.stderr,
        )
        return 1
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in recon-coverage.json: {e}", file=sys.stderr)
        return 1

    # Determine output stream for verbose messages
    verbose_out = sys.stderr if args.return_json else sys.stdout

    if verbose:
        print(f"Loaded {sum(len(v) for v in functions_to_cover.values())} functions to analyze", file=verbose_out)

    # Find the most recent LCOV file
    try:
        lcov_path, timestamp = find_latest_lcov(echidna_dir)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if verbose:
        print(f"Using LCOV file: {lcov_path}", file=verbose_out)

    # Parse the LCOV file
    lcov_sources = parse_lcov_file(lcov_path)

    if verbose:
        print(f"Found {len(lcov_sources)} source files in LCOV file", file=verbose_out)

    # Analyze coverage for each function
    missing_coverage: list = []

    for contract_name, function_names in functions_to_cover.items():
        # Find the source file for this contract
        source_path = find_source_for_contract(contract_name, lcov_sources)

        if source_path is None:
            print(
                f"Warning: Contract '{contract_name}' not found in LCOV file",
                file=sys.stderr,
            )
            continue

        if verbose:
            print(f"Analyzing {contract_name} from {source_path}", file=verbose_out)

        # Get line coverage data for this source
        line_coverage = lcov_sources[source_path]["line_coverage"]

        # Parse the source file to find function locations
        functions = find_functions_in_source(source_path)

        if verbose:
            print(f"  Found {len(functions)} functions in source file", file=verbose_out)

        for func_name in function_names:
            if func_name not in functions:
                print(
                    f"Warning: Function '{func_name}' not found in {contract_name}",
                    file=sys.stderr,
                )
                continue

            start_line, end_line = functions[func_name]

            percentage, uncovered_lines = analyze_function_coverage(
                line_coverage,
                start_line,
                end_line,
                source_path,
            )

            if verbose:
                print(f"  {func_name} (lines {start_line}-{end_line}): {percentage:.2f}% coverage", file=verbose_out)

            if percentage < 100.0:
                # Extract code snippets for uncovered lines
                code_snippets = extract_code_snippets(source_path, uncovered_lines, line_coverage)

                # Create a separate entry for each uncovered section
                for snippet in code_snippets:
                    missing_coverage.append({
                        "function": func_name,
                        "contract": contract_name,
                        "source_file": source_path,
                        "function_range": {
                            "start": start_line,
                            "end": end_line,
                        },
                        "uncovered_code": snippet,
                    })

    # Filter out internal/private functions to avoid redundant reporting
    # Internal/private functions can only be called from within the same contract,
    # so if they're uncovered, it's because their caller is uncovered.
    # We filter them out to show only the root cause (the uncovered caller).
    if verbose:
        print(f"Filtering internal/private functions...", file=verbose_out)
        print(f"  Before filtering: {len(missing_coverage)} uncovered sections", file=verbose_out)

    filtered_coverage = []
    for entry in missing_coverage:
        func_name = entry["function"]
        source_path = entry["source_file"]
        start_line = entry["function_range"]["start"]

        # Check if this function is internal or private
        is_internal = is_internal_or_private_function(source_path, func_name, start_line)

        if is_internal:
            if verbose:
                print(f"  Filtering out internal/private function: {func_name}", file=verbose_out)
            # Skip this entry - it's an internal/private function that can only
            # be called from within the contract, so covering its caller will
            # automatically cover this function
            continue

        # Keep this entry - it's a public/external function that needs direct coverage
        filtered_coverage.append(entry)

    if verbose:
        print(f"  After filtering: {len(filtered_coverage)} uncovered sections", file=verbose_out)

    missing_coverage = filtered_coverage

    # Prepare output data
    # Count unique functions with missing coverage
    unique_functions_with_issues = len(set(entry["function"] for entry in missing_coverage))

    output_data = {
        "timestamp": timestamp,
        "lcov_file": str(lcov_path),
        "missing_coverage": missing_coverage,
        "summary": {
            "functions_analyzed": sum(len(v) for v in functions_to_cover.values()),
            "functions_with_missing_coverage": unique_functions_with_issues,
            "uncovered_sections": len(missing_coverage),
            "full_coverage": len(missing_coverage) == 0
        }
    }

    # Return JSON or write to file
    if args.return_json:
        print(json.dumps(output_data, indent=2))
        return 0
    else:
        # Write output file (backward compatible)
        output_path = magic_dir / f"functions-missing-covg-{timestamp}.json"
        with open(output_path, "w") as f:
            json.dump(missing_coverage, f, indent=2)

        print(f"Results written to: {output_path}")

        if missing_coverage:
            unique_funcs = len(set(entry["function"] for entry in missing_coverage))
            print(f"Found {unique_funcs} functions with < 100% coverage ({len(missing_coverage)} uncovered sections)")
        else:
            print("All functions have 100% coverage!")

        return 0


if __name__ == "__main__":
    sys.exit(main())
