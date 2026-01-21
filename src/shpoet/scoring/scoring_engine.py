"""Scoring engine for candidate chunks and paths."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Iterable, List

from shpoet.common.types import CandidateScore, GuidanceProfile
from shpoet.scoring.features_for_scoring import build_scoring_features


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScoringResult:
    """Result bundle for a scored candidate."""

    score: CandidateScore
    anchor_hits: List[str]


class ScoringEngine:
    """Compute deterministic scores for candidate chunks."""

    def score_candidate(
        self,
        chunk: Dict[str, object],
        guidance: GuidanceProfile,
    ) -> ScoringResult:
        """Score a single chunk candidate against the guidance profile."""

        features = build_scoring_features(chunk, guidance.anchor_targets)
        anchor_hits = list(features["anchor_hits"])
        anchor_hit_count = int(features["anchor_hit_count"])
        token_count = int(features["token_count"])

        anchor_weight = float(guidance.priors.get("anchor_presence", 1.0))
        length_weight = float(guidance.priors.get("length_preference", 0.1))

        anchor_score = anchor_hit_count * anchor_weight
        length_score = -abs(token_count - 10) * length_weight

        total_score = anchor_score + length_score
        breakdown = {
            "anchor_score": anchor_score,
            "length_score": length_score,
        }

        score = CandidateScore(
            candidate_id=str(chunk.get("chunk_id", "")),
            total_score=total_score,
            breakdown=breakdown,
        )
        logger.debug("Scored candidate %s with %s", score.candidate_id, score.total_score)
        return ScoringResult(score=score, anchor_hits=anchor_hits)

    def score_path(
        self,
        candidate_scores: Iterable[CandidateScore],
    ) -> CandidateScore:
        """Aggregate candidate scores into a path score."""

        total = 0.0
        breakdown: Dict[str, float] = {}
        candidate_id = "path"
        for candidate in candidate_scores:
            total += candidate.total_score
            for key, value in candidate.breakdown.items():
                breakdown[key] = breakdown.get(key, 0.0) + value
        score = CandidateScore(candidate_id=candidate_id, total_score=total, breakdown=breakdown)
        logger.debug("Aggregated path score: %s", score.total_score)
        return score
