"""
Tool to analyze Echidna output, categorize errors, and determine next workflow steps.
Checks exit codes and log content to identify compilation errors vs other failures.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple


def find_echidna_log(log_path: str = "echidna-output.log") -> Optional[str]:
    """
    Find the Echidna log file.

    Args:
        log_path: Path to the Echidna log file

    Returns:
        Path to log file if it exists, None otherwise
    """
    if os.path.exists(log_path):
        return log_path

    # Try alternative locations
    alternatives = [
        "./echidna-output.log",
        "./logs/echidna-output.log",
        "./magic/echidna-output.log"
    ]

    for alt_path in alternatives:
        if os.path.exists(alt_path):
            return alt_path

    return None


def analyze_error_type(log_content: str) -> Tuple[str, Dict]:
    """
    Analyze log content to determine the type of error.

    Args:
        log_content: The full log output from Echidna

    Returns:
        Tuple of (error_type, error_details)
        error_type: 'compilation', 'setup', 'rpc', 'contract_not_found', 'unknown'
        error_details: Dictionary with specific error information
    """
    error_details = {
        "error_lines": [],
        "context": "",
        "suggested_action": ""
    }

    # Check for compilation errors (highest priority)
    if "CryticCompile:Error" in log_content:
        # Extract compilation error details
        lines = log_content.split('\n')
        for i, line in enumerate(lines):
            if "CryticCompile:Error" in line:
                # Get surrounding context
                start_idx = max(0, i - 2)
                end_idx = min(len(lines), i + 10)
                error_details["error_lines"] = lines[start_idx:end_idx]
                error_details["context"] = '\n'.join(lines[start_idx:end_idx])
                error_details["suggested_action"] = "trigger_compilation_fix_agent"
                break
        return "compilation", error_details

    # Check for unlinked libraries
    if "unlinked libraries" in log_content.lower() or "Error toCode" in log_content:
        error_details["context"] = "Unlinked libraries detected in contract bytecode"
        error_details["suggested_action"] = "stop"

        # Extract error details
        lines = log_content.split('\n')
        for i, line in enumerate(lines):
            if "unlinked libraries" in line.lower() or "Error toCode" in line:
                # Get surrounding context
                start_idx = max(0, i - 2)
                end_idx = min(len(lines), i + 10)
                error_details["error_lines"] = lines[start_idx:end_idx]
                error_details["context"] = '\n'.join(lines[start_idx:end_idx])
                break

        error_details["suggested_fix"] = (
            "Link libraries in echidna.yaml configuration:\n"
            "1. Add library deployment under 'deployContracts' section\n"
            "2. Add library addresses to cryticArgs with --libraries flag\n"
            "3. Example: cryticArgs: ['--libraries', 'MyLib:0x1234...']"
        )
        error_details["common_causes"] = [
            "Contract uses library functions but libraries are not linked",
            "Missing library deployment configuration in echidna.yaml",
            "Libraries need to be deployed before contract instantiation"
        ]
        return "unlinked_libraries", error_details

    # Check for setUp() function failure
    if "Calling the setUp() function failed" in log_content:
        error_details["context"] = "setUp() function failed during contract initialization"
        error_details["suggested_action"] = "generate_ai_summary"

        # Extract last 20 lines for context
        lines = log_content.split('\n')
        error_details["error_lines"] = lines[-20:] if len(lines) > 20 else lines

        # Common causes
        error_details["common_causes"] = [
            "Contract state initialization issues",
            "Missing or incorrect RPC configuration",
            "Out of gas during setup",
            "Reverting require statements in setUp()"
        ]
        return "setup", error_details

    # Check for RPC configuration errors
    if "ERROR: Requested RPC but it is not configured" in log_content:
        error_details["context"] = "RPC configuration is missing but required"
        error_details["suggested_action"] = "generate_ai_summary"

        # Find RPC-related lines
        lines = log_content.split('\n')
        rpc_lines = [line for line in lines if 'RPC' in line]
        error_details["error_lines"] = rpc_lines

        error_details["suggested_fix"] = "Add RPC URL to echidna.yaml configuration file"
        return "rpc", error_details

    # Check for contract not found
    if "could not find contract" in log_content.lower():
        error_details["context"] = "Specified contract could not be found"
        error_details["suggested_action"] = "generate_ai_summary"

        # Extract contract-related lines
        lines = log_content.split('\n')
        contract_lines = [line for line in lines if 'contract' in line.lower()]
        error_details["error_lines"] = contract_lines[-10:] if len(contract_lines) > 10 else contract_lines
        return "contract_not_found", error_details

    # Unknown error type
    error_details["context"] = "Unrecognized error pattern"
    error_details["suggested_action"] = "generate_ai_summary"

    # Get last 30 lines for context
    lines = log_content.split('\n')
    error_details["error_lines"] = lines[-30:] if len(lines) > 30 else lines

    return "unknown", error_details


def create_error_summary(error_type: str, error_details: Dict, exit_code: int) -> Dict:
    """
    Create a structured error summary for AI processing or workflow decisions.

    Args:
        error_type: Type of error detected
        error_details: Details about the error
        exit_code: Echidna's exit code

    Returns:
        Dictionary with complete error summary
    """
    summary = {
        "echidna_exit_code": exit_code,
        "error_type": error_type,
        "requires_compilation_fix": 1 if error_type == "compilation" else 0,
        "error_details": error_details,
        "workflow_action": error_details.get("suggested_action", "stop")
    }

    # Add human-readable description
    descriptions = {
        "compilation": "Solidity compilation failed. The contracts have syntax errors or dependency issues.",
        "unlinked_libraries": "Contract bytecode contains unlinked library references. Libraries must be deployed and linked before Echidna can run the contract.",
        "setup": "The setUp() function in the fuzzing harness failed to execute properly.",
        "rpc": "Echidna requires RPC access for mainnet forking but no RPC URL is configured.",
        "contract_not_found": "The specified contract could not be found in the compiled artifacts.",
        "unknown": "An unrecognized error occurred during Echidna execution."
    }

    summary["description"] = descriptions.get(error_type, "Unknown error")

    # Add timestamp
    from datetime import datetime
    summary["timestamp"] = datetime.now().isoformat()

    return summary


def analyze_echidna_output(exit_code: int, log_file: Optional[str] = None, return_json: bool = False) -> int:
    """
    Main function to analyze Echidna output and determine workflow action.

    Args:
        exit_code: Echidna's exit code (0 for success, non-zero for failure)
        log_file: Path to Echidna log file (will search if not provided)
        return_json: If True, output JSON to stdout

    Returns:
        0: Success - continue workflow
        1: General failure - stop workflow
        2: Compilation error - trigger compilation fix agent
        3: Other error - generate AI summary and stop
    """

    # Handle successful execution
    if exit_code == 0:
        result = {
            "status": "success",
            "echidna_exit_code": 0,
            "error_type": None,  # Explicitly set to None for success case
            "workflow_action": "continue",
            "message": "Echidna completed successfully",
            "requires_compilation_fix": 0
        }

        # Check if coverage files were generated
        coverage_files = list(Path("echidna").glob("*.txt")) if Path("echidna").exists() else []
        if coverage_files:
            result["coverage_files"] = [str(f) for f in coverage_files]
            result["coverage_generated"] = True
        else:
            result["coverage_generated"] = False
            result["warning"] = "No coverage files found despite successful execution"

        # Add timestamp
        from datetime import datetime
        result["timestamp"] = datetime.now().isoformat()

        if return_json:
            print(json.dumps(result, indent=2))
        else:
            # Write file for standalone CLI usage
            summary_file = "magic/echidna-error-analysis.json"
            os.makedirs("magic", exist_ok=True)
            with open(summary_file, 'w') as f:
                json.dump(result, f, indent=2)

            print("✅ Echidna completed successfully")
            if coverage_files:
                print(f"📊 Generated {len(coverage_files)} coverage files")
            print(f"💾 Analysis saved to: {summary_file}")

        return 0

    # Handle failure - need to analyze logs
    if not log_file:
        log_file = find_echidna_log()

    if not log_file or not os.path.exists(log_file):
        error_result = {
            "status": "error",
            "echidna_exit_code": exit_code,
            "error": "Log file not found",
            "workflow_action": "stop",
            "message": f"Echidna failed with exit code {exit_code} but no log file found for analysis"
        }

        if return_json:
            print(json.dumps(error_result, indent=2))
        else:
            print(f"❌ Echidna failed with exit code {exit_code}")
            print("❌ No log file found for error analysis")

        return 1

    # Read and analyze log content
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        log_content = f.read()

    # Determine error type
    error_type, error_details = analyze_error_type(log_content)

    # Create summary
    summary = create_error_summary(error_type, error_details, exit_code)

    if return_json:
        # Workflow mode: Always return 0 if analysis completed successfully
        # The JSON content indicates what was found; decision steps will route workflow
        print(json.dumps(summary, indent=2))
        return 0
    else:
        # Standalone CLI mode: Use exit codes to signal error types directly
        # Save error summary for downstream processing
        summary_file = "magic/echidna-error-analysis.json"
        os.makedirs("magic", exist_ok=True)
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)

        print(f"❌ Echidna failed with exit code {exit_code}")
        print(f"🔍 Error type: {error_type}")
        print(f"📝 {summary['description']}")
        print(f"💾 Error analysis saved to: {summary_file}")

        if error_type == "compilation":
            print("🔧 Compilation error detected - triggering fix agent")
            return 2  # CLI: User can check exit code in scripts
        elif error_type in ["setup", "rpc", "contract_not_found", "unknown", "unlinked_libraries"]:
            print("📋 Other error detected - generating AI summary")
            return 3  # CLI: Different exit code for non-compilation errors
        else:
            return 1  # CLI: General failure


def main():
    """Main entry point for the script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze Echidna output and determine workflow action based on error type"
    )
    parser.add_argument(
        "exit_code",
        type=int,
        help="Echidna's exit code"
    )
    parser.add_argument(
        "--log-file",
        "-l",
        default=None,
        help="Path to Echidna log file (will search common locations if not provided)"
    )
    parser.add_argument(
        "--return-json",
        action="store_true",
        help="Return JSON output to stdout"
    )

    args = parser.parse_args()
    sys.exit(analyze_echidna_output(args.exit_code, args.log_file, args.return_json))


if __name__ == "__main__":
    main()