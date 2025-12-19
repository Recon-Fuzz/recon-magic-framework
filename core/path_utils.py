"""Path resolution utilities for consistent file operations."""

import os
from pathlib import Path


def get_base_path() -> Path:
    """
    Get the base path for file operations.

    Uses environment variables in this priority:
    1. RECON_FOUNDRY_ROOT (for monorepos)
    2. RECON_REPO_PATH (for regular repos)
    3. Absolute path of current directory (fallback)

    Returns:
        Path: Absolute path to use as base for all file operations
    """
    repo_path = os.environ.get('RECON_FOUNDRY_ROOT') or os.environ.get('RECON_REPO_PATH')

    if repo_path:
        return Path(repo_path).absolute()
    else:
        # If no env vars set, use absolute path of current directory
        # This ensures consistency even if cwd changes later
        return Path.cwd().absolute()


def resolve_file_path(relative_path: str | Path) -> Path:
    """
    Resolve a relative file path to an absolute path using the base path.

    Args:
        relative_path: Relative path to resolve

    Returns:
        Path: Absolute path
    """
    path = Path(relative_path)

    if path.is_absolute():
        return path
    else:
        return get_base_path() / path
