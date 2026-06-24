"""Paper mapping: discover paper files and map sections to code/results."""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..memory.sqlite_store import SQLiteStore
from ..parsers.markdown_parser import parse_markdown

PAPER_FILENAMES = {
    "paper.tex", "main.tex", "main_new.tex", "manuscript.tex",
    "paper.md", "main.md", "draft.md",
    "response_to_reviewers.md", "revision_changelog.md",
    "remaining_issues.md", "experiment_action_plan.md",
    "experiments_and_results.md", "reviewer_issue_action_status.md",
}


def discover_paper_files(store: SQLiteStore, repo_id: int,
                         repo_root: Path) -> list[dict]:
    """Find paper-related files and extract sections, claims, mappings."""
    files = store.get_all_files(repo_id)
    paper_files: list[dict] = []

    for f in files:
        is_paper = (
            f["file_type"] in ("paper_latex", "paper_markdown", "paper_draft") or
            Path(f["path"]).name in PAPER_FILENAMES
        )
        if not is_paper:
            continue

        filepath = repo_root / f["path"]
        if not filepath.exists():
            continue

        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except (OSError, PermissionError):
            continue

        if f["path"].endswith(".tex"):
            info = _parse_latex_paper(content, f["path"])
        else:
            md_info = parse_markdown(filepath, content)
            info = _md_to_paper_info(md_info, f["path"])

        # Store sections
        for section in info.get("sections", []):
            store.insert_paper_section(
                repo_id=repo_id,
                paper_file=f["path"],
                section_title=section["title"],
                section_type=section.get("type", ""),
                line_number=section.get("line", 0),
                summary=section.get("summary", ""),
                claims=section.get("claims", []),
                related_files=section.get("related_files", []),
            )

        # Store key info as memory items
        if info.get("title"):
            store.set_memory(
                repo_id, "paper_title", info["title"],
                source_path=f["path"], confidence=0.9,
            )
        if info.get("target_venue"):
            store.set_memory(
                repo_id, "target_venue", info["target_venue"],
                source_path=f["path"], confidence=0.7,
            )

        paper_files.append(info)

    return paper_files


def _parse_latex_paper(content: str, path: str) -> dict:
    """Parse LaTeX paper for sections and structure."""
    info: dict = {
        "path": path,
        "title": "",
        "sections": [],
        "target_venue": "",
    }

    # Extract title
    title_match = re.search(r"\\title\{([^}]+)\}", content)
    if title_match:
        info["title"] = title_match.group(1).strip()

    # Extract sections
    section_pattern = re.compile(
        r"\\(section|subsection|subsubsection)\*?\{([^}]+)\}"
    )
    for match in section_pattern.finditer(content):
        level = {"section": 1, "subsection": 2, "subsubsection": 3}[match.group(1)]
        title = match.group(2).strip()
        line = content[:match.start()].count("\n") + 1

        section_type = _classify_section_type(title)
        info["sections"].append({
            "title": title,
            "type": section_type,
            "line": line,
            "level": level,
            "claims": [],
            "related_files": [],
        })

    # Try to detect venue from document class or packages
    venue_patterns = [
        r"\\documentclass\[.*?(ieee|springer|elsevier|acm|aaai|neurips|icml|iclr)",
        r"\\usepackage.*?(ieee|springer|elsevier|acm|natbib)",
    ]
    for pattern in venue_patterns:
        venue_match = re.search(pattern, content, re.IGNORECASE)
        if venue_match:
            info["target_venue"] = venue_match.group(1).upper()
            break

    return info


def _md_to_paper_info(md_info: object, path: str) -> dict:
    """Convert parsed markdown info to paper info format."""
    from ..parsers.markdown_parser import MdFileInfo

    info: dict = {
        "path": path,
        "title": getattr(md_info, "title", ""),
        "sections": [],
    }

    for section in getattr(md_info, "sections", []):
        section_type = _classify_section_type(section.title)
        info["sections"].append({
            "title": section.title,
            "type": section_type,
            "line": section.line,
            "level": section.level,
            "claims": section.claims,
            "related_files": [],
        })

    return info


def _classify_section_type(title: str) -> str:
    title_lower = title.lower()
    if any(w in title_lower for w in ["introduction", "intro"]):
        return "introduction"
    if any(w in title_lower for w in ["related", "background"]):
        return "background"
    if any(w in title_lower for w in ["method", "approach", "framework", "proposed"]):
        return "method"
    if any(w in title_lower for w in ["experiment", "result", "evaluation", "empirical"]):
        return "results"
    if any(w in title_lower for w in ["discussion", "analysis"]):
        return "discussion"
    if any(w in title_lower for w in ["conclusion", "summary", "future"]):
        return "conclusion"
    if any(w in title_lower for w in ["abstract"]):
        return "abstract"
    if any(w in title_lower for w in ["appendix", "supplementary", "supplement"]):
        return "appendix"
    if any(w in title_lower for w in ["reviewer", "revision", "response"]):
        return "revisions"
    return "other"
