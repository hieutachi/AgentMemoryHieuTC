"""Hashing utilities."""

from __future__ import annotations

import hashlib
from pathlib import Path


def file_hash(path: Path, algorithm: str = "sha256") -> str:
    h = hashlib.new(algorithm)
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
    except (OSError, PermissionError):
        return ""
    return h.hexdigest()


def string_hash(text: str, algorithm: str = "sha256") -> str:
    return hashlib.new(algorithm, text.encode("utf-8")).hexdigest()[:16]
