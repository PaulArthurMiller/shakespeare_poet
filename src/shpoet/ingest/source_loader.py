"""Load raw corpus sources for ingestion."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List


logger = logging.getLogger(__name__)


def load_lines(source_path: Path) -> List[str]:
    """Load non-empty lines from a plaintext source file."""

    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    raw_text = source_path.read_text(encoding="utf-8")
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    logger.info("Loaded %s lines from %s", len(lines), source_path)
    return lines
