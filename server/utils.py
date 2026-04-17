"""
Utility functions for parsing.
"""


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
