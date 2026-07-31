"""Persist evaluation scorecards under ``data/eval/``.

A scorecard is only useful next to another scorecard. The point of writing them
to disk is comparison: knobs-on against knobs-off, this week's run against last
week's, act 1 against act 5 once the corpus starts thinning out.

Filenames are built from the scenario, the arm, and a run signature over the
settings that affect the result, so two runs that differ only in when they
happened overwrite each other and two runs that differ in configuration do not.
Timestamping every file instead would fill the directory with runs nobody can
tell apart.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Mapping, Optional

from shpoet.learning.metrics import Scorecard


logger = logging.getLogger(__name__)


_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def _slugify(value: str) -> str:
    """Reduce a label to something safe to use in a filename."""

    slug = _UNSAFE_FILENAME_CHARS.sub("-", value.strip()).strip("-")
    return slug.lower() or "unlabeled"


def run_signature(config: Mapping[str, object], knobs: Mapping[str, float]) -> str:
    """Return a short stable hash of the settings that shaped a run.

    Only inputs go in. Anything derived from the output would make the signature
    change whenever the result did, which defeats the purpose: the signature has
    to identify "the same experiment" so successive runs of it can be compared.
    """

    payload = json.dumps(
        {"config": dict(sorted(config.items())), "knobs": dict(sorted(knobs.items()))},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:10]


def scorecard_filename(scorecard: Scorecard) -> str:
    """Build the filename a scorecard is stored under."""

    signature = run_signature(scorecard.config, scorecard.knobs)
    return f"{_slugify(scorecard.label)}.{signature}.json"


def save_scorecard(scorecard: Scorecard, eval_dir: Path) -> Path:
    """Write a scorecard to the evaluation directory and return its path.

    Raises:
        OSError: if the directory cannot be created or the file cannot be written.
    """

    eval_dir.mkdir(parents=True, exist_ok=True)
    path = eval_dir / scorecard_filename(scorecard)
    path.write_text(
        json.dumps(scorecard.to_dict(), ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("Wrote scorecard %s to %s", scorecard.label, path)
    return path


def load_scorecard_dict(path: Path) -> Dict[str, object]:
    """Read a stored scorecard back as a plain dict.

    Returned as a dict rather than a Scorecard: stored cards may have been
    written by an older version with different fields, and comparison should not
    fail because a field was added since.

    Raises:
        FileNotFoundError: if the path does not exist.
        ValueError: if the file is not a JSON object.
    """

    if not path.exists():
        raise FileNotFoundError(f"Scorecard not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Scorecard is not a JSON object: {path}")
    return payload


def list_scorecards(eval_dir: Path, label_prefix: Optional[str] = None) -> List[Path]:
    """List stored scorecard files, optionally filtered by label prefix."""

    if not eval_dir.exists():
        return []
    paths = sorted(eval_dir.glob("*.json"))
    if label_prefix is None:
        return paths
    prefix = _slugify(label_prefix)
    return [path for path in paths if path.name.startswith(prefix)]
