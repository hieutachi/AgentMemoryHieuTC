"""Parser for YAML/JSON config files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def parse_config_file(filepath: Path) -> dict[str, Any]:
    """Parse a config file and return a flat key-value dictionary."""
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError):
        return {}

    suffix = filepath.suffix.lower()
    data: Any = None

    if suffix in (".yaml", ".yml"):
        try:
            import yaml
            data = yaml.safe_load(content)
        except Exception:
            pass
    elif suffix == ".json":
        try:
            data = json.loads(content)
        except Exception:
            pass
    elif suffix == ".toml":
        data = _parse_simple_toml(content)

    if data is None:
        return {}

    return _flatten_dict(data)


def _parse_simple_toml(content: str) -> dict:
    """Minimal TOML parser for simple key = value files."""
    result: dict = {}
    current_section = result
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            key = line[1:-1]
            if key not in result:
                result[key] = {}
            current_section = result[key]
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            current_section[key] = value
    return result


def _flatten_dict(d: dict, prefix: str = "", sep: str = ".") -> dict[str, Any]:
    items: list[tuple[str, Any]] = []
    for k, v in d.items():
        new_key = f"{prefix}{sep}{k}" if prefix else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep).items())
        else:
            items.append((new_key, v))
    return dict(items)
