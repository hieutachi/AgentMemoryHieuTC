"""Markdown file parser for extracting structure, references, and claims."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MdSection:
    title: str
    level: int
    line: int
    content: str = ""
    claims: list[str] = field(default_factory=list)
    figure_refs: list[str] = field(default_factory=list)
    table_refs: list[str] = field(default_factory=list)
    todos: list[str] = field(default_factory=list)


@dataclass
class MdFileInfo:
    path: str
    title: str = ""
    sections: list[MdSection] = field(default_factory=list)
    figure_refs: list[str] = field(default_factory=list)
    table_refs: list[str] = field(default_factory=list)
    todos: list[str] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    file_refs: list[str] = field(default_factory=list)


def parse_markdown(filepath: Path, content: str | None = None) -> MdFileInfo:
    if content is None:
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except (OSError, PermissionError):
            return MdFileInfo(path=str(filepath))

    info = MdFileInfo(path=str(filepath))
    lines = content.splitlines()

    current_section: MdSection | None = None

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Headings
        heading_match = re.match(r"^(#{1,6})\s+(.+)", stripped)
        if heading_match:
            if current_section:
                info.sections.append(current_section)
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            if level == 1 and not info.title:
                info.title = title
            current_section = MdSection(
                title=title, level=level, line=i + 1
            )
            continue

        # Accumulate content for current section
        if current_section is not None:
            current_section.content += line + "\n"

        # Figure references: ![...](...) or Figure X or Fig. X
        fig_refs = re.findall(r"!\[.*?\]\((.+?)\)", stripped)
        fig_refs += re.findall(r"[Ff]ig(?:ure)?\.?\s*(\d+[a-z]?)", stripped)
        info.figure_refs.extend(fig_refs)
        if current_section:
            current_section.figure_refs.extend(fig_refs)

        # Table references
        tbl_refs = re.findall(r"[Tt]able\s+(\d+[a-z]?)", stripped)
        info.table_refs.extend(tbl_refs)
        if current_section:
            current_section.table_refs.extend(tbl_refs)

        # TODOs and FIXMEs
        todo_match = re.findall(r"(?:TODO|FIXME|HACK|XXX|REVIEWER)[:\s]+(.+)", stripped, re.IGNORECASE)
        info.todos.extend(todo_match)
        if current_section:
            current_section.todos.extend(todo_match)

        # Citations: \cite{...} or [@key]
        cites = re.findall(r"\\cite\{([^}]+)\}", stripped)
        cites += re.findall(r"\[@([^\]]+)\]", stripped)
        info.citations.extend(cites)

        # File references
        file_refs = re.findall(r"`([^`]+\.(py|yaml|yml|json|csv|tex|sh))`", stripped)
        info.file_refs.extend([f[0] for f in file_refs])

    if current_section:
        info.sections.append(current_section)

    return info
