"""Parser for result files (JSON, CSV) to extract experiment metadata."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any


def parse_result_file(filepath: Path) -> dict[str, Any]:
    """Parse a result/metrics file and extract structured metadata."""
    suffix = filepath.suffix.lower()
    if suffix == ".json":
        return _parse_json_result(filepath)
    elif suffix == ".csv":
        return _parse_csv_result(filepath)
    elif suffix == ".jsonl":
        return _parse_jsonl_result(filepath)
    return {}


def _parse_json_result(filepath: Path) -> dict[str, Any]:
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
        data = json.loads(content)
    except (OSError, json.JSONDecodeError):
        return {}

    result: dict[str, Any] = {
        "format": "json",
        "keys": [],
        "metrics": [],
        "seeds": [],
        "algorithms": [],
        "environments": [],
    }

    if isinstance(data, dict):
        result["keys"] = list(data.keys())[:50]
        _extract_nested_metadata(data, result)
    elif isinstance(data, list) and data:
        result["keys"] = list(data[0].keys())[:50] if isinstance(data[0], dict) else []
        result["num_entries"] = len(data)
        if isinstance(data[0], dict):
            _extract_nested_metadata(data[0], result)

    return result


def _parse_jsonl_result(filepath: Path) -> dict[str, Any]:
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError):
        return {}

    result: dict[str, Any] = {
        "format": "jsonl",
        "keys": [],
        "metrics": [],
        "num_entries": 0,
    }

    lines = content.strip().splitlines()
    result["num_entries"] = len(lines)
    if lines:
        try:
            first = json.loads(lines[0])
            if isinstance(first, dict):
                result["keys"] = list(first.keys())[:50]
        except json.JSONDecodeError:
            pass

    return result


def _parse_csv_result(filepath: Path) -> dict[str, Any]:
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError):
        return {}

    result: dict[str, Any] = {
        "format": "csv",
        "columns": [],
        "metrics": [],
        "num_rows": 0,
    }

    try:
        reader = csv.DictReader(io.StringIO(content))
        result["columns"] = reader.fieldnames or []
        rows = list(reader)
        result["num_rows"] = len(rows)
    except Exception:
        return result

    # Identify likely metric columns (numeric values)
    if rows:
        for col in result["columns"]:
            try:
                float(rows[0].get(col, ""))
                result["metrics"].append(col)
            except (ValueError, TypeError):
                pass

    # Try to find seed, algorithm, environment columns
    for col in result["columns"]:
        col_lower = col.lower()
        if "seed" in col_lower:
            vals = set(r.get(col, "") for r in rows)
            result["seeds"] = sorted(list(vals))[:20]
        if col_lower in ("algorithm", "algo", "method", "agent"):
            vals = set(r.get(col, "") for r in rows)
            result["algorithms"] = sorted(list(vals))[:20]
        if col_lower in ("environment", "env", "map", "scenario"):
            vals = set(r.get(col, "") for r in rows)
            result["environments"] = sorted(list(vals))[:20]

    return result


def _extract_nested_metadata(data: dict, result: dict) -> None:
    """Recursively extract metadata fields from nested JSON."""
    metadata_keys = {
        "seed": "seeds", "seeds": "seeds", "num_seeds": "seeds",
        "algorithm": "algorithms", "algo": "algorithms",
        "method": "algorithms", "model": "algorithms",
        "environment": "environments", "env": "environments",
        "scenario": "environments", "map_name": "environments",
    }
    metric_keys = {
        "reward", "return", "mean_reward", "avg_reward", "score",
        "accuracy", "loss", "coverage", "collision_rate", "success_rate",
        "win_rate", "mean_return", "episode_reward", "value_loss",
        "policy_loss", "entropy", "fps", "eval_reward",
    }

    for k, v in data.items():
        k_lower = k.lower()
        if k_lower in metadata_keys:
            target = metadata_keys[k_lower]
            if isinstance(v, list):
                result[target].extend(str(x) for x in v)
            else:
                result[target].append(str(v))
        if k_lower in metric_keys or any(mk in k_lower for mk in metric_keys):
            result["metrics"].append(k)
