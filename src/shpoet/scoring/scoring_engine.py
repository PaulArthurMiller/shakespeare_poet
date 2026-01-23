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
        """Score a single chunk candidate against the guidance profile.

        Scoring factors:
        - anchor_presence: Reward for containing anchor keywords
        - length_preference: Penalty for deviating from ideal length
        - meter_preference: Reward for iambic meter conformity
        - emotion_alignment: Reward for matching target emotion
        """
        features = build_scoring_features(chunk, guidance.anchor_targets)
        anchor_hits = list(features["anchor_hits"])
        anchor_hit_count = int(features["anchor_hit_count"])
        token_count = int(features["token_count"])

        # Get weights from guidance priors
        anchor_weight = float(guidance.priors.get("anchor_presence", 1.0))
        length_weight = float(guidance.priors.get("length_preference", 0.1))
        meter_weight = float(guidance.priors.get("meter_preference", 0.0))
        emotion_weight = float(guidance.priors.get("emotion_alignment", 0.0))

        # Anchor score
        anchor_score = anchor_hit_count * anchor_weight

        # Length score (prefer ~10 syllables for pentameter)
        syllable_count = int(features["syllable_count"]) if features["syllable_count"] else token_count
        length_score = -abs(syllable_count - 10) * length_weight

        # Meter score (reward iambic conformity)
        iambic_score_val = float(features["iambic_score"])
        meter_score = iambic_score_val * meter_weight

        # Emotion alignment score
        emotion_score = 0.0
        if emotion_weight > 0:
            target_valence = float(guidance.priors.get("target_valence", 0.0))
            chunk_valence = float(features["emotion_valence"])
            valence_diff = abs(target_valence - chunk_valence)
            emotion_score = (1.0 - valence_diff) * emotion_weight

        total_score = anchor_score + length_score + meter_score + emotion_score
        breakdown = {
            "anchor_score": anchor_score,
            "length_score": length_score,
            "meter_score": meter_score,
            "emotion_score": emotion_score,
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
