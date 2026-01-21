"""Normalization utilities for raw corpus lines.

Handles character normalization critical for accurate tokenization:
- Curly quotes → straight apostrophes (for contractions/possessives)
- Various dash types → standard hyphen
- Whitespace normalization
"""

from __future__ import annotations

import re
from typing import List


_WHITESPACE_RE = re.compile(r"\s+")

# Unicode curly quotes and similar characters that should become apostrophes
# U+2018 ' left single quotation mark
# U+2019 ' right single quotation mark (most common for apostrophes)
# U+201A ‚ single low-9 quotation mark
# U+201B ‛ single high-reversed-9 quotation mark
# U+0060 ` grave accent (sometimes used as apostrophe)
# U+00B4 ´ acute accent
_APOSTROPHE_CHARS = "\u2018\u2019\u201a\u201b\u0060\u00b4"
_APOSTROPHE_RE = re.compile(f"[{_APOSTROPHE_CHARS}]")

# Various dash/hyphen characters that should become standard hyphen
# U+2010 ‐ hyphen
# U+2011 ‑ non-breaking hyphen
# U+2012 ‒ figure dash
# U+2013 – en dash
# U+2014 — em dash
# U+2015 ― horizontal bar
_DASH_CHARS = "\u2010\u2011\u2012\u2013\u2014\u2015"
_DASH_RE = re.compile(f"[{_DASH_CHARS}]")


def normalize_apostrophes(text: str) -> str:
    """Convert all apostrophe-like characters to standard ASCII apostrophe.

    This is critical for tokenization - words like "Neptune's" must not be
    split into "Neptune" and "s" due to curly quote characters.
    """
    return _APOSTROPHE_RE.sub("'", text)


def normalize_dashes(text: str) -> str:
    """Convert various dash characters to standard hyphen."""
    return _DASH_RE.sub("-", text)


def normalize_line(line: str) -> str:
    """Normalize a raw line for consistent processing.

    Performs:
    1. Apostrophe normalization (curly → straight)
    2. Dash normalization (em/en dash → hyphen)
    3. Whitespace normalization (collapse multiple spaces)
    """
    line = normalize_apostrophes(line)
    line = normalize_dashes(line)
    line = _WHITESPACE_RE.sub(" ", line).strip()
    return line


def normalize_lines(lines: List[str]) -> List[str]:
    """Normalize a list of raw corpus lines."""
    return [normalize_line(line) for line in lines if line.strip()]
