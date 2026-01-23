"""Tier-3 lazy feature extraction with caching.

Provides on-demand extraction of expensive features that are not
needed for every query. Uses caching to avoid recomputation.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List, Optional

from shpoet.features.nlp_context import NLPContext

logger = logging.getLogger(__name__)

# Module-level cache for expensive computations
_feature_cache: Dict[str, Dict[str, Any]] = {}
_cache_max_size = 10000


def _cache_key(text: str, feature_name: str) -> str:
    """Generate a cache key for a text-feature combination."""
    text_hash = hashlib.md5(text.encode()).hexdigest()[:12]
    return f"{feature_name}:{text_hash}"


def _get_cached(key: str) -> Optional[Dict[str, Any]]:
    """Get a cached feature result."""
    return _feature_cache.get(key)


def _set_cached(key: str, value: Dict[str, Any]) -> None:
    """Store a feature result in cache."""
    global _feature_cache

    # LRU-style eviction
    if len(_feature_cache) >= _cache_max_size:
        evict_count = max(1, _cache_max_size // 10)
        keys_to_remove = list(_feature_cache.keys())[:evict_count]
        for k in keys_to_remove:
            del _feature_cache[k]

    _feature_cache[key] = value


def clear_cache() -> None:
    """Clear the feature cache."""
    global _feature_cache
    _feature_cache.clear()
    logger.debug("Cleared Tier-3 feature cache")


def get_dependency_tree(text: str) -> Dict[str, Any]:
    """Get full dependency tree (expensive NLP operation).

    Args:
        text: The text to analyze

    Returns:
        Dict with dependency tree information
    """
    cache_key = _cache_key(text, "dependency_tree")
    cached = _get_cached(cache_key)
    if cached:
        return cached

    doc = NLPContext.get_doc(text)

    tree = {
        "tokens": [],
        "edges": [],
    }

    for token in doc:
        tree["tokens"].append({
            "idx": token.i,
            "text": token.text,
            "lemma": token.lemma_,
            "pos": token.pos_,
            "tag": token.tag_,
            "dep": token.dep_,
            "head": token.head.i,
        })

        if token.head != token:
            tree["edges"].append({
                "from": token.head.i,
                "to": token.i,
                "label": token.dep_,
            })

    _set_cached(cache_key, tree)
    return tree


def get_named_entities(text: str) -> List[Dict[str, Any]]:
    """Extract named entities from text.

    Args:
        text: The text to analyze

    Returns:
        List of entity dictionaries with text, label, start, end
    """
    cache_key = _cache_key(text, "named_entities")
    cached = _get_cached(cache_key)
    if cached:
        return cached.get("entities", [])

    doc = NLPContext.get_doc(text)

    entities = []
    for ent in doc.ents:
        entities.append({
            "text": ent.text,
            "label": ent.label_,
            "start": ent.start_char,
            "end": ent.end_char,
        })

    result = {"entities": entities}
    _set_cached(cache_key, result)
    return entities


def get_noun_phrases(text: str) -> List[str]:
    """Extract noun phrases from text.

    Args:
        text: The text to analyze

    Returns:
        List of noun phrase strings
    """
    cache_key = _cache_key(text, "noun_phrases")
    cached = _get_cached(cache_key)
    if cached:
        return cached.get("phrases", [])

    doc = NLPContext.get_doc(text)

    phrases = [chunk.text for chunk in doc.noun_chunks]

    result = {"phrases": phrases}
    _set_cached(cache_key, result)
    return phrases


def get_sentence_structure(text: str) -> Dict[str, Any]:
    """Analyze sentence structure (subject, verb, object).

    Args:
        text: The text to analyze

    Returns:
        Dict with subject, verb, object components
    """
    cache_key = _cache_key(text, "sentence_structure")
    cached = _get_cached(cache_key)
    if cached:
        return cached

    doc = NLPContext.get_doc(text)

    structure = {
        "subject": None,
        "verb": None,
        "object": None,
        "modifiers": [],
    }

    for token in doc:
        if token.dep_ in ("nsubj", "nsubjpass"):
            structure["subject"] = token.text
        elif token.dep_ == "ROOT" and token.pos_ == "VERB":
            structure["verb"] = token.text
        elif token.dep_ in ("dobj", "pobj", "obj"):
            structure["object"] = token.text
        elif token.dep_ in ("amod", "advmod"):
            structure["modifiers"].append(token.text)

    _set_cached(cache_key, structure)
    return structure


def get_text_embedding(text: str) -> Optional[List[float]]:
    """Get spaCy vector embedding for text.

    Args:
        text: The text to embed

    Returns:
        List of floats representing the embedding, or None if unavailable
    """
    cache_key = _cache_key(text, "embedding")
    cached = _get_cached(cache_key)
    if cached:
        return cached.get("vector")

    doc = NLPContext.get_doc(text)

    if doc.has_vector:
        vector = doc.vector.tolist()
        _set_cached(cache_key, {"vector": vector})
        return vector

    return None


def compute_semantic_distance(text_a: str, text_b: str) -> float:
    """Compute semantic distance between two texts.

    Uses spaCy vectors for similarity computation.

    Args:
        text_a: First text
        text_b: Second text

    Returns:
        float: Distance from 0.0 (identical) to 1.0 (unrelated)
    """
    doc_a = NLPContext.get_doc(text_a)
    doc_b = NLPContext.get_doc(text_b)

    if doc_a.has_vector and doc_b.has_vector:
        similarity = doc_a.similarity(doc_b)
        # Convert similarity to distance
        return max(0.0, 1.0 - similarity)

    return 0.5  # Neutral distance when vectors unavailable


def extract_lazy_features(text: str, features: List[str]) -> Dict[str, Any]:
    """Extract specified lazy features on demand.

    Args:
        text: The text to analyze
        features: List of feature names to extract

    Returns:
        Dict with requested features
    """
    result = {}

    for feature in features:
        if feature == "dependency_tree":
            result["dependency_tree"] = get_dependency_tree(text)
        elif feature == "named_entities":
            result["named_entities"] = get_named_entities(text)
        elif feature == "noun_phrases":
            result["noun_phrases"] = get_noun_phrases(text)
        elif feature == "sentence_structure":
            result["sentence_structure"] = get_sentence_structure(text)
        elif feature == "embedding":
            result["embedding"] = get_text_embedding(text)
        else:
            logger.warning("Unknown lazy feature requested: %s", feature)

    return result
