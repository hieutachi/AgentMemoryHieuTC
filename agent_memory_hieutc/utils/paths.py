"""Path and pattern utilities."""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path


def should_ignore(rel_path: str, patterns: list[str]) -> bool:
    """Check if a relative path matches any ignore pattern."""
    parts = Path(rel_path).parts
    for pattern in patterns:
        # Direct match
        if fnmatch.fnmatch(rel_path, pattern):
            return True
        if fnmatch.fnmatch(os.path.basename(rel_path), pattern):
            return True
        # Directory prefix match
        if pattern.endswith("/"):
            dir_name = pattern.rstrip("/")
            if dir_name in parts:
                return True
        # Prefix match for nested paths
        for part in parts:
            if fnmatch.fnmatch(part, pattern.rstrip("/")):
                return True
    return False


def safe_relative(path: Path, root: Path) -> str:
    """Return a POSIX relative path string."""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def sanitize_mermaid_id(text: str) -> str:
    """Create a valid Mermaid node ID from arbitrary text."""
    clean = text.replace(".", "_").replace("-", "_").replace(" ", "_")
    clean = clean.replace("/", "__").replace("\\", "__")
    clean = clean.replace("(", "").replace(")", "")
    clean = clean.replace("[", "").replace("]", "")
    clean = clean.replace("{", "").replace("}", "")
    clean = clean.replace("'", "").replace('"', "")
    if clean and clean[0].isdigit():
        clean = "n" + clean
    return clean or "node"
