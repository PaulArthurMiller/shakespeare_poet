"""Meter analysis for iambic pentameter and stress patterns.

Provides meter analysis using CMU pronouncing dictionary stress markers
with fallback heuristics. Optimized for Shakespearean iambic pentameter.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from shpoet.features.phonetics import get_phonemes, get_stress_pattern
from shpoet.features.syllables import get_syllable_counter

logger = logging.getLogger(__name__)

# Iambic pattern: unstressed (0) followed by stressed (1)
# In CMU: 0=no stress, 1=primary, 2=secondary
# We treat both 1 and 2 as "stressed" for iambic analysis
IAMBIC_PATTERN = "01"  # Unstressed-Stressed foot


@dataclass
class MeterAnalysis:
    """Result of meter analysis for a text chunk."""

    stress_pattern: str       # e.g., "01010101010" for perfect iambic pentameter
    syllable_count: int       # Total syllables
    is_iambic: bool           # True if pattern is predominantly iambic
    iambic_score: float       # 0.0-1.0 conformity to iambic pattern
    pentameter_fit: float     # How well it fits 10 syllables (0.0-1.0)

    @property
    def feet_count(self) -> int:
        """Number of metrical feet (pairs of syllables)."""
        return self.syllable_count // 2

    @property
    def is_pentameter(self) -> bool:
        """True if this is pentameter (5 feet, 10 syllables)."""
        return self.syllable_count == 10


def _normalize_stress(pattern: str) -> str:
    """Normalize stress pattern to binary (0/1).

    CMU uses 0=no stress, 1=primary, 2=secondary.
    For iambic analysis, we treat both 1 and 2 as stressed.
    """
    result = []
    for c in pattern:
        if c == "0":
            result.append("0")
        elif c in "12":
            result.append("1")
    return "".join(result)


def _compute_iambic_score(pattern: str) -> float:
    """Compute how well a pattern conforms to iambic meter.

    Perfect iambic: 01010101...
    Returns 0.0 (no match) to 1.0 (perfect iambic).
    """
    if not pattern:
        return 0.0

    normalized = _normalize_stress(pattern)
    if not normalized:
        return 0.0

    # Count matches with ideal iambic pattern
    matches = 0
    for i, c in enumerate(normalized):
        expected = "0" if i % 2 == 0 else "1"
        if c == expected:
            matches += 1

    return matches / len(normalized)


def _get_word_stress(word: str) -> str:
    """Get stress pattern for a single word.

    Uses CMU dictionary with fallback heuristics.
    """
    phonemes = get_phonemes(word)
    if phonemes:
        return get_stress_pattern(phonemes[0])

    # Fallback: estimate stress based on syllables
    # Single syllable words are typically stressed
    counter = get_syllable_counter()
    syllables = counter.count_syllables(word)

    if syllables == 1:
        # Function words get no stress, content words get stress
        _FUNCTION_WORDS = {"a", "an", "the", "and", "or", "but", "to", "of", "in", "on", "at", "for", "with", "by", "is", "it", "as", "that"}
        if word.lower() in _FUNCTION_WORDS:
            return "0"
        return "1"

    # Multi-syllable: assume alternating pattern starting with unstressed
    return "".join("0" if i % 2 == 0 else "1" for i in range(syllables))


def analyze_meter(text: str, tokens: Optional[List[str]] = None) -> MeterAnalysis:
    """Perform full meter analysis on a text chunk.

    Args:
        text: The text to analyze
        tokens: Optional pre-tokenized list (if None, will tokenize)

    Returns:
        MeterAnalysis with stress pattern and metrics
    """
    if tokens is None:
        tokens = re.findall(r"[A-Za-z']+", text)

    if not tokens:
        return MeterAnalysis(
            stress_pattern="",
            syllable_count=0,
            is_iambic=False,
            iambic_score=0.0,
            pentameter_fit=0.0,
        )

    # Build combined stress pattern from all words
    stress_parts = []
    for token in tokens:
        word_stress = _get_word_stress(token)
        stress_parts.append(word_stress)

    stress_pattern = "".join(stress_parts)

    # Count syllables
    counter = get_syllable_counter()
    syllable_count = sum(counter.count_syllables(t) for t in tokens)

    # Compute iambic score
    iambic_score = _compute_iambic_score(stress_pattern)

    # Determine if predominantly iambic (threshold: 0.6)
    is_iambic = iambic_score >= 0.6

    # Compute pentameter fit
    # Perfect fit at 10 syllables, decreases with distance
    if syllable_count == 0:
        pentameter_fit = 0.0
    else:
        distance = abs(syllable_count - 10)
        # Fit decreases by 0.2 for each syllable away from 10
        pentameter_fit = max(0.0, 1.0 - distance * 0.2)

    return MeterAnalysis(
        stress_pattern=stress_pattern,
        syllable_count=syllable_count,
        is_iambic=is_iambic,
        iambic_score=iambic_score,
        pentameter_fit=pentameter_fit,
    )


def check_meter_adjacency(
    prev_pattern: str,
    curr_pattern: str,
    strictness: float = 0.5,
) -> Tuple[bool, float]:
    """Check if two stress patterns combine well metrically.

    When concatenating two chunks, the ending stress of the first
    should flow naturally into the starting stress of the second
    for good iambic meter.

    Args:
        prev_pattern: Stress pattern of previous chunk
        curr_pattern: Stress pattern of current chunk
        strictness: 0.0 (lenient) to 1.0 (strict) - threshold for acceptance

    Returns:
        Tuple of (acceptable, score) where score is 0.0-1.0
    """
    if not prev_pattern or not curr_pattern:
        # Can't check adjacency without patterns
        return True, 1.0

    prev_norm = _normalize_stress(prev_pattern)
    curr_norm = _normalize_stress(curr_pattern)

    if not prev_norm or not curr_norm:
        return True, 1.0

    prev_end = prev_norm[-1]
    curr_start = curr_norm[0]

    # For iambic flow: previous should end stressed (1), current start unstressed (0)
    # Or: previous ends unstressed (0), current starts stressed (1)
    # Both maintain the alternating pattern

    if prev_end == "1" and curr_start == "0":
        # Perfect iambic transition: stressed -> unstressed
        score = 1.0
    elif prev_end == "0" and curr_start == "1":
        # Also good: unstressed -> stressed (continues pattern)
        score = 0.9
    elif prev_end == curr_start:
        # Same stress level adjacent - disrupts meter
        score = 0.3
    else:
        score = 0.5

    acceptable = score >= (1.0 - strictness)
    return acceptable, score


def get_meter_features(text: str, tokens: Optional[List[str]] = None) -> Dict[str, Any]:
    """Extract meter features for a text chunk.

    Convenience function that returns a dictionary suitable for
    metadata storage.

    Args:
        text: The text to analyze
        tokens: Optional pre-tokenized list

    Returns:
        Dict with meter features
    """
    analysis = analyze_meter(text, tokens)

    return {
        "stress_pattern": analysis.stress_pattern,
        "syllable_count": analysis.syllable_count,
        "is_iambic": analysis.is_iambic,
        "iambic_score": round(analysis.iambic_score, 3),
        "pentameter_fit": round(analysis.pentameter_fit, 3),
    }
