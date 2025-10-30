"""
Utility functions for logging, parsing, and dependency checking.
"""

import subprocess
import time


def create_log_file() -> str:
    """
    Create a timestamped log file path.
    - Generate log ID from current timestamp
    - Create path: artifacts/claude_logs_{timestamp}.json
    - Return log file path
    """
    log_id = time.strftime("%Y%m%d_%H%M%S")
    log_file = f"artifacts/claude_logs_{log_id}.json"
    return log_file


def parse_repo_info(repo_url: str) -> tuple[str, str]:
    """
    Extract organization and repo name from GitHub URL.
    - Parse https://github.com/{org}/{repo} format
    - Return (org_name, repo_name)
    """
    try:
        # Remove protocol and trailing slashes/extensions
        url = repo_url.replace("https://github.com/", "").replace("http://github.com/", "")
        url = url.rstrip("/").rstrip(".git")

        # Split into parts
        parts = url.split("/")
        if len(parts) >= 2:
            org_name = parts[0]
            repo_name = parts[1]
            return org_name, repo_name
        else:
            return "", ""
    except Exception as e:
        print(f"Error parsing repo info: {e}")
        return "", ""


def check_dependencies() -> dict[str, bool]:
    """
    Check if required tools are installed.
    - Check: forge, echidna, medusa, halmos, node, claude
    - Return dict of {tool: is_installed}
    """
    tools = ["forge", "echidna", "medusa", "halmos", "node", "claude", "git"]
    status = {}

    for tool in tools:
        try:
            result = subprocess.run(
                ["which", tool],
                capture_output=True,
                text=True
            )
            status[tool] = result.returncode == 0
        except Exception:
            status[tool] = False

    return status


def install_missing_dependencies(deps: list[str]) -> bool:
    """
    Install missing dependencies.
    - Call appropriate installers for each missing dependency
    - Return overall success status
    """
    # This is a placeholder - actual implementation would need
    # to handle different installation methods per dependency
    print(f"Missing dependencies: {deps}")
    print("Please install them manually or run the install_deps.sh script")
    return False
