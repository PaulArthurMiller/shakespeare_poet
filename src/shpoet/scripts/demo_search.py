"""Demo script for beam search sequence generation."""

from __future__ import annotations

import logging
from typing import Dict, List

from shpoet.common.types import GuidanceProfile
from shpoet.search.beam_search import BeamSearch


logger = logging.getLogger(__name__)


def build_demo_corpus() -> List[Dict[str, object]]:
    """Build a tiny demo corpus for beam search."""

    return [
        {
            "chunk_id": "c1",
            "text": "Love is bright",
            "tokens": ["Love", "is", "bright"],
            "token_count": 3,
        },
        {
            "chunk_id": "c2",
            "text": "The night grows",
            "tokens": ["The", "night", "grows"],
            "token_count": 3,
        },
        {
            "chunk_id": "c3",
            "text": "Stars above us",
            "tokens": ["Stars", "above", "us"],
            "token_count": 3,
        },
    ]


def build_demo_guidance() -> GuidanceProfile:
    """Build a simple guidance profile for demo search."""

    return GuidanceProfile(
        beat_id="demo-beat",
        anchor_targets=["love"],
        constraints={"required_anchor_count": 0.0},
        priors={"anchor_presence": 1.0, "length_preference": 0.0},
    )


def run_demo_search() -> List[str]:
    """Run beam search on the demo corpus and return the best path."""

    corpus = build_demo_corpus()
    guidance = build_demo_guidance()

    search = BeamSearch(corpus)
    result = search.run(
        guidance=guidance,
        beam_width=2,
        max_length=2,
        checkpoint_interval=1,
    )

    logger.info("Beam search demo best score: %s", result.best_score)
    logger.info("Beam search demo best path: %s", result.best_path)
    return result.best_path


def main() -> None:
    """Run the beam search demo as a CLI entry point."""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    run_demo_search()


if __name__ == "__main__":
    main()
