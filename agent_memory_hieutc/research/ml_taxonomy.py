"""ML/RL/MARL research taxonomy for concept detection."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Keyword sets for research domain detection
ML_DL_KEYWORDS: set[str] = {
    "dataset", "preprocessing", "model", "architecture", "loss", "loss_function",
    "optimizer", "training", "evaluation", "metric", "checkpoint", "inference",
    "dataloader", "batch", "epoch", "learning_rate", "scheduler", "augmentation",
    "transform", "embedding", "encoder", "decoder", "attention", "transformer",
    "cnn", "rnn", "lstm", "gru", "resnet", "convolution", "pooling",
    "dropout", "batch_norm", "normalization", "fine_tune", "pretrained",
}

RL_KEYWORDS: set[str] = {
    "environment", "observation", "action_space", "reward", "policy",
    "value_function", "actor", "critic", "replay_buffer", "rollout_buffer",
    "trajectory", "episode", "step", "return", "discount", "gamma",
    "entropy", "exploration", "baseline", "seed", "timestep",
    "gae", "gae_lambda", "clip_range", "advantage", "bootstrap",
    "on_policy", "off_policy", "experience", "transition",
}

MARL_KEYWORDS: set[str] = {
    "agent", "multi_agent", "joint_action", "local_observation",
    "global_state", "centralized_critic", "decentralized_actor",
    "ctde", "communication", "coordination", "team_size", "coverage",
    "collision", "cooperation", "mappo", "ippo", "vd_mappo", "vdn",
    "qmix", "maddpg", "commnet", "tardeepq", "maven",
    "shared_reward", "individual_reward", "shared_policy",
    "heterogeneous", "homogeneous", "num_agents",
}

PAPER_KEYWORDS: set[str] = {
    "ablation", "baseline", "comparison", "unseen_map", "generalization",
    "runtime", "benchmark", "learning_curve", "sensitivity", "significance",
    "reviewer", "camera_ready", "revision", "reproducibility", "supplementary",
    "main_result", "table", "figure", "appendix", "contribution",
}

ALL_KEYWORDS: dict[str, set[str]] = {
    "ml_dl": ML_DL_KEYWORDS,
    "rl": RL_KEYWORDS,
    "marl": MARL_KEYWORDS,
    "paper": PAPER_KEYWORDS,
}


@dataclass
class TaxonomyMatch:
    category: str
    keywords_found: list[str] = field(default_factory=list)
    confidence: float = 0.0

    @property
    def is_rl(self) -> bool:
        return self.category in ("rl", "marl")

    @property
    def is_marl(self) -> bool:
        return self.category == "marl"


def detect_research_domain(text: str) -> list[TaxonomyMatch]:
    """Detect which research domains a piece of text relates to."""
    text_lower = text.lower()
    matches: list[TaxonomyMatch] = []

    for category, keywords in ALL_KEYWORDS.items():
        found = [kw for kw in keywords if kw in text_lower]
        if found:
            score = min(len(found) / 5.0, 1.0)
            matches.append(TaxonomyMatch(
                category=category,
                keywords_found=found[:10],
                confidence=round(score, 2),
            ))

    return sorted(matches, key=lambda m: m.confidence, reverse=True)


def classify_file_content(text: str) -> dict[str, any]:  # type: ignore
    """Classify a file's content based on taxonomy keywords."""
    text_lower = text.lower()
    result: dict[str, any] = {  # type: ignore
        "domains": [],
        "rl_concepts": [],
        "marl_concepts": [],
        "paper_concepts": [],
    }

    for category, keywords in ALL_KEYWORDS.items():
        found = [kw for kw in keywords if kw in text_lower]
        if found:
            result["domains"].append(category)
            if category == "rl":
                result["rl_concepts"] = found
            elif category == "marl":
                result["marl_concepts"] = found
            elif category == "paper":
                result["paper_concepts"] = found

    return result
