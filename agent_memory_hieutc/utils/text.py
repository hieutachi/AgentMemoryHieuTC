"""Text processing utilities."""

from __future__ import annotations

import re

STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "must", "can", "could", "to", "of", "in",
    "for", "on", "with", "at", "by", "from", "as", "into", "through",
    "during", "before", "after", "above", "below", "between", "out",
    "off", "over", "under", "again", "further", "then", "once", "here",
    "there", "when", "where", "why", "how", "all", "each", "every",
    "both", "few", "more", "most", "other", "some", "such", "no", "nor",
    "not", "only", "own", "same", "so", "than", "too", "very", "just",
    "don", "now", "and", "but", "or", "if", "what", "which", "who",
    "whom", "this", "that", "these", "those", "i", "me", "my", "we",
    "our", "you", "your", "he", "him", "his", "she", "her", "it", "its",
    "they", "them", "their", "about", "up", "down",
})


def extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords from a question or text."""
    words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower())
    keywords = [w for w in words if w not in STOPWORDS and len(w) > 2]
    return list(dict.fromkeys(keywords))  # deduplicate, preserve order


def truncate(text: str, max_len: int = 200) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def extract_code_snippet(content: str, line: int, context: int = 3) -> str:
    """Extract a snippet around a given line number."""
    lines = content.splitlines()
    start = max(0, line - 1 - context)
    end = min(len(lines), line + context)
    snippet_lines = []
    for i in range(start, end):
        prefix = ">>>" if i == line - 1 else "   "
        snippet_lines.append(f"{prefix} {i+1:4d} | {lines[i]}")
    return "\n".join(snippet_lines)


def clean_docstring(doc: str | None) -> str:
    if not doc:
        return ""
    lines = doc.strip().splitlines()
    cleaned = []
    for line in lines:
        cleaned.append(line.strip())
    return " ".join(cleaned).strip()
