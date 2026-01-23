"""Accurate syllable counting using multiple strategies.

Uses pyphen (dictionary-based hyphenation) as primary method,
with CMU pronouncing dictionary and vowel heuristics as fallbacks.
Special handling for archaic Shakespearean words.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Lazy-loaded components
_pyphen_dict: Any = None
_pyphen_loaded: bool = False
_archaic_syllables: Dict[str, int] = {}
_archaic_loaded: bool = False

# Vowel pattern for fallback heuristic
_VOWEL_RE = re.compile(r"[aeiouy]+", re.IGNORECASE)

# Path to archaic pronunciations data
_ARCHAIC_DATA_PATH = Path(__file__).parent.parent.parent.parent / "data" / "archaic_pronunciations.json"


def _get_pyphen_dict() -> Any:
    """Lazy-load the pyphen English dictionary."""
    global _pyphen_dict, _pyphen_loaded
    if not _pyphen_loaded:
        _pyphen_loaded = True
        try:
            import pyphen
            _pyphen_dict = pyphen.Pyphen(lang="en_US")
            logger.debug("Loaded pyphen dictionary for en_US")
        except ImportError:
            logger.warning("pyphen not installed. Syllable counting will use fallbacks.")
            _pyphen_dict = None
    return _pyphen_dict


def _load_archaic_syllables() -> Dict[str, int]:
    """Load syllable counts for archaic words from data file."""
    global _archaic_syllables, _archaic_loaded
    if not _archaic_loaded:
        _archaic_loaded = True
        try:
            if _ARCHAIC_DATA_PATH.exists():
                with open(_ARCHAIC_DATA_PATH, "r", encoding="utf-8") as f:
                    data: Dict[str, Any] = json.load(f)
                # Extract syllable counts from phoneme data
                for word, phonemes in data.items():
                    if isinstance(phonemes, list):
                        # Count vowel phonemes (those with digits are stressed vowels)
                        syllable_count = sum(
                            1 for p in phonemes if isinstance(p, str) and any(c.isdigit() for c in p)
                        )
                        _archaic_syllables[word.lower()] = max(1, syllable_count)
                logger.debug("Loaded %d archaic syllable entries", len(_archaic_syllables))
        except Exception as e:
            logger.warning("Could not load archaic pronunciations: %s", e)
    return _archaic_syllables


def _count_syllables_cmu(word: str) -> Optional[int]:
    """Count syllables using CMU pronouncing dictionary."""
    try:
        import pronouncing
        phones_list = pronouncing.phones_for_word(word.lower())
        if phones_list:
            # Use first pronunciation
            phones = phones_list[0]
            # Count vowel phonemes (contain digits for stress)
            return pronouncing.syllable_count(phones)
    except ImportError:
        pass
    return None


def _count_syllables_vowel_heuristic(word: str) -> int:
    """Estimate syllables using vowel group heuristic."""
    # Remove leading/trailing punctuation
    clean = re.sub(r"^[^a-zA-Z]+|[^a-zA-Z]+$", "", word)
    if not clean:
        return 1

    # Find vowel groups
    groups = _VOWEL_RE.findall(clean.lower())
    count = len(groups)

    # Adjustments for common patterns
    if clean.lower().endswith("e") and len(clean) > 2:
        # Silent 'e' at end (but not words like "be", "me")
        if not clean.lower().endswith(("le", "re", "ve", "ce", "ge", "se", "ze")):
            count = max(1, count - 1)
    if clean.lower().endswith("ed") and len(clean) > 3:
        # "-ed" often silent unless preceded by t/d
        if clean[-3].lower() not in "td":
            count = max(1, count - 1)
    if clean.lower().endswith("es") and len(clean) > 3:
        # "-es" often silent
        count = max(1, count - 1)

    return max(1, count)


class SyllableCounter:
    """Accurate syllable counter with multiple fallback strategies."""

    def __init__(self):
        """Initialize the syllable counter."""
        self._archaic = _load_archaic_syllables()

    def count_syllables(self, word: str) -> int:
        """Count syllables in a word using best available method.

        Strategy:
        1. Check archaic word dictionary (exact match)
        2. Try CMU pronouncing dictionary (most accurate)
        3. Try pyphen (dictionary-based hyphenation)
        4. Fall back to vowel heuristic

        Args:
            word: The word to count syllables for

        Returns:
            int: Number of syllables (minimum 1)
        """
        clean_word = re.sub(r"^[^a-zA-Z']+|[^a-zA-Z']+$", "", word)
        if not clean_word:
            return 1

        lower_word = clean_word.lower()

        # 1. Check archaic dictionary (handles contractions like 'tis, o'er)
        if lower_word in self._archaic:
            return self._archaic[lower_word]

        # 2. Try CMU dictionary first (most accurate for common words)
        cmu_count = _count_syllables_cmu(clean_word)
        if cmu_count is not None:
            return cmu_count

        # 3. Try pyphen as secondary source
        pyphen_dict = _get_pyphen_dict()
        if pyphen_dict:
            # Strip apostrophes for pyphen lookup
            pyphen_word = clean_word.replace("'", "")
            if pyphen_word:
                hyphenated = pyphen_dict.inserted(pyphen_word)
                if hyphenated and "-" in hyphenated:
                    count = hyphenated.count("-") + 1
                    if count > 0:
                        return count

        # 4. Vowel heuristic fallback
        return _count_syllables_vowel_heuristic(clean_word)

    def get_syllable_breakdown(self, word: str) -> List[str]:
        """Split a word into its syllables.

        Args:
            word: The word to break down

        Returns:
            List[str]: List of syllable strings
        """
        clean_word = re.sub(r"^[^a-zA-Z']+|[^a-zA-Z']+$", "", word)
        if not clean_word:
            return [word] if word else []

        # Try pyphen for hyphenation
        pyphen_dict = _get_pyphen_dict()
        if pyphen_dict:
            hyphenated = pyphen_dict.inserted(clean_word)
            if hyphenated and "-" in hyphenated:
                return hyphenated.split("-")

        # Fallback: return word as single syllable
        return [clean_word]

    def count_text_syllables(self, text: str) -> int:
        """Count total syllables in a text string.

        Args:
            text: The text to count syllables in

        Returns:
            int: Total syllable count
        """
        words = re.findall(r"[A-Za-z']+", text)
        return sum(self.count_syllables(word) for word in words)

    def count_tokens_syllables(self, tokens: List[str]) -> int:
        """Count total syllables in a list of tokens.

        Args:
            tokens: List of word tokens

        Returns:
            int: Total syllable count
        """
        return sum(self.count_syllables(token) for token in tokens)


# Module-level singleton
_syllable_counter = None


def get_syllable_counter() -> SyllableCounter:
    """Get the singleton syllable counter instance."""
    global _syllable_counter
    if _syllable_counter is None:
        _syllable_counter = SyllableCounter()
    return _syllable_counter


def count_syllables(word: str) -> int:
    """Count syllables in a word (convenience function)."""
    return get_syllable_counter().count_syllables(word)


def count_text_syllables(text: str) -> int:
    """Count syllables in text (convenience function)."""
    return get_syllable_counter().count_text_syllables(text)
