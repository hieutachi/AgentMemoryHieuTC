"""Install git hooks for automatic agentmemory update."""

from __future__ import annotations

from pathlib import Path

HOOK_SCRIPT = """#!/bin/sh
# AgentMemoryHieuTC post-commit hook — incremental index update
if command -v agentmemory >/dev/null 2>&1; then
  agentmemory update -v 2>/dev/null || true
fi
exit 0
"""

PRE_COMMIT_SCRIPT = """#!/bin/sh
# AgentMemoryHieuTC pre-commit — verify locks before commit
if command -v agentmemory >/dev/null 2>&1; then
  agentmemory lock verify 2>/dev/null || true
fi
exit 0
"""


def install_hooks(repo_root: Path) -> list[str]:
    """Install post-commit and pre-commit hooks. Returns installed paths."""
    hooks_dir = repo_root / ".git" / "hooks"
    if not hooks_dir.is_dir():
        raise FileNotFoundError("Not a git repository (.git/hooks missing)")

    installed: list[str] = []
    for name, content in (
        ("post-commit", HOOK_SCRIPT),
        ("pre-commit", PRE_COMMIT_SCRIPT),
    ):
        path = hooks_dir / name
        path.write_text(content, encoding="utf-8")
        try:
            path.chmod(0o755)
        except OSError:
            pass
        installed.append(str(path))
    return installed


def uninstall_hooks(repo_root: Path) -> list[str]:
    """Remove AgentMemory hooks if they match our template."""
    hooks_dir = repo_root / ".git" / "hooks"
    removed: list[str] = []
    for name in ("post-commit", "pre-commit"):
        path = hooks_dir / name
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="replace")
            if "AgentMemoryHieuTC" in text:
                path.unlink()
                removed.append(str(path))
    return removed
