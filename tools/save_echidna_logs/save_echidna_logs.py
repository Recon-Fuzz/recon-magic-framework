#!/usr/bin/env python3
"""
Tool to capture and save Echidna logs for later analysis.
Reads from the most recent echidna log file and saves to magic/ directory.
"""

import glob
import json
import os
import sys
from pathlib import Path


def find_latest_echidna_log(logs_dir: str = "./logs") -> str | None:
    """Find the most recent echidna log file."""
    pattern = os.path.join(logs_dir, "*echidna*.log")
    log_files = glob.glob(pattern)

    if not log_files:
        return None

    # Get the most recent file
    latest_log = max(log_files, key=os.path.getmtime)
    return latest_log


def parse_echidna_output(log_content: str) -> dict:
    """Parse Echidna output and extract key information."""
    result = {
        "raw_output": log_content,
        "success": "PASSED" in log_content or "All tests passed" in log_content,
        "failed_tests": [],
        "errors": [],
        "coverage_info": None
    }

    # Extract failed tests
    for line in log_content.split("\n"):
        if "FAILED" in line or "failed!" in line:
            result["failed_tests"].append(line.strip())
        if "Error:" in line or "error:" in line.lower():
            result["errors"].append(line.strip())

    return result


def save_echidna_logs(output_dir: str = "./magic", return_json: bool = False) -> int:
    """
    Save Echidna logs from the most recent run to magic/ directory.

    Args:
        output_dir: Directory to save output files
        return_json: If True, return JSON to stdout instead of writing files

    Returns:
        0 on success, 1 on failure
    """
    # Find latest log
    log_file = find_latest_echidna_log()

    if not log_file:
        if return_json:
            error_output = {
                "error": "No Echidna log files found in logs/",
                "success": False
            }
            print(json.dumps(error_output, indent=2))
        else:
            print("❌ No Echidna log files found in logs/")
        return 1

    if not return_json:
        print(f"📝 Found Echidna log: {log_file}")

    # Read log content
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        log_content = f.read()

    # Parse output
    parsed_data = parse_echidna_output(log_content)

    # Prepare output with metadata
    output_data = {
        "log_file": log_file,
        "parsed_data": parsed_data,
        "files_written": {}
    }

    # Return JSON or write to files
    if return_json:
        print(json.dumps(output_data, indent=2))
        return 0
    else:
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)

        # Save raw output
        output_file = os.path.join(output_dir, "echidna-output.txt")
        with open(output_file, 'w') as f:
            f.write(log_content)

        print(f"✅ Saved raw output to: {output_file}")

        # Save parsed JSON
        json_file = os.path.join(output_dir, "echidna-summary.json")
        with open(json_file, 'w') as f:
            json.dump(parsed_data, f, indent=2)

        print(f"✅ Saved parsed summary to: {json_file}")

        # Print summary
        if parsed_data["success"]:
            print("✅ Echidna run was successful")
        else:
            print("⚠️ Echidna run had issues")
            if parsed_data["failed_tests"]:
                print(f"   Failed tests: {len(parsed_data['failed_tests'])}")
            if parsed_data["errors"]:
                print(f"   Errors found: {len(parsed_data['errors'])}")

        return 0


def main():
    """Main entry point for the script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Save Echidna logs from the most recent run to magic/ directory"
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default="./magic",
        help="Output directory for saved logs (default: ./magic)"
    )
    parser.add_argument(
        "--return-json",
        action="store_true",
        help="Return JSON output to stdout instead of writing to files"
    )

    args = parser.parse_args()
    sys.exit(save_echidna_logs(args.output_dir, args.return_json))


if __name__ == "__main__":
    main()
