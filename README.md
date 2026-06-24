# AgentMemoryHieuTC

A local research memory agent for AI/ML/RL/MARL codebases.

Prevents every new AI agent session from rediscovering your project from zero.
Scans your Git repository once, builds durable context, and exports a compact
memory pack that any AI agent can read to resume work immediately.

## Installation

```bash
pip install -e .
```

## Quick Start

```bash
cd /path/to/your/research_repo

# 1. Initialize
agentmemory init

# 2. Full scan
agentmemory scan -v

# 3. Generate context for next AI agent
agentmemory context

# 4. The key output file:
#    .agent_memory_hieutc/context/NEXT_AGENT_PROMPT.md
```

## Commands

| Command | Description |
|---|---|
| `agentmemory init` | Initialize `.agent_memory_hieutc/` in the repo |
| `agentmemory scan` | Full static scan of all files |
| `agentmemory update` | Incremental update from Git diff |
| `agentmemory graph` | Generate codebase and research workflow graphs |
| `agentmemory context` | Export context pack for AI agent handoff |
| `agentmemory ask "question"` | Ask a question using indexed metadata |
| `agentmemory paper-map` | Generate paper-to-code mapping |
| `agentmemory health` | Check repository quality |
| `agentmemory diff` | Show changes since last scan |

## Key Output

After scanning, find these files in `.agent_memory_hieutc/context/`:

- **`AGENT_BRIEF.md`** — Complete project overview for AI agents
- **`NEXT_AGENT_PROMPT.md`** — Ready-to-copy prompt for new sessions
- **`PROJECT_CONTEXT.md`** — Full file inventory with importance scores
- **`EXPERIMENT_MAPPING.md`** — Experiment-to-script mapping
- **`PAPER_MAPPING.md`** — Paper section-to-code mapping
- **`FIGURE_MAPPING.md`** — Figure generator and source mapping

## How It Works

1. Walks your repository and classifies every file
2. Parses Python files with AST to extract symbols, imports, and RL/MARL patterns
3. Discovers experiments, paper files, and figure generators
4. Builds a codebase dependency graph and research workflow graph
5. Stores everything in a local SQLite database
6. Exports compact Markdown context files for AI agent handoff
7. Updates incrementally using Git diffs

## Requirements

- Python 3.10+
- No GPU required
- No cloud API required
- Works fully offline

## Example Workflow

```bash
# Day 1: Set up
cd my_mappo_project
agentmemory init --name "VD-MAPPO Coverage"
agentmemory scan -v

# Day 2: After editing code
agentmemory update -v
agentmemory health

# Before handing off to a new AI agent
agentmemory context
# Then paste contents of .agent_memory_hieutc/context/NEXT_AGENT_PROMPT.md

# Quick question
agentmemory ask "Where is the reward function?"
agentmemory ask "Which scripts generate figures?"
agentmemory ask "What should the next AI agent read first?"
```

## Limitations

- Static analysis only (does not execute code)
- No vector embeddings in baseline mode
- Mermaid graph complexity limited for very large repos
- Python-only deep parsing (other languages get basic classification)

## License

MIT
