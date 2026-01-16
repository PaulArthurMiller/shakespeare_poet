"""Anchor planning helpers for the expander."""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Tuple

from shpoet.common.types import AnchorPlan, AnchorRegistry, BeatObligation, UserPlayInput


logger = logging.getLogger(__name__)

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "with",
}


def _tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase words for anchor candidate extraction."""

    tokens = re.findall(r"[a-zA-Z']+", text.lower())
    return [token for token in tokens if token not in _STOPWORDS]


def _collect_candidates(user_input: UserPlayInput) -> List[str]:
    """Collect potential anchor candidates from user input fields."""

    candidates: List[str] = []
    candidates.extend(_tokenize(user_input.overview))
    for character in user_input.characters:
        candidates.extend(_tokenize(character.description))
        candidates.extend(_tokenize(" ".join(character.voice_traits)))
    for scene in user_input.scenes:
        candidates.extend(_tokenize(scene.setting))
        candidates.extend(_tokenize(scene.summary))
    logger.info("Collected %s anchor candidates", len(candidates))
    return candidates


def _unique_ordered(items: List[str]) -> List[str]:
    """Return de-duplicated list preserving original order."""

    seen: set[str] = set()
    unique_items: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        unique_items.append(item)
    return unique_items


def plan_anchors(
    user_input: UserPlayInput,
    beat_ids_by_act: Dict[int, List[str]],
) -> Tuple[AnchorRegistry, Dict[str, BeatObligation]]:
    """Create anchors and beat obligations based on user input and beats."""

    candidates = _unique_ordered(_collect_candidates(user_input))
    primary_anchor = candidates[0] if candidates else "fate"
    related_terms = candidates[1:7] if len(candidates) > 1 else []

    recurrence_rules = [
        "Mention the primary anchor early in each act to reinforce continuity.",
        "Revisit anchor variations near emotional turns to sustain motifs.",
    ]

    placements: List[str] = []
    obligations: Dict[str, BeatObligation] = {}
    for act, beat_ids in beat_ids_by_act.items():
        if not beat_ids:
            continue
        first_beat = beat_ids[0]
        placements.append(first_beat)
        obligations[first_beat] = BeatObligation(
            beat_id=first_beat,
            required_anchors=[primary_anchor],
            desired_anchors=related_terms[:2],
        )
        logger.info("Anchor obligation set for act %s beat %s", act, first_beat)

    anchor_plan = AnchorPlan(
        anchor_term=primary_anchor,
        related_terms=related_terms,
        recurrence_rules=recurrence_rules,
        placements=placements,
    )

    registry = AnchorRegistry(primary_anchor=primary_anchor, anchors=[anchor_plan])

    logger.info("Primary anchor selected: %s", primary_anchor)
    return registry, obligations
