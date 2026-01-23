"""Phonetic analysis using CMU Pronouncing Dictionary.

Provides phoneme extraction, rhyme class computation, stress patterns,
and alliteration detection. Includes fallback for archaic Shakespearean words.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Lazy-loaded archaic pronunciations
_archaic_pronunciations: Dict[str, List[str]] = {}

# Path to archaic pronunciations data
_ARCHAIC_DATA_PATH = Path(__file__).parent.parent.parent.parent / "data" / "archaic_pronunciations.json"

# Consonant clusters that commonly start words (for alliteration)
_INITIAL_CLUSTERS = re.compile(r"^([bcdfghjklmnpqrstvwxyz]+)", re.IGNORECASE)


_archaic_loaded: bool = False


def _load_archaic_pronunciations() -> Dict[str, List[str]]:
    """Load pronunciations for archaic words from data file."""
    global _archaic_pronunciations, _archaic_loaded
    if not _archaic_loaded:
        _archaic_loaded = True
        try:
            if _ARCHAIC_DATA_PATH.exists():
                with open(_ARCHAIC_DATA_PATH, "r", encoding="utf-8") as f:
                    data: Dict[str, List[str]] = json.load(f)
                    _archaic_pronunciations.update(data)
                logger.debug("Loaded %d archaic pronunciations", len(_archaic_pronunciations))
        except Exception as e:
            logger.warning("Could not load archaic pronunciations: %s", e)
    return _archaic_pronunciations


def get_phonemes(word: str) -> List[List[str]]:
    """Get CMU phoneme sequences for a word.

    May return multiple pronunciations for words with variants.

    Args:
        word: The word to look up

    Returns:
        List of phoneme lists (may be empty if word not found)
    """
    clean_word = re.sub(r"^[^a-zA-Z']+|[^a-zA-Z']+$", "", word).lower()
    if not clean_word:
        return []

    # Check archaic dictionary first
    archaic = _load_archaic_pronunciations()
    if clean_word in archaic:
        return [archaic[clean_word]]

    # Try CMU dictionary
    try:
        import pronouncing
        phones_list = pronouncing.phones_for_word(clean_word)
        if phones_list:
            return [phones.split() for phones in phones_list]
    except ImportError:
        logger.warning("pronouncing library not available")

    return []


def get_stress_pattern(phonemes: List[str]) -> str:
    """Extract stress pattern from phonemes.

    Stress markers in CMU:
    - 0: no stress
    - 1: primary stress
    - 2: secondary stress

    Args:
        phonemes: List of CMU phonemes

    Returns:
        str: Stress pattern string (e.g., "0101" for iambic)
    """
    pattern = []
    for phoneme in phonemes:
        # Vowel phonemes have stress markers (digits)
        for char in phoneme:
            if char.isdigit():
                pattern.append(char)
                break
    return "".join(pattern)


def compute_rhyme_class(phonemes: List[str]) -> str:
    """Compute rhyme class from phonemes.

    The rhyme class is the last stressed vowel plus all following phonemes.
    Words with the same rhyme class rhyme with each other.

    Args:
        phonemes: List of CMU phonemes

    Returns:
        str: Rhyme class string (empty if cannot be computed)
    """
    if not phonemes:
        return ""

    # Find the last stressed vowel (primary stress = 1)
    last_stressed_idx = -1
    for i, phoneme in enumerate(phonemes):
        if "1" in phoneme or "2" in phoneme:
            last_stressed_idx = i

    if last_stressed_idx < 0:
        # No stress found, use last vowel
        for i, phoneme in enumerate(phonemes):
            if any(c.isdigit() for c in phoneme):
                last_stressed_idx = i

    if last_stressed_idx < 0:
        return ""

    # Rhyme class is from last stressed vowel to end
    rhyme_phones = phonemes[last_stressed_idx:]

    # Remove stress markers for comparison
    normalized = []
    for p in rhyme_phones:
        clean = "".join(c for c in p if not c.isdigit())
        normalized.append(clean)

    return "_".join(normalized)


def get_alliteration_sound(word: str) -> str:
    """Get the initial consonant sound for alliteration matching.

    Args:
        word: The word to analyze

    Returns:
        str: Initial consonant cluster (lowercase), or empty if starts with vowel
    """
    clean_word = re.sub(r"^[^a-zA-Z]+", "", word).lower()
    if not clean_word:
        return ""

    # Check if starts with vowel
    if clean_word[0] in "aeiou":
        return ""

    # Get phonemes for more accurate analysis
    phonemes = get_phonemes(clean_word)
    if phonemes:
        first_phoneme = phonemes[0][0] if phonemes[0] else ""
        # Remove any stress markers
        first_phoneme = "".join(c for c in first_phoneme if not c.isdigit())
        return first_phoneme.upper()

    # Fallback to orthographic consonant cluster
    match = _INITIAL_CLUSTERS.match(clean_word)
    if match:
        cluster = match.group(1).lower()
        # Normalize common digraphs
        if cluster.startswith("ph"):
            return "F"
        if cluster.startswith("th"):
            return "TH"
        if cluster.startswith("ch"):
            return "CH"
        if cluster.startswith("sh"):
            return "SH"
        if cluster.startswith("wh"):
            return "W"
        return cluster[0].upper()

    return ""


def words_rhyme(word1: str, word2: str) -> bool:
    """Check if two words rhyme.

    Args:
        word1: First word
        word2: Second word

    Returns:
        bool: True if the words rhyme
    """
    phonemes1 = get_phonemes(word1)
    phonemes2 = get_phonemes(word2)

    if not phonemes1 or not phonemes2:
        return False

    # Check all pronunciation combinations
    for p1 in phonemes1:
        rc1 = compute_rhyme_class(p1)
        for p2 in phonemes2:
            rc2 = compute_rhyme_class(p2)
            if rc1 and rc2 and rc1 == rc2:
                return True

    return False


def words_alliterate(word1: str, word2: str) -> bool:
    """Check if two words alliterate.

    Args:
        word1: First word
        word2: Second word

    Returns:
        bool: True if the words alliterate (same initial consonant sound)
    """
    sound1 = get_alliteration_sound(word1)
    sound2 = get_alliteration_sound(word2)

    if not sound1 or not sound2:
        return False

    return sound1 == sound2


def extract_phonetic_features(text: str, tokens: List[str]) -> Dict[str, Any]:
    """Extract phonetic features for a text chunk.

    Args:
        text: The raw text
        tokens: List of word tokens

    Returns:
        Dict with keys:
        - phonemes: JSON-serializable phoneme list for first pronunciation
        - stress_pattern: Combined stress pattern string
        - rhyme_class: Rhyme class of last word
        - alliteration_sound: Initial consonant of first content word
    """
    if not tokens:
        return {
            "phonemes": [],
            "stress_pattern": "",
            "rhyme_class": "",
            "alliteration_sound": "",
        }

    # Get phonemes and stress for each word
    all_phonemes = []
    stress_patterns = []

    for token in tokens:
        token_phonemes = get_phonemes(token)
        if token_phonemes:
            # Use first pronunciation
            all_phonemes.append(token_phonemes[0])
            stress_patterns.append(get_stress_pattern(token_phonemes[0]))
        else:
            all_phonemes.append([])
            stress_patterns.append("")

    # Compute rhyme class from last word with phonemes
    rhyme_class = ""
    for phonemes in reversed(all_phonemes):
        if phonemes:
            rhyme_class = compute_rhyme_class(phonemes)
            break

    # Find first content word for alliteration
    # Skip common function words
    _FUNCTION_WORDS = {"a", "an", "the", "and", "or", "but", "to", "of", "in", "on", "at", "for", "with", "by"}
    alliteration_sound = ""
    for token in tokens:
        if token.lower() not in _FUNCTION_WORDS:
            alliteration_sound = get_alliteration_sound(token)
            if alliteration_sound:
                break

    # Combine stress patterns
    combined_stress = "".join(stress_patterns)

    return {
        "phonemes": all_phonemes,
        "stress_pattern": combined_stress,
        "rhyme_class": rhyme_class,
        "alliteration_sound": alliteration_sound,
    }
