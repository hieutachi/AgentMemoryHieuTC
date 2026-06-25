"""Experiment mapping: discover and classify experiments in the repository."""

from __future__ import annotations

import re
from pathlib import Path

from ..memory.sqlite_store import SQLiteStore

# Paths / names that are library code, not experiment launchers
EXCLUDED_PREFIXES = (
    "tests/", "test_", "agent_memory_hieutc/parsers/",
    "agent_memory_hieutc/utils/", "agent_memory_hieutc/graph/",
    "agent_memory_hieutc/memory/", "agent_memory_hieutc/reports/",
    ".agent_memory_hieutc/",
)
EXCLUDED_STEM_SUFFIXES = (
    "_parser", "_mapper", "_exporter", "_store", "_schema",
    "_utils", "_report", "_taxonomy",
)
EXCLUDED_STEMS = {"__init__", "conftest", "setup", "cli", "config", "scanner"}

STRONG_INDICATORS = frozenset({
    "wandb.init", "hydra.main", "@hydra", "run_experiment",
    "total_timesteps", "num_seeds", "sacred", "mlflow",
})
WEAK_INDICATORS = frozenset({
    "num_episodes", "n_training", "n_eval", "train(", "evaluate(",
    "episodes", "seeds",
})
# Too generic alone — require strong signal or training/experiment file type
GENERIC_INDICATORS = frozenset({"parser.add_argument", "argparse"})


def discover_experiments(store: SQLiteStore, repo_id: int, repo_root: Path) -> list[dict]:
    """Scan files for experiment-related patterns and register experiments."""
    experiments: list[dict] = []
    files = store.get_all_files(repo_id)

    for f in files:
        if f["file_type"] not in (
            "training_script", "experiment_script", "evaluation_script",
        ):
            continue
        if not _is_experiment_candidate(f["path"], f["file_type"]):
            continue

        filepath = repo_root / f["path"]
        if not filepath.exists():
            continue

        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except (OSError, PermissionError):
            continue

        exp_info = _extract_experiment_info(content, f["path"], f["file_type"])
        if exp_info:
            exp_id = store.insert_experiment(
                repo_id=repo_id,
                name=exp_info["name"],
                script_path=f["path"],
                config_path=exp_info.get("config_path", ""),
                result_path=exp_info.get("result_path", ""),
                algorithms=exp_info.get("algorithms", []),
                environment=exp_info.get("environment", ""),
                seeds=exp_info.get("seeds", []),
                metrics=exp_info.get("metrics", []),
                status="detected",
                summary=exp_info.get("summary", ""),
            )
            exp_info["experiment_id"] = exp_id
            experiments.append(exp_info)

    for f in files:
        if f["file_type"] != "config_file":
            continue
        if not _is_config_experiment_candidate(f["path"]):
            continue

        filepath = repo_root / f["path"]
        if not filepath.exists():
            continue
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except (OSError, PermissionError):
            continue

        exp_info = _extract_config_experiment(content, f["path"])
        if exp_info:
            existing = store.search_experiments(exp_info["name"])
            if not existing:
                exp_id = store.insert_experiment(
                    repo_id=repo_id,
                    name=exp_info["name"],
                    config_path=f["path"],
                    algorithms=exp_info.get("algorithms", []),
                    environment=exp_info.get("environment", ""),
                    seeds=exp_info.get("seeds", []),
                    status="config_only",
                    summary=exp_info.get("summary", ""),
                )
                exp_info["experiment_id"] = exp_id
                experiments.append(exp_info)

    return experiments


def _is_experiment_candidate(path: str, file_type: str) -> bool:
    norm = path.replace("\\", "/").lower()
    if any(norm.startswith(p) or f"/{p}" in norm for p in EXCLUDED_PREFIXES):
        return False
    stem = Path(path).stem.lower()
    if stem in EXCLUDED_STEMS or stem.startswith("test_"):
        return False
    if any(stem.endswith(s) for s in EXCLUDED_STEM_SUFFIXES):
        return False
    return file_type in ("training_script", "experiment_script", "evaluation_script")


