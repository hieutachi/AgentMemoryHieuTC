"""Experiment mapping: discover and classify experiments in the repository."""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..memory.sqlite_store import SQLiteStore
from ..parsers.python_parser import parse_python_file
from .ml_taxonomy import detect_research_domain


def discover_experiments(store: SQLiteStore, repo_id: int, repo_root: Path) -> list[dict]:
    """Scan files for experiment-related patterns and register experiments."""
    experiments: list[dict] = []
    files = store.get_all_files(repo_id)

    # Strategy 1: Find scripts that look like experiment launchers
    for f in files:
        if f["file_type"] not in ("training_script", "experiment_script",
                                   "evaluation_script", "source_code"):
            continue

        filepath = repo_root / f["path"]
        if not filepath.exists():
            continue

        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except (OSError, PermissionError):
            continue

        exp_info = _extract_experiment_info(content, f["path"])
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

    # Strategy 2: Find config files that look like experiment configs
    for f in files:
        if f["file_type"] != "config_file":
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
            # Check if we already have this experiment from strategy 1
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


def _extract_experiment_info(content: str, path: str) -> dict | None:
    """Extract experiment metadata from a Python script."""
    info: dict = {}
    content_lower = content.lower()

    # Check if file looks like an experiment script
    experiment_indicators = [
        "num_seeds", "seeds", "total_timesteps", "episodes", "num_episodes",
        "n_training", "n_eval", "run_experiment", "train(", "evaluate(",
        "parser.add_argument", "argparse", "hydra", "wandb.init",
        "sacred", "mlflow",
    ]
    indicator_count = sum(1 for ind in experiment_indicators if ind in content_lower)
    if indicator_count < 1:
        return None

    # Extract experiment name from filename
    name = Path(path).stem
    info["name"] = name
    info["summary"] = f"Experiment script at {path}"

    # Extract algorithms
    algo_patterns = [
        r"(?:algorithm|algo|method)\s*=\s*['\"](\w+)['\"]",
        r"(?:MAPPO|IPPO|VD.?MAPPO|PPO|SAC|TD3|DDPG|QMIX|VDN|A2C|DQN)",
    ]
    algorithms: list[str] = []
    for pattern in algo_patterns:
        found = re.findall(pattern, content, re.IGNORECASE)
        algorithms.extend(f if isinstance(f, str) else f for f in found)
    info["algorithms"] = list(set(a.upper() for a in algorithms))[:10]

    # Extract environment
    env_patterns = [
        r"(?:environment|env|scenario|map)\s*=\s*['\"]([^'\"]+)['\"]",
        r"(?:make|gym\.make|gymnasium\.make)\s*\(\s*['\"]([^'\"]+)['\"]",
    ]
    for pattern in env_patterns:
        found = re.findall(pattern, content, re.IGNORECASE)
        if found:
            info["environment"] = found[0]
            break

    # Extract seeds
    seed_match = re.search(
        r"(?:seeds|num_seeds|n_seeds)\s*=\s*\[?(\d[^\n\]]{0,100})",
        content, re.IGNORECASE,
    )
    if seed_match:
        seed_str = seed_match.group(1)
        seeds = re.findall(r"\d+", seed_str)
        info["seeds"] = [int(s) for s in seeds[:20]]

    # Extract metrics
    metric_patterns = [
        r"(?:metric|metrics|log_)\s*=?\s*\[?['\"]?([a-zA-Z_][\w_]*)",
    ]
    metrics: list[str] = []
    for pattern in metric_patterns:
        found = re.findall(pattern, content)
        metrics.extend(found)
    info["metrics"] = list(set(metrics))[:15]

    # Extract config and result paths
    config_refs = re.findall(r"['\"]([^'\"]*config[^'\"]*\.(yaml|yml|json))['\"]", content, re.IGNORECASE)
    if config_refs:
        info["config_path"] = config_refs[0][0]

    result_refs = re.findall(r"['\"]([^'\"]*result[^'\"]*\.(json|csv))['\"]", content, re.IGNORECASE)
    if result_refs:
        info["result_path"] = result_refs[0][0]

    return info


def _extract_config_experiment(content: str, path: str) -> dict | None:
    """Extract experiment metadata from a config file."""
    content_lower = content.lower()

    experiment_indicators = [
        "algorithm", "algo", "num_seeds", "total_timesteps", "environment",
        "learning_rate", "gamma", "clip_range", "num_agents", "map_size",
    ]
    indicator_count = sum(1 for ind in experiment_indicators if ind in content_lower)
    if indicator_count < 2:
        return None

    name = Path(path).stem
    info: dict = {"name": f"config_{name}", "summary": f"Experiment config at {path}"}

    # Extract algorithms
    algo_match = re.findall(r"(?:algorithm|algo|method)[':=\s]+['\"]?(\w+)", content, re.IGNORECASE)
    info["algorithms"] = list(set(a.upper() for a in algo_match))[:10]

    # Extract environment
    env_match = re.findall(r"(?:environment|env|scenario)[':=\s]+['\"]?([\w\-/]+)", content, re.IGNORECASE)
    if env_match:
        info["environment"] = env_match[0]

    # Extract seeds
    seed_match = re.findall(r"(?:seeds|num_seeds|n_seeds)[':=\s]+[\[]?([\d\s,\[\]]+)", content, re.IGNORECASE)
    if seed_match:
        seeds = re.findall(r"\d+", seed_match[0])
        info["seeds"] = [int(s) for s in seeds[:20]]

    return info
