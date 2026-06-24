"""Git utility functions."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class GitInfo:
    remote: str = ""
    branch: str = ""
    latest_commit: str = ""
    latest_commit_msg: str = ""
    is_clean: bool = True


def _run_git(args: list[str], cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return ""


def get_repo_info(repo_root: Path) -> GitInfo:
    info = GitInfo()
    info.remote = _run_git(["config", "--get", "remote.origin.url"], repo_root)
    info.branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    info.latest_commit = _run_git(["rev-parse", "HEAD"], repo_root)
    info.latest_commit_msg = _run_git(["log", "-1", "--pretty=%s"], repo_root)
    status = _run_git(["status", "--porcelain"], repo_root)
    info.is_clean = status == ""
    return info


def get_changed_files(repo_root: Path, since_commit: str | None = None) -> list[str]:
    """Get list of changed files since a commit or all uncommitted changes."""
    if since_commit:
        diff_files = _run_git(
            ["diff", "--name-only", since_commit, "HEAD"], repo_root
        )
    else:
        # Combine staged, unstaged, and untracked
        tracked = _run_git(["diff", "--name-only", "HEAD"], repo_root)
        untracked = _run_git(
            ["ls-files", "--others", "--exclude-standard"], repo_root
        )
        all_changes = set()
        if tracked:
            all_changes.update(tracked.splitlines())
        if untracked:
            all_changes.update(untracked.splitlines())
        return sorted(all_changes)

    if diff_files:
        return diff_files.splitlines()
    return []


def get_file_log(repo_root: Path, filepath: str, n: int = 5) -> list[dict[str, str]]:
    """Get recent commits touching a file."""
    log = _run_git(
        ["log", f"-{n}", "--pretty=format:%H|%h|%s|%ai", "--", filepath],
        repo_root,
    )
    entries = []
    for line in log.splitlines():
        parts = line.split("|", 3)
        if len(parts) == 4:
            entries.append({
                "hash": parts[0],
                "short_hash": parts[1],
                "message": parts[2],
                "date": parts[3],
            })
    return entries


def is_git_repo(path: Path) -> bool:
    return _run_git(["rev-parse", "--is-inside-work-tree"], path) == "true"
