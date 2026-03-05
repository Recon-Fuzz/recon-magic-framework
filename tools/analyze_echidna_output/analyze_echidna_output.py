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


def _get_base_dir() -> Path:
    """Get the effective base directory, preferring RECON_FOUNDRY_ROOT env var."""
    foundry_root = os.environ.get('RECON_FOUNDRY_ROOT')
    if foundry_root:
        return Path(foundry_root)
    return Path.cwd()


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
        error_type: One of the 16+ Echidna error types
        error_details: Dictionary with specific error information
    """
    error_details = {
        "error_lines": [],
        "context": "",
        "suggested_action": ""
    }

    # Helper function to extract context around matching lines
    def extract_context(lines, pattern, context_before=2, context_after=10):
        for i, line in enumerate(lines):
            if re.search(pattern, line, re.IGNORECASE):
                start_idx = max(0, i - context_before)
                end_idx = min(len(lines), i + context_after)
                return lines[start_idx:end_idx]
        return []

    lines = log_content.split('\n')

    # Check for compilation errors (highest priority)
    if "CryticCompile:Error" in log_content or re.search(r"Couldn't compile given file", log_content):
        error_details["error_lines"] = extract_context(lines, r"CryticCompile:Error|Couldn't compile given file")
        error_details["context"] = '\n'.join(error_details["error_lines"])
        error_details["suggested_action"] = "trigger_compilation_fix_agent"
        return "compilation", error_details

    # Check for no_crytic_compile error
    if re.search(r"crytic-compile not installed|not found in PATH", log_content):
        error_details["error_lines"] = extract_context(lines, r"crytic-compile not installed|not found in PATH")
        error_details["context"] = '\n'.join(error_details["error_lines"])
        error_details["suggested_action"] = "stop"
        return "no_crytic_compile", error_details

    # Check for solc_read_failure
    if re.search(r"Could not read crytic-export/combined_solc\.json", log_content):
        error_details["error_lines"] = extract_context(lines, r"Could not read crytic-export/combined_solc\.json")
        error_details["context"] = '\n'.join(error_details["error_lines"])
        error_details["suggested_action"] = "generate_ai_summary"
        return "solc_read_failure", error_details

    # Check for no_contracts
    if re.search(r"No contracts found in given file", log_content):
        error_details["error_lines"] = extract_context(lines, r"No contracts found")
        error_details["context"] = '\n'.join(error_details["error_lines"])
        error_details["suggested_action"] = "generate_ai_summary"
        return "no_contracts", error_details

    # Check for contract_not_found
    if re.search(r"Given contract .* not found in given file|could not find contract", log_content, re.IGNORECASE):
        error_details["error_lines"] = extract_context(lines, r"contract .* not found|could not find contract")
        error_details["context"] = '\n'.join(error_details["error_lines"])
        error_details["suggested_action"] = "generate_ai_summary"
        return "contract_not_found", error_details

    # Check for no_bytecode
    if re.search(r"No bytecode found for contract", log_content):
        error_details["error_lines"] = extract_context(lines, r"No bytecode found")
        error_details["context"] = '\n'.join(error_details["error_lines"])
        error_details["suggested_action"] = "generate_ai_summary"
        return "no_bytecode", error_details

    # Check for no_funcs
    if re.search(r"ABI is empty, are you sure your constructor is right\?", log_content):
        error_details["error_lines"] = extract_context(lines, r"ABI is empty")
        error_details["context"] = '\n'.join(error_details["error_lines"])
        error_details["suggested_action"] = "generate_ai_summary"
        return "no_funcs", error_details

    # Check for no_tests
    if re.search(r"No tests found in ABI", log_content):
        error_details["error_lines"] = extract_context(lines, r"No tests found")
        error_details["context"] = '\n'.join(error_details["error_lines"])
        error_details["suggested_action"] = "generate_ai_summary"
        return "no_tests", error_details

    # Check for only_tests
    if re.search(r"Only tests and no public functions found in ABI", log_content):
        error_details["error_lines"] = extract_context(lines, r"Only tests and no public")
        error_details["context"] = '\n'.join(error_details["error_lines"])
        error_details["suggested_action"] = "generate_ai_summary"
        return "only_tests", error_details

    # Check for constructor_args
    if re.search(r"Constructor arguments are required", log_content):
        error_details["error_lines"] = extract_context(lines, r"Constructor arguments are required")
        error_details["context"] = '\n'.join(error_details["error_lines"])
        error_details["suggested_action"] = "generate_ai_summary"
        return "constructor_args", error_details

    # Check for deployment_failed
    if re.search(r"Deploying the contract .* failed", log_content):
        error_details["error_lines"] = extract_context(lines, r"Deploying the contract .* failed")
        error_details["context"] = '\n'.join(error_details["error_lines"])
        error_details["suggested_action"] = "generate_ai_summary"
        return "deployment_failed", error_details

    # Check for invalid_method_filters
    if re.search(r"Applying the filter .* to the methods produces an empty list", log_content):
        error_details["error_lines"] = extract_context(lines, r"Applying the filter")
        error_details["context"] = '\n'.join(error_details["error_lines"])
        error_details["suggested_action"] = "generate_ai_summary"
        return "invalid_method_filters", error_details

    # Check for outdated_solc_version
    if re.search(r"Solc version .* detected.*doesn't support versions of solc before", log_content):
        error_details["error_lines"] = extract_context(lines, r"Solc version .* detected")
        error_details["context"] = '\n'.join(error_details["error_lines"])
        error_details["suggested_action"] = "stop"
        return "outdated_solc_version", error_details

    # Check for bad_addr
    if re.search(r"No contract at .* exists", log_content):
        error_details["error_lines"] = extract_context(lines, r"No contract at .* exists")
        error_details["context"] = '\n'.join(error_details["error_lines"])
        error_details["suggested_action"] = "generate_ai_summary"
        return "bad_addr", error_details

    # Check for test_args_found
    if re.search(r"Test .* has arguments, aborting", log_content):
        error_details["error_lines"] = extract_context(lines, r"Test .* has arguments")
        error_details["context"] = '\n'.join(error_details["error_lines"])
        error_details["suggested_action"] = "generate_ai_summary"
        return "test_args_found", error_details

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
    # Simplify exit codes: 0=success, 1=compilation error, 2=other errors
    simplified_exit_code = 1 if error_type == "compilation" else 2

    summary = {
        "exit_code": simplified_exit_code,
        "error_type": error_type,
        "error_details": error_details,
        "workflow_action": error_details.get("suggested_action", "stop")
    }

    # Add human-readable description
    descriptions = {
        "compilation": "Solidity compilation failed. The contracts have syntax errors or dependency issues.",
        "no_crytic_compile": "crytic-compile is not installed or not found in PATH. This tool is required for contract compilation.",
        "solc_read_failure": "Could not read the compiled Solidity output file (crytic-export/combined_solc.json).",
        "no_contracts": "No contracts found in the given file. The file may be empty or contain only interfaces/libraries.",
        "contract_not_found": "The specified contract could not be found in the compiled artifacts.",
        "no_bytecode": "No bytecode found for the specified contract. The contract may not have compiled successfully.",
        "no_funcs": "ABI is empty. This usually means the constructor parameters or configuration is incorrect.",
        "no_tests": "No test functions found in the contract ABI. Check that test functions are properly defined.",
        "only_tests": "Only test functions found with no public functions to fuzz. Add public functions to the contract.",
        "constructor_args": "Constructor arguments are required but not provided in the configuration.",
        "deployment_failed": "Failed to deploy the contract. This can be due to revert, out-of-gas, or constructor issues.",
        "setup": "The setUp() function in the fuzzing harness failed to execute properly.",
        "invalid_method_filters": "The method filter configuration produces an empty list of functions to test.",
        "outdated_solc_version": "The Solidity compiler version is too old. Echidna requires solc 0.4.25 or newer.",
        "bad_addr": "No contract exists at the specified address.",
        "test_args_found": "Test function has arguments. Echidna test functions should have no parameters.",
        "unlinked_libraries": "Contract bytecode contains unlinked library references. Libraries must be deployed and linked before Echidna can run the contract.",
        "rpc": "Echidna requires RPC access for mainnet forking but no RPC URL is configured.",
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
        1: Compilation error - trigger compilation fix agent
        2: All other errors - stop workflow or generate AI summary
    """

    # Handle successful execution
    if exit_code == 0:
        result = {
            "status": "success",
            "exit_code": 0,  # 0 = success
            "error_type": None,  # Explicitly set to None for success case
            "workflow_action": "continue",
            "message": "Echidna completed successfully"
        }

        # Check if coverage files were generated
        base = _get_base_dir()
        echidna_dir = base / "echidna"
        coverage_files = list(echidna_dir.glob("*.txt")) if echidna_dir.exists() else []
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
            magic_dir = str(base / "magic")
            summary_file = os.path.join(magic_dir, "echidna-error-analysis.json")
            os.makedirs(magic_dir, exist_ok=True)
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
            "exit_code": 2,  # 2 = other errors (can't determine if compilation without log)
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
        base = _get_base_dir()
        magic_dir = str(base / "magic")
        summary_file = os.path.join(magic_dir, "echidna-error-analysis.json")
        os.makedirs(magic_dir, exist_ok=True)
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)

        print(f"❌ Echidna failed with exit code {exit_code}")
        print(f"🔍 Error type: {error_type}")
        print(f"📝 {summary['description']}")
        print(f"💾 Error analysis saved to: {summary_file}")

        # Simplified exit codes: 0=success, 1=compilation error, 2=all other errors
        if error_type == "compilation":
            print("🔧 Compilation error detected - triggering fix agent")
            return 1  # CLI: Compilation error
        else:
            # All other error types
            if error_type in ["no_crytic_compile", "outdated_solc_version"]:
                print("⚠️ Environment setup error - manual intervention required")
            elif error_type == "unlinked_libraries":
                print("🔗 Unlinked libraries detected - configuration update needed")
            else:
                print("📋 Error detected - generating AI summary")
            return 2  # CLI: All other errors


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