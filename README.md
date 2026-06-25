# AgentMemoryHieuTC v2.0

Local research memory agent for AI/ML/RL/MARL codebases — **compact context**, **phase tracking**, **metric LOCK**, and **decision log** for long research projects.

## Installation

```bash
pip install -e .
# Optional semantic search:
pip install -e ".[embeddings]"
```

## Quick Start

```bash
cd /path/to/your/research_repo
agentmemory init --name "My MARL Project"
agentmemory scan -v
agentmemory phase set baseline
agentmemory context
# Hand off: .agent_memory_hieutc/context/NEXT_AGENT_PROMPT.md
```

## Core Commands

| Command | Description |
|---|---|
| `agentmemory init` | Initialize memory in repo |
| `agentmemory scan` | Full scan + graph + context |
| `agentmemory update` | Incremental git diff update |
| `agentmemory context` | Export compact context (~500 tokens) |
| `agentmemory ask "..."` | Keyword search (no LLM) |
| `agentmemory diff` | Changes since last scan |
| `agentmemory health` | Repository health report |
| `agentmemory verify` | Verify LOCKs + paper claims |
| `agentmemory matrix` | Experiment matrix export |

## v2.0: LOCK (freeze numbers & files)

```bash
agentmemory lock result results/table2.json --label table2
agentmemory lock config configs/mappo_train.yaml --label main_config
agentmemory lock metric table2_reward "reward=0.847,seed=3"
agentmemory lock list
agentmemory lock verify    # fails if locked file changed
agentmemory lock unlock table2
```

## v2.0: Phase tracking

```bash
agentmemory phase set baseline
agentmemory phase task "MAPPO 5 seeds on map A done"
agentmemory phase done baseline
agentmemory phase set ablation
agentmemory phase status
```

Phases: `baseline`, `ablation`, `unseen_map`, `sensitivity`, `camera_ready`, `revision`

## v2.0: Decision log

```bash
agentmemory note "Tried entropy coef 0.01 — coverage dropped" --outcome fail
agentmemory note "Best config: lr=3e-4, clip=0.2" --outcome success
```

## v2.0: Integrations

```bash
# Auto-sync wandb/ and mlruns/ on scan (configurable)
agentmemory scan -v

# Git hooks (auto update + lock verify on commit)
agentmemory hooks install

# Semantic search (optional)
agentmemory embed index
agentmemory embed search "reward shaping function"
```

## Key Output Files

| File | Purpose |
|---|---|
| `CONTEXT_COMPACT.md` | Primary agent handoff (~500 tokens) |
| `NEXT_AGENT_PROMPT.md` | Copy-paste prompt for new session |
| `PHASE_STATUS.md` | Current phase + rules |
| `EXPERIMENT_MATRIX.md` | Algo × env × seeds table |
| `DECISION_LOG.md` | What was tried (via `note`) |

## Config (`.agent_memory_hieutc/config.yaml`)

```yaml
version: "2.0.0"
context_mode: compact
context_max_files: 12
context_importance_min: 5.0
wandb_sync_enabled: true
mlflow_sync_enabled: true
embeddings_enabled: false
```

## Research Workflow Example

```bash
agentmemory init --name "VD-MAPPO Coverage"
agentmemory phase set baseline
agentmemory scan -v

# After training
agentmemory lock result outputs/baseline_mappo.json --label table1
agentmemory lock config configs/mappo.yaml --label baseline_cfg
agentmemory note "Baseline MAPPO 5 seeds — coverage 0.82±0.03" -o success
agentmemory phase done baseline

agentmemory context          # ~500 tokens for next agent
agentmemory hooks install    # auto-update on commit
```

## Requirements

- Python 3.10+
- Works offline (embeddings/wandb/mlflow optional)
- No cloud LLM required

## License

MIT
