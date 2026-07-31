"""Score a previously-exported play from ``data/output/``.

The replay suite scores plays it generated itself, where the chunk dicts are
still in hand. This scores one off the disk: the export stores only chunk ids,
so the ids are resolved back into chunks first (``validation/chunk_resolver.py``)
and the scorecard is computed from those.

What it can measure depends on where the chunks come from, and the output says
so rather than leaving it to be inferred:

* Chroma index available  -> full scorecard, Tier-2 metadata included.
* Processed JSONL only    -> quote integrity and source diversity are real;
                             meter and line length come back unmeasured.
* Plan JSON supplied      -> anchor coverage is measured. The export does not
                             carry the plan's obligations, so without it there
                             is nothing to check coverage against.

Usage::

    python -m shpoet.scripts.score_play data/output/<job_id>.json
    python -m shpoet.scripts.score_play data/output/<job_id>.json --plan plan.json
    python -m shpoet.scripts.score_play data/output/<job_id>.json --no-index
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional, Sequence

from shpoet.common.types import PlayPlan
from shpoet.config.settings import get_settings
from shpoet.learning.eval_store import save_scorecard
from shpoet.learning.metrics import compute_scorecard
from shpoet.learning.play_run import play_run_from_export
from shpoet.validation.chunk_resolver import build_resolver, load_play_json


logger = logging.getLogger(__name__)


def _load_plan(path: Optional[Path]) -> Optional[PlayPlan]:
    """Load a plan JSON so anchor obligations can be checked, or return None."""

    if path is None:
        return None
    try:
        return PlayPlan.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.error("Could not read plan %s (%s); anchor coverage will be unmeasured", path, exc)
        return None


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for scoring an exported play."""

    parser = argparse.ArgumentParser(
        description="Score an exported play, resolving its chunk ids back to chunks.",
    )
    parser.add_argument("play", type=Path, help="Path to an exported play JSON file.")
    parser.add_argument(
        "--plan",
        type=Path,
        default=None,
        help="Plan JSON for this play; required for anchor coverage to be measured.",
    )
    parser.add_argument(
        "--no-index",
        action="store_true",
        help=(
            "Resolve from the processed JSONL corpus instead of the Chroma index. "
            "Faster to start, but carries no Tier-2 metadata, so meter and line "
            "length come back unmeasured."
        ),
    )
    parser.add_argument(
        "--eval-dir",
        type=Path,
        default=None,
        help="Directory for the scorecard (default: SHPOET_EVAL_DIR, else data/eval).",
    )
    parser.add_argument(
        "--label",
        default=None,
        help="Label for the stored scorecard (default: the play file's stem).",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Score one exported play and write its scorecard.

    Returns:
        0 when the play passes quote integrity, 1 when it does not, 2 on a
        usage or IO error. A play whose integrity could not be fully verified
        also returns 1: a partial check is not a pass.
    """

    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    args = _build_arg_parser().parse_args(argv)
    settings = get_settings()

    try:
        play_json = load_play_json(args.play)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"Could not read play: {exc}", file=sys.stderr)
        return 2

    resolver = build_resolver(
        processed_dir=settings.processed_dir,
        chroma_dir=None if args.no_index else settings.chroma_dir,
    )
    try:
        run = play_run_from_export(
            play_json=play_json,
            resolver=resolver,
            plan=_load_plan(args.plan),
        )
        scorecard = compute_scorecard(run, label=args.label or args.play.stem)
    finally:
        close = getattr(resolver, "close", None)
        if callable(close):
            close()

    eval_dir = args.eval_dir if args.eval_dir is not None else settings.eval_dir
    try:
        path = save_scorecard(scorecard, eval_dir)
    except OSError as exc:
        logger.error("Could not persist scorecard: %s", exc)
        path = None

    print()
    print(scorecard.describe())
    if path is not None:
        print(f"  written to     {path}")
    print()

    integrity = scorecard.quote_integrity
    if not integrity.passed:
        print(f"FAIL: {integrity.violations} quote-integrity violations", file=sys.stderr)
        for example in integrity.examples:
            print(f"  {example}", file=sys.stderr)
        return 1
    if not integrity.fully_verified:
        # Not a pass: the quotes with no provenance were never checked at all.
        print(
            f"FAIL: {integrity.unverifiable} quotes had no source span, so the "
            f"no-reuse rule was only checked on the other {integrity.checked}",
            file=sys.stderr,
        )
        return 1

    print(f"PASS: {integrity.checked} quotes checked, no reuse found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
