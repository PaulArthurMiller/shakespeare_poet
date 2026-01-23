"""Rhyme constraint for candidate chunk filtering.

Supports rhyme scheme enforcement by matching chunks based on
their rhyme class (last stressed vowel + following phonemes).
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from shpoet.features.phonetics import compute_rhyme_class, get_phonemes

logger = logging.getLogger(__name__)


class RhymeConstraint:
    """Apply rhyme-based filtering rules for chunk selection.

    Can enforce rhyme schemes (ABAB, etc.) or find rhyming pairs.
    """

    def __init__(self) -> None:
        """Initialize the rhyme constraint."""
        # Track rhyme classes at line positions for scheme enforcement
        self._rhyme_scheme: Dict[str, str] = {}  # position -> rhyme_class
        self._scheme_pattern: str = ""  # e.g., "ABAB"

    def set_rhyme_scheme(self, pattern: str) -> None:
        """Set the rhyme scheme pattern to enforce.

        Args:
            pattern: Rhyme scheme like "ABAB", "AABB", "ABBA"
                    Each letter position will rhyme with same letters
        """
        self._scheme_pattern = pattern.upper()
        self._rhyme_scheme.clear()

    def register_line_rhyme(self, position: int, rhyme_class: str) -> None:
        """Register the rhyme class for a line position.

        Args:
            position: 0-indexed line position
            rhyme_class: The rhyme class of the line's last word
        """
        if position < len(self._scheme_pattern):
            scheme_letter = self._scheme_pattern[position]
            # Store the rhyme class for this scheme letter
            if scheme_letter not in self._rhyme_scheme:
                self._rhyme_scheme[scheme_letter] = rhyme_class
            logger.debug("Registered rhyme %s at position %d (letter %s)",
                        rhyme_class, position, scheme_letter)

    def get_required_rhyme(self, position: int) -> Optional[str]:
        """Get the required rhyme class for a position.

        Args:
            position: 0-indexed line position

        Returns:
            Required rhyme class, or None if no requirement
        """
        if position >= len(self._scheme_pattern):
            return None

        scheme_letter = self._scheme_pattern[position]
        return self._rhyme_scheme.get(scheme_letter)

    def evaluate(
        self,
        candidate_chunk: Dict[str, object],
        position: int,
    ) -> Tuple[bool, str]:
        """Check if a candidate chunk satisfies rhyme requirements.

        Args:
            candidate_chunk: The chunk being evaluated
            position: The line position this chunk would fill

        Returns:
            Tuple of (passed, reason) where reason explains failure
        """
        if not self._scheme_pattern:
            # No scheme to enforce
            return True, "ok"

        if position >= len(self._scheme_pattern):
            # Beyond scheme - accept
            return True, "ok"

        required = self.get_required_rhyme(position)
        if required is None:
            # First occurrence of this rhyme letter - accept anything
            return True, "ok"

        # Get candidate's rhyme class
        candidate_rhyme = str(candidate_chunk.get("rhyme_class", ""))

        if not candidate_rhyme:
            # No rhyme class available - compute from last token
            last_token = str(candidate_chunk.get("last_token", ""))
            if last_token:
                phonemes = get_phonemes(last_token)
                if phonemes:
                    candidate_rhyme = compute_rhyme_class(phonemes[0])

        if not candidate_rhyme:
            # Still no rhyme - accept (can't evaluate)
            return True, "ok"

        # Check if rhymes match
        if candidate_rhyme == required:
            return True, "ok"

        return False, "rhyme_mismatch"

    def evaluate_pair(
        self,
        chunk_a: Dict[str, object],
        chunk_b: Dict[str, object],
    ) -> Tuple[bool, float]:
        """Check if two chunks rhyme with each other.

        Args:
            chunk_a: First chunk
            chunk_b: Second chunk

        Returns:
            Tuple of (rhymes, similarity) where similarity is 0.0-1.0
        """
        rhyme_a = str(chunk_a.get("rhyme_class", ""))
        rhyme_b = str(chunk_b.get("rhyme_class", ""))

        # If missing, try to compute from last tokens
        if not rhyme_a:
            last_a = str(chunk_a.get("last_token", ""))
            if last_a:
                phonemes = get_phonemes(last_a)
                if phonemes:
                    rhyme_a = compute_rhyme_class(phonemes[0])

        if not rhyme_b:
            last_b = str(chunk_b.get("last_token", ""))
            if last_b:
                phonemes = get_phonemes(last_b)
                if phonemes:
                    rhyme_b = compute_rhyme_class(phonemes[0])

        if not rhyme_a or not rhyme_b:
            return False, 0.0

        # Exact match
        if rhyme_a == rhyme_b:
            return True, 1.0

        # Partial similarity (share some ending phonemes)
        parts_a = rhyme_a.split("_")
        parts_b = rhyme_b.split("_")

        # Count matching phonemes from the end
        matches = 0
        for pa, pb in zip(reversed(parts_a), reversed(parts_b)):
            if pa == pb:
                matches += 1
            else:
                break

        if matches > 0:
            max_len = max(len(parts_a), len(parts_b))
            similarity = matches / max_len
            # Near-rhyme if similarity > 0.5
            return similarity > 0.7, similarity

        return False, 0.0

    def find_rhyming_candidates(
        self,
        target_rhyme: str,
        candidates: List[Dict[str, object]],
    ) -> List[str]:
        """Find candidates that rhyme with a target rhyme class.

        Args:
            target_rhyme: The rhyme class to match
            candidates: List of candidate chunks

        Returns:
            List of chunk_ids that rhyme with the target
        """
        rhyming = []

        for chunk in candidates:
            chunk_id = str(chunk.get("chunk_id", ""))
            chunk_rhyme = str(chunk.get("rhyme_class", ""))

            if not chunk_rhyme:
                last_token = str(chunk.get("last_token", ""))
                if last_token:
                    phonemes = get_phonemes(last_token)
                    if phonemes:
                        chunk_rhyme = compute_rhyme_class(phonemes[0])

            if chunk_rhyme == target_rhyme:
                rhyming.append(chunk_id)

        return rhyming
