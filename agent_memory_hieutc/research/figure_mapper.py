"""Figure mapping: discover figure generators and outputs."""

from __future__ import annotations

import json
from pathlib import Path

from ..memory.sqlite_store import SQLiteStore

FIGURE_EXTENSIONS = {".png", ".pdf", ".svg", ".eps", ".jpg", ".jpeg"}
FIGURE_DIR_NAMES = {"figures", "figs", "plots", "images", "output_figures"}


def discover_figures(store: SQLiteStore, repo_id: int,
                     repo_root: Path) -> list[dict]:
    """Map figures to their generators and source data."""
    files = store.get_all_files(repo_id)
    figures: list[dict] = []

    # Find all figure output files
    figure_files: list[dict] = []
    for f in files:
        if Path(f["path"]).suffix.lower() in FIGURE_EXTENSIONS:
            figure_files.append(f)

    # Find potential generator scripts
    generator_scripts: list[dict] = []
    for f in files:
        if f["file_type"] in ("figure_generation_script", "source_code"):
            generator_scripts.append(f)

    # Match figures to generators using filename patterns and content
    for fig_file in figure_files:
        fig_name = Path(fig_file["path"]).stem
        fig_info: dict = {
            "figure_name": fig_name,
            "output_path": fig_file["path"],
            "generator_script": "",
            "source_data": [],
            "paper_reference": "",
            "caption": "",
            "status": "found",
        }

        # Try to find matching generator script
        for script in generator_scripts:
            script_path = repo_root / script["path"]
            if not script_path.exists():
                continue
            try:
                content = script_path.read_text(encoding="utf-8", errors="replace")
            except (OSError, PermissionError):
                continue

            # Check if script references this figure name
            if fig_name in content or Path(fig_file["path"]).name in content:
                fig_info["generator_script"] = script["path"]
                break

            # Check if script is in a figure directory and name matches
            script_stem = Path(script["path"]).stem
            if (fig_name.startswith("fig") and script_stem.startswith("plot") or
                fig_name.replace("fig", "plot") == script_stem or
                fig_name.replace("figure", "plot") == script_stem):
                fig_info["generator_script"] = script["path"]
                break

        # If generator script found, extract source data references
        if fig_info["generator_script"]:
            gen_path = repo_root / fig_info["generator_script"]
            if gen_path.exists():
                try:
                    gen_content = gen_path.read_text(encoding="utf-8", errors="replace")
                    import re
                    data_refs = re.findall(
                        r"['\"]([^'\"]*\.(json|csv|npy|npz|pkl))['\"]",
                        gen_content,
                    )
                    fig_info["source_data"] = [d[0] for d in data_refs]
                except (OSError, PermissionError):
                    pass

        # Store in database
        store.insert_figure(
            repo_id=repo_id,
            figure_name=fig_info["figure_name"],
            output_path=fig_info["output_path"],
            generator_script=fig_info["generator_script"],
            source_data=fig_info["source_data"],
            paper_reference=fig_info["paper_reference"],
            caption=fig_info["caption"],
            status=fig_info["status"],
        )
        figures.append(fig_info)

    return figures
