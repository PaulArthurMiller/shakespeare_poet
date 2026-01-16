"""Build a canonical line index from normalized corpus lines."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from shpoet.ingest.normalize import normalize_line


logger = logging.getLogger(__name__)

_PLAY_HEADER_RE = re.compile(r"^[A-Z][A-Z\s',.-]+$")
_ACT_RE = re.compile(r"^ACT\s+([IVXLC]+)")
_SCENE_RE = re.compile(r"^SCENE\s+([IVXLC]+)\b")
_WORD_RE = re.compile(r"[A-Za-z']+")


@dataclass(frozen=True)
class CanonicalLine:
    """Canonical line entry with provenance metadata."""

    line_id: str
    play: str
    act: int
    scene: int
    line_in_scene: int
    word_index: str
    raw_text: str
    tokens: List[str]


def _roman_to_int(value: str) -> int:
    """Convert a Roman numeral string into an integer."""

    roman_map = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    total = 0
    previous = 0
    for char in reversed(value.upper()):
        current = roman_map.get(char, 0)
        if current < previous:
            total -= current
        else:
            total += current
            previous = current
    return total


def _slugify_play(play: str) -> str:
    """Create a lowercase slug for the play name."""

    return re.sub(r"[^a-z0-9]+", "_", play.lower()).strip("_")


def _is_play_header(line: str) -> bool:
    """Determine whether a line is a play header line."""

    return bool(_PLAY_HEADER_RE.match(line)) and not line.startswith("ACT") and not line.startswith("SCENE")


def _extract_tokens(line: str) -> List[str]:
    """Extract word tokens from a line for word index tracking."""

    return _WORD_RE.findall(line)


def build_canonical_index(lines: Iterable[str]) -> List[CanonicalLine]:
    """Build a canonical line index from raw corpus lines."""

    play: Optional[str] = None
    act: Optional[int] = None
    scene: Optional[int] = None
    line_in_scene = 0
    canonical_lines: List[CanonicalLine] = []

    for raw_line in lines:
        line = normalize_line(raw_line)
        if not line:
            continue

        if _is_play_header(line):
            play = line.title()
            act = None
            scene = None
            line_in_scene = 0
            logger.info("Detected play header: %s", play)
            continue

        act_match = _ACT_RE.match(line)
        if act_match:
            act = _roman_to_int(act_match.group(1))
            scene = None
            line_in_scene = 0
            logger.info("Detected act %s", act)
            continue

        scene_match = _SCENE_RE.match(line)
        if scene_match:
            scene = _roman_to_int(scene_match.group(1))
            line_in_scene = 0
            logger.info("Detected scene %s", scene)
            continue

        if play is None or act is None or scene is None:
            logger.warning("Skipping line before headers are set: %s", line)
            continue

        tokens = _extract_tokens(line)
        if not tokens:
            logger.warning("Skipping line without tokens: %s", line)
            continue

        line_in_scene += 1
        word_index = ",".join(str(idx) for idx in range(len(tokens)))
        line_id = f"{_slugify_play(play)}_act{act}_scene{scene}_line{line_in_scene}"
        canonical_lines.append(
            CanonicalLine(
                line_id=line_id,
                play=play,
                act=act,
                scene=scene,
                line_in_scene=line_in_scene,
                word_index=word_index,
                raw_text=line,
                tokens=tokens,
            )
        )

    logger.info("Built canonical index with %s lines", len(canonical_lines))
    return canonical_lines


def canonical_lines_to_dicts(lines: List[CanonicalLine]) -> List[Dict[str, object]]:
    """Convert CanonicalLine entries into JSON-serializable dictionaries."""

    return [
        {
            "line_id": line.line_id,
            "play": line.play,
            "act": line.act,
            "scene": line.scene,
            "line_in_scene": line.line_in_scene,
            "word_index": line.word_index,
            "raw_text": line.raw_text,
            "tokens": line.tokens,
        }
        for line in lines
    ]
