"""Tier-2 derived feature extraction for chunk enrichment.

Orchestrates batch extraction of phonetics, meter, syntax, and semantic
features to build comprehensive metadata for corpus indexing.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterable, List

from shpoet.features.meter import get_meter_features
from shpoet.features.phonetics import extract_phonetic_features
from shpoet.features.semantics import extract_semantic_features
from shpoet.features.syntax import extract_syntax_features

logger = logging.getLogger(__name__)


def extract_tier2_features(text: str, tokens: List[str]) -> Dict[str, Any]:
    """Extract all Tier-2 features for a single chunk.

    Combines phonetics, meter, syntax, and semantics into a unified
    feature dictionary suitable for ChromaDB metadata.

    Args:
        text: The raw text
        tokens: List of word tokens

    Returns:
        Dict with all Tier-2 features
    """
    features = {}

    # Phonetic features
    phonetic = extract_phonetic_features(text, tokens)
    features["phonemes"] = json.dumps(phonetic["phonemes"])
    features["stress_pattern"] = phonetic["stress_pattern"]
    features["rhyme_class"] = phonetic["rhyme_class"]
    features["alliteration_sound"] = phonetic["alliteration_sound"]

    # Meter features
    meter = get_meter_features(text, tokens)
    features["syllable_count"] = meter["syllable_count"]
    features["is_iambic"] = meter["is_iambic"]
    features["iambic_score"] = meter["iambic_score"]

    # Syntax features
    syntax = extract_syntax_features(text, tokens)
    features["pos_tags"] = syntax["pos_tags"]
    features["pos_first"] = syntax["pos_first"]
    features["pos_last"] = syntax["pos_last"]
    features["grammatical_role"] = syntax["grammatical_role"]
    features["has_verb"] = syntax["has_verb"]
    features["has_noun"] = syntax["has_noun"]
    features["clause_type"] = syntax["clause_type"]

    # Semantic features
    semantic = extract_semantic_features(text, tokens)
    features["emotion_valence"] = semantic["emotion_valence"]
    features["emotion_intensity"] = semantic["emotion_intensity"]
    features["rhetoric_label"] = semantic["rhetoric_label"]
    features["topic_cluster"] = semantic["topic_cluster"]

    return features


def apply_tier2_features(chunks: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Apply Tier-2 features to a list of chunk dictionaries.

    This is the main batch processing function for index building.
    Each chunk dict should have 'text' and 'tokens' keys.

    Args:
        chunks: Iterable of chunk dictionaries

    Returns:
        List of enriched chunk dictionaries with Tier-2 features
    """
    enriched: List[Dict[str, Any]] = []
    chunk_count = 0

    for chunk in chunks:
        text = str(chunk.get("text", ""))
        tokens = chunk.get("tokens", [])

        if not tokens and text:
            # Fallback tokenization
            import re
            tokens = re.findall(r"[A-Za-z']+", text)

        # Extract Tier-2 features
        tier2_features = extract_tier2_features(text, tokens)

        # Merge with existing chunk data
        merged = {**chunk, **tier2_features}
        enriched.append(merged)
        chunk_count += 1

        if chunk_count % 100 == 0:
            logger.info("Processed %d chunks for Tier-2 features", chunk_count)

    logger.info("Applied Tier-2 features to %d chunks", len(enriched))
    return enriched


def get_tier2_metadata_keys() -> List[str]:
    """Return the list of Tier-2 metadata field names.

    Useful for schema documentation and validation.

    Returns:
        List of metadata key names
    """
    return [
        # Phonetics
        "phonemes",
        "stress_pattern",
        "rhyme_class",
        "alliteration_sound",
        # Meter
        "syllable_count",
        "is_iambic",
        "iambic_score",
        # Syntax
        "pos_tags",
        "pos_first",
        "pos_last",
        "grammatical_role",
        "has_verb",
        "has_noun",
        "clause_type",
        # Semantics
        "emotion_valence",
        "emotion_intensity",
        "rhetoric_label",
        "topic_cluster",
    ]
