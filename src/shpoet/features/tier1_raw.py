"""Tier-1 raw feature extraction for line chunks."""

from __future__ import annotations

import logging
import re
from typing import Dict, Iterable, List


logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"[A-Za-z']+")
_VOWEL_RE = re.compile(r"[aeiouy]+", re.IGNORECASE)
_FUNCTION_WORDS = {
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
    """Tokenize text into word tokens for feature extraction."""

    return _WORD_RE.findall(text)


def _punctuation_profile(text: str) -> Dict[str, int]:
    """Count punctuation marks in the text for quick profiling."""

    return {
        "comma": text.count(","),
        "period": text.count("."),
        "question": text.count("?"),
        "exclamation": text.count("!"),
        "semicolon": text.count(";"),
        "colon": text.count(":"),
    }


def _estimate_syllables(token: str) -> int:
    """Estimate syllables in a token using a simple vowel-group heuristic."""

    groups = _VOWEL_RE.findall(token)
    return max(1, len(groups)) if token else 0


def _rhyme_tail(token: str) -> str:
    """Estimate a rhyme tail based on the last few characters of a token."""

    if len(token) <= 3:
        return token.lower()
    return token[-3:].lower()


def _function_word_flags(tokens: List[str]) -> Dict[str, bool]:
    """Determine if tokens start or end with function words."""

    if not tokens:
        return {"starts_with_function_word": False, "ends_with_function_word": False}
    start = tokens[0].lower() in _FUNCTION_WORDS
    end = tokens[-1].lower() in _FUNCTION_WORDS
    return {"starts_with_function_word": start, "ends_with_function_word": end}


def extract_tier1_features(text: str) -> Dict[str, object]:
    """Extract Tier-1 raw features for a single line of text."""

    tokens = _tokenize(text)
    first_token = tokens[0].lower() if tokens else ""
    last_token = tokens[-1].lower() if tokens else ""
    syllable_estimate = sum(_estimate_syllables(token) for token in tokens)
    features: Dict[str, object] = {
        "token_count": len(tokens),
        "char_count": len(text),
        "tokens": tokens,
        "first_token": first_token,
        "last_token": last_token,
        "punctuation": _punctuation_profile(text),
        "left_context": "",
        "right_context": "",
        "syllable_estimate": syllable_estimate,
        "rhyme_tail": _rhyme_tail(last_token) if last_token else "",
    }
    features.update(_function_word_flags(tokens))
    return features


def apply_tier1_features(chunks: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    """Apply Tier-1 features to a list of chunk dictionaries."""

    enriched: List[Dict[str, object]] = []
    for chunk in chunks:
        text = str(chunk.get("text", ""))
        features = extract_tier1_features(text)
        merged = {**chunk, **features}
        enriched.append(merged)

    logger.info("Applied Tier-1 features to %s chunks", len(enriched))
    return enriched
