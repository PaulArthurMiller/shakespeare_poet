"""Semantic feature extraction for emotion, rhetoric, and topics.

Provides emotion valence/intensity, rhetoric labels, and topic clustering
using word lists and optional spaCy vectors.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from shpoet.features.nlp_context import NLPContext

logger = logging.getLogger(__name__)

# Emotion lexicons (simplified - can be expanded)
# Valence: positive words = +1, negative = -1
POSITIVE_WORDS = frozenset([
    "love", "joy", "happy", "bright", "fair", "sweet", "good", "beautiful",
    "gentle", "kind", "gracious", "noble", "true", "virtue", "honor", "glory",
    "peace", "hope", "faith", "delight", "pleasure", "blessed", "heaven",
    "light", "golden", "divine", "eternal", "pure", "radiant", "splendor",
])

NEGATIVE_WORDS = frozenset([
    "hate", "death", "dark", "foul", "bitter", "evil", "terrible", "cruel",
    "wicked", "vile", "cursed", "damned", "hell", "sin", "woe", "grief",
    "sorrow", "pain", "blood", "murder", "fear", "dread", "doom", "grave",
    "black", "poison", "treachery", "despair", "anguish", "torment",
])

# Intensity words (amplifiers)
INTENSITY_WORDS = frozenset([
    "very", "most", "greatly", "deeply", "truly", "utterly", "extremely",
    "infinitely", "exceedingly", "profoundly", "mightily", "fierce", "wild",
])

# Rhetoric labels based on patterns
RHETORIC_PATTERNS = {
    "question": ["?", "what", "why", "how", "when", "where", "who", "which", "wherefore"],
    "exclamation": ["!", "o", "oh", "alas", "hark", "lo", "fie"],
    "command": ["let", "come", "go", "give", "take", "make", "be", "do"],
    "negation": ["not", "no", "never", "neither", "nor", "none", "nothing"],
    "comparison": ["like", "as", "than", "more", "less", "most", "least"],
}

# Topic clusters (keywords associated with themes)
TOPIC_CLUSTERS = {
    "love": ["love", "heart", "kiss", "embrace", "beloved", "passion", "desire", "affection"],
    "death": ["death", "die", "dead", "grave", "tomb", "funeral", "corpse", "ghost"],
    "power": ["king", "crown", "throne", "rule", "power", "kingdom", "reign", "lord"],
    "honor": ["honor", "noble", "virtue", "glory", "fame", "reputation", "worthy"],
    "nature": ["sun", "moon", "star", "flower", "tree", "sea", "wind", "earth", "sky"],
    "time": ["time", "hour", "day", "night", "year", "age", "moment", "eternity"],
    "war": ["war", "battle", "sword", "army", "fight", "enemy", "victory", "defeat"],
    "fate": ["fate", "fortune", "destiny", "chance", "doom", "prophecy", "oracle"],
}


def _compute_emotion_valence(tokens: List[str]) -> float:
    """Compute emotion valence from -1.0 (negative) to +1.0 (positive).

    Args:
        tokens: List of word tokens

    Returns:
        float: Valence score (-1.0 to +1.0)
    """
    if not tokens:
        return 0.0

    positive_count = sum(1 for t in tokens if t.lower() in POSITIVE_WORDS)
    negative_count = sum(1 for t in tokens if t.lower() in NEGATIVE_WORDS)

    total = positive_count + negative_count
    if total == 0:
        return 0.0

    # Normalize to -1 to +1 range
    return (positive_count - negative_count) / total


def _compute_emotion_intensity(tokens: List[str]) -> float:
    """Compute emotion intensity from 0.0 (neutral) to 1.0 (intense).

    Args:
        tokens: List of word tokens

    Returns:
        float: Intensity score (0.0 to 1.0)
    """
    if not tokens:
        return 0.0

    # Count emotion words and intensity modifiers
    emotion_count = sum(1 for t in tokens if t.lower() in POSITIVE_WORDS or t.lower() in NEGATIVE_WORDS)
    intensity_count = sum(1 for t in tokens if t.lower() in INTENSITY_WORDS)

    # Base intensity from emotion word density
    base = emotion_count / len(tokens)

    # Boost from intensity modifiers
    boost = min(0.3, intensity_count * 0.1)

    return min(1.0, base + boost)


def _detect_rhetoric_label(text: str, tokens: List[str]) -> str:
    """Detect the primary rhetoric type.

    Args:
        text: The raw text
        tokens: List of word tokens

    Returns:
        str: Rhetoric label (question, exclamation, command, etc.)
    """
    text_lower = text.lower()
    tokens_lower = [t.lower() for t in tokens]

    # Check question
    if "?" in text or any(t in tokens_lower[:2] for t in ["what", "why", "how", "when", "where", "who", "which", "wherefore"]):
        return "question"

    # Check exclamation
    if "!" in text or any(t in tokens_lower[:2] for t in ["o", "oh", "alas", "hark", "lo", "fie"]):
        return "exclamation"

    # Check command (imperative)
    if tokens_lower and tokens_lower[0] in ["let", "come", "go", "give", "take", "make", "be", "do"]:
        return "command"

    # Check negation
    if any(t in tokens_lower for t in ["not", "no", "never", "neither", "nor", "none"]):
        return "negation"

    # Check comparison
    if any(t in tokens_lower for t in ["like", "as", "than", "more", "less"]):
        return "comparison"

    return "statement"


def _detect_topic_cluster(tokens: List[str]) -> str:
    """Detect the primary topic cluster.

    Args:
        tokens: List of word tokens

    Returns:
        str: Topic cluster name or "general"
    """
    tokens_lower = {t.lower() for t in tokens}

    best_topic = "general"
    best_score = 0

    for topic, keywords in TOPIC_CLUSTERS.items():
        score = sum(1 for k in keywords if k in tokens_lower)
        if score > best_score:
            best_score = score
            best_topic = topic

    return best_topic


def _get_embedding_similarity(text: str, topic: str) -> float:
    """Compute semantic similarity using spaCy vectors.

    Args:
        text: The text to analyze
        topic: Topic word to compare against

    Returns:
        float: Similarity score (0.0 to 1.0)
    """
    try:
        doc = NLPContext.get_doc(text)
        topic_doc = NLPContext.get_doc(topic)

        if doc.has_vector and topic_doc.has_vector:
            return doc.similarity(topic_doc)
    except Exception as e:
        logger.debug("Could not compute embedding similarity: %s", e)

    return 0.0


def extract_semantic_features(
    text: str,
    tokens: Optional[List[str]] = None,
    embedding: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Extract semantic features for a text chunk.

    Args:
        text: The text to analyze
        tokens: Optional pre-tokenized list
        embedding: Optional pre-computed embedding (unused currently)

    Returns:
        Dict with keys:
        - emotion_valence: -1.0 to +1.0 (negative to positive)
        - emotion_intensity: 0.0 to 1.0
        - rhetoric_label: question, exclamation, command, etc.
        - topic_cluster: love, death, power, etc.
    """
    if tokens is None:
        import re
        tokens = re.findall(r"[A-Za-z']+", text)

    if not tokens:
        return {
            "emotion_valence": 0.0,
            "emotion_intensity": 0.0,
            "rhetoric_label": "empty",
            "topic_cluster": "general",
        }

    valence = _compute_emotion_valence(tokens)
    intensity = _compute_emotion_intensity(tokens)
    rhetoric = _detect_rhetoric_label(text, tokens)
    topic = _detect_topic_cluster(tokens)

    return {
        "emotion_valence": round(valence, 3),
        "emotion_intensity": round(intensity, 3),
        "rhetoric_label": rhetoric,
        "topic_cluster": topic,
    }


def compute_semantic_similarity(chunk_a: Dict[str, Any], chunk_b: Dict[str, Any]) -> float:
    """Compute semantic similarity between two chunks.

    Uses topic cluster matching and emotion alignment.

    Args:
        chunk_a: First chunk with semantic features
        chunk_b: Second chunk with semantic features

    Returns:
        float: Similarity score (0.0 to 1.0)
    """
    # Topic match
    topic_a = chunk_a.get("topic_cluster", "general")
    topic_b = chunk_b.get("topic_cluster", "general")
    topic_match = 1.0 if topic_a == topic_b else 0.3

    # Emotion alignment (similar valence)
    valence_a = float(chunk_a.get("emotion_valence", 0.0))
    valence_b = float(chunk_b.get("emotion_valence", 0.0))
    valence_diff = abs(valence_a - valence_b)
    valence_match = 1.0 - (valence_diff / 2.0)  # Max diff is 2.0

    # Weighted combination
    similarity = 0.6 * topic_match + 0.4 * valence_match

    return round(similarity, 3)