def _is_config_experiment_candidate(path: str) -> bool:
    norm = path.replace("\\", "/").lower()
    if ".agent_memory" in norm or norm in ("pyproject.toml", "setup.cfg"):
        return False
    name = Path(path).stem.lower()
    return any(k in name for k in ("train", "experiment", "exp", "hydra", "sweep", "eval"))


def _score_experiment_signals(content_lower: str, file_type: str) -> int:
    strong = sum(1 for s in STRONG_INDICATORS if s in content_lower)
    weak = sum(1 for s in WEAK_INDICATORS if s in content_lower)
    generic = sum(1 for s in GENERIC_INDICATORS if s in content_lower)
    score = strong * 3 + weak
    if file_type in ("training_script", "experiment_script"):
        score += 2
    if generic and strong == 0 and weak < 2:
        return 0
    return score


def _extract_experiment_info(content: str, path: str, file_type: str) -> dict | None:
    """Extract experiment metadata from a Python script."""
    content_lower = content.lower()
    if _score_experiment_signals(content_lower, file_type) < 3:
        return None

    name = Path(path).stem
    info: dict = {"name": name, "summary": f"Script: {path}"}

    algo_patterns = [
        r"(?:algorithm|algo|method)\s*=\s*['\"](\w+)['\"]",
        r"\b(MAPPO|IPPO|VD.?MAPPO|PPO|SAC|TD3|DDPG|QMIX|VDN|A2C|DQN)\b",
    ]
    algorithms: list[str] = []
    for pattern in algo_patterns:
        found = re.findall(pattern, content, re.IGNORECASE)
        algorithms.extend(f if isinstance(f, str) else f for f in found)
    info["algorithms"] = list(dict.fromkeys(a.upper() for a in algorithms))[:5]

    env_patterns = [
        r"(?:environment|env|scenario|map)\s*=\s*['\"]([^'\"]+)['\"]",
        r"(?:gym\.make|gymnasium\.make)\s*\(\s*['\"]([^'\"]+)['\"]",
    ]
    for pattern in env_patterns:
        found = re.findall(pattern, content, re.IGNORECASE)
        if found:
            info["environment"] = found[0]
            break

    seed_match = re.search(
        r"(?:seeds|num_seeds|n_seeds)\s*=\s*\[?(\d[^\n\]]{0,100})",
        content, re.IGNORECASE,
    )
    if seed_match:
        seeds = re.findall(r"\d+", seed_match.group(1))
        info["seeds"] = [int(s) for s in seeds[:10]]

    config_refs = re.findall(
        r"['\"]([^'\"]*config[^'\"]*\.(yaml|yml|json))['\"]", content, re.IGNORECASE,
    )
    if config_refs:
        info["config_path"] = config_refs[0][0]

    result_refs = re.findall(
        r"['\"]([^'\"]*result[^'\"]*\.(json|csv))['\"]", content, re.IGNORECASE,
    )
    if result_refs:
        info["result_path"] = result_refs[0][0]

    return info


def _extract_config_experiment(content: str, path: str) -> dict | None:
    """Extract experiment metadata from a config file."""
    content_lower = content.lower()
    indicators = [
        "algorithm", "num_seeds", "total_timesteps", "environment",
        "learning_rate", "gamma", "clip_range", "num_agents",
    ]
    if sum(1 for ind in indicators if ind in content_lower) < 3:
        return None

    name = Path(path).stem
    info: dict = {"name": f"config_{name}", "summary": f"Config: {path}"}

    algo_match = re.findall(
        r"(?:algorithm|algo|method)[':=\s]+['\"]?(\w+)", content, re.IGNORECASE,
    )
    info["algorithms"] = list(dict.fromkeys(a.upper() for a in algo_match))[:5]

    env_match = re.findall(
        r"(?:environment|env|scenario)[':=\s]+['\"]?([\w\-/]+)", content, re.IGNORECASE,
    )
    if env_match:
        info["environment"] = env_match[0]

    seed_match = re.findall(
        r"(?:seeds|num_seeds)[':=\s]+[\[]?([\d\s,\[\]]+)", content, re.IGNORECASE,
    )
    if seed_match:
        seeds = re.findall(r"\d+", seed_match[0])
        info["seeds"] = [int(s) for s in seeds[:10]]

    return info
