"""Normalization utilities for raw corpus lines."""

from __future__ import annotations

import re
from typing import List


_WHITESPACE_RE = re.compile(r"\s+")


def normalize_line(line: str) -> str:
    """Normalize whitespace in a raw line while preserving punctuation."""

    return _WHITESPACE_RE.sub(" ", line).strip()


def normalize_lines(lines: List[str]) -> List[str]:
    """Normalize a list of raw corpus lines."""

    return [normalize_line(line) for line in lines if line.strip()]
