"""Python AST-based parser for extracting symbols, imports, and research patterns."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PySymbol:
    symbol_type: str  # function, class, method, constant, main_block
    name: str
    start_line: int
    end_line: int
    signature: str = ""
    docstring: str = ""
    decorators: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)
    base_classes: list[str] = field(default_factory=list)


@dataclass
class PyFileInfo:
    path: str
    imports: list[str] = field(default_factory=list)
    from_imports: dict[str, list[str]] = field(default_factory=dict)
    symbols: list[PySymbol] = field(default_factory=list)
    cli_args: list[str] = field(default_factory=list)
    referenced_files: list[str] = field(default_factory=list)
    config_files_loaded: list[str] = field(default_factory=list)
    result_files_written: list[str] = field(default_factory=list)
    figure_files_written: list[str] = field(default_factory=list)
    has_main: bool = False
    calls_train: bool = False
    calls_evaluate: bool = False
    calls_plot: bool = False
    calls_save: bool = False
    research_keywords: list[str] = field(default_factory=list)
    summary: str = ""


def _extract_calls(node: ast.AST) -> list[str]:
    calls = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Attribute):
                calls.append(func.attr)
            elif isinstance(func, ast.Name):
                calls.append(func.id)
    return calls


def _get_decorators(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> list[str]:
    decs = []
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name):
            decs.append(dec.id)
        elif isinstance(dec, ast.Attribute):
            decs.append(dec.attr)
        elif isinstance(dec, ast.Call):
            if isinstance(dec.func, ast.Name):
                decs.append(dec.func.id)
            elif isinstance(dec.func, ast.Attribute):
                decs.append(dec.func.attr)
    return decs


def _extract_string_literals(node: ast.AST) -> list[str]:
    strings = []
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            strings.append(child.value)
    return strings


def parse_python_file(filepath: Path, content: str | None = None) -> PyFileInfo:
    """Parse a Python file and extract structured information."""
    info = PyFileInfo(path=str(filepath))

    if content is None:
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except (OSError, PermissionError):
            return info

    try:
        tree = ast.parse(content, filename=str(filepath))
    except SyntaxError:
        return info

    # Extract imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                info.imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module = node.module
                names = [a.name for a in node.names]
                info.from_imports.setdefault(module, []).extend(names)
                info.imports.append(module)

    # Extract top-level symbols
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            sig = f"def {node.name}("
            args = []
            for a in node.args.args:
                args.append(a.arg)
            sig += ", ".join(args) + ")"
            doc = ast.get_docstring(node) or ""
            calls = _extract_calls(node)
            decs = _get_decorators(node)
            info.symbols.append(PySymbol(
                symbol_type="function",
                name=node.name,
                start_line=node.lineno,
                end_line=node.end_lineno or node.lineno,
                signature=sig,
                docstring=doc,
                decorators=decs,
                calls=calls,
            ))
            if node.name == "main":
                info.has_main = True

        elif isinstance(node, ast.ClassDef):
            bases = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    bases.append(base.attr)
            doc = ast.get_docstring(node) or ""
            decs = _get_decorators(node)
            info.symbols.append(PySymbol(
                symbol_type="class",
                name=node.name,
                start_line=node.lineno,
                end_line=node.end_lineno or node.lineno,
                docstring=doc,
                decorators=decs,
                base_classes=bases,
            ))
            # Extract methods
            for item in ast.iter_child_nodes(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    msig = f"{node.name}.{item.name}()"
                    mdoc = ast.get_docstring(item) or ""
                    mcalls = _extract_calls(item)
                    info.symbols.append(PySymbol(
                        symbol_type="method",
                        name=f"{node.name}.{item.name}",
                        start_line=item.lineno,
                        end_line=item.end_lineno or item.lineno,
                        signature=msig,
                        docstring=mdoc,
                        calls=mcalls,
                    ))

        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    name = target.id
                    if name.isupper() and len(name) > 1:
                        info.symbols.append(PySymbol(
                            symbol_type="constant",
                            name=name,
                            start_line=node.lineno,
                            end_line=node.end_lineno or node.lineno,
                        ))

    # Check for if __name__ == "__main__"
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            try:
                if (isinstance(node.test, ast.Compare) and
                    isinstance(node.test.left, ast.Name) and
                    node.test.left.id == "__name__"):
                    info.has_main = True
            except Exception:
                pass

    # Analyze calls and patterns
    all_calls = []
    for sym in info.symbols:
        all_calls.extend(sym.calls)
    all_calls_lower = [c.lower() for c in all_calls]

    info.calls_train = any(c in all_calls_lower for c in ["train", "training", "run_training"])
    info.calls_evaluate = any(c in all_calls_lower for c in ["evaluate", "eval", "evaluation", "test"])
    info.calls_plot = any(c in all_calls_lower for c in ["plot", "plot_", "savefig", "save_figure", "generate_figure", "make_figure"])
    info.calls_save = any(c in all_calls_lower for c in ["save", "save_json", "save_csv", "dump", "pickle", "torch_save"])

    # Detect config file references from string literals
    all_strings = _extract_string_literals(tree)
    for s in all_strings:
        if any(s.endswith(ext) for ext in [".yaml", ".yml", ".json", ".toml", ".ini", ".cfg"]):
            info.config_files_loaded.append(s)
        if any(s.endswith(ext) for ext in [".csv", ".json", ".jsonl", ".parquet"]):
            if any(kw in s.lower() for kw in ["result", "metric", "output", "log", "eval"]):
                info.result_files_written.append(s)
        if any(s.endswith(ext) for ext in [".png", ".pdf", ".svg", ".eps", ".jpg"]):
            info.figure_files_written.append(s)
        # Detect argparse CLI arguments
        if s.startswith("--"):
            info.cli_args.append(s)

    # Extract research-relevant keywords
    rl_keywords = [
        "reward", "policy", "value", "actor", "critic", "episode", "trajectory",
        "rollout", "buffer", "replay", "environment", "observation", "action",
        "discount", "entropy", "gae", "ppo", "sac", "td3", "ddpg", "mappo",
        "ippo", "vdn", "qmix", "coverage", "collision", "agent", "multi_agent",
        "centralized", "decentralized", "ctde", "communication", "coordination",
    ]
    content_lower = content.lower()
    for kw in rl_keywords:
        if kw in content_lower:
            info.research_keywords.append(kw)

    # Generate summary
    type_counts: dict[str, int] = {}
    for s in info.symbols:
        type_counts[s.symbol_type] = type_counts.get(s.symbol_type, 0) + 1
    parts = []
    if info.has_main:
        parts.append("has main entrypoint")
    if type_counts.get("class", 0):
        parts.append(f"{type_counts['class']} class(es)")
    if type_counts.get("function", 0):
        parts.append(f"{type_counts['function']} function(s)")
    if info.imports:
        parts.append(f"{len(info.imports)} import(s)")
    if info.research_keywords:
        parts.append(f"RL keywords: {', '.join(info.research_keywords[:5])}")
    info.summary = "; ".join(parts) if parts else "empty or unparseable"

    return info
