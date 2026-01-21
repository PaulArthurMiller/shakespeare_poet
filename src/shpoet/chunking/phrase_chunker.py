"""Phrase chunking implementation for semantic quote extraction.

Phrases are extracted from Shakespeare lines based on punctuation boundaries,
with intelligent merging to ensure each phrase carries meaning independently.
Each phrase is at least 3 words and maintains exact provenance for quote
tracking and validation.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from shpoet.chunking.provenance import build_phrase_provenance
from shpoet.ingest.canon_index import CanonicalLine


logger = logging.getLogger(__name__)


# Punctuation that typically marks phrase boundaries in Shakespeare
# Ordered by boundary strength (stronger boundaries first)
PHRASE_BOUNDARY_CHARS = frozenset(['.', '!', '?', ';', ':', ',', '—', '-', '(', ')'])

# Words that should not start a phrase (weak openers)
# These are better attached to the preceding phrase
WEAK_STARTERS = frozenset([
    'and', 'or', 'but', 'for', 'nor', 'yet', 'so',  # conjunctions
    'that', 'which', 'who', 'whom', 'whose',  # relative pronouns
    'if', 'when', 'where', 'while', 'though', 'although',  # subordinating
])

# Words that should not end a phrase (weak closers)
# These are better attached to the following phrase
WEAK_CLOSERS = frozenset([
    'the', 'a', 'an',  # articles
    'my', 'thy', 'his', 'her', 'its', 'our', 'your', 'their',  # possessives
    'this', 'that', 'these', 'those',  # demonstratives
    'to', 'of', 'in', 'on', 'at', 'by', 'with', 'from', 'for',  # prepositions
    'is', 'are', 'was', 'were', 'be', 'been', 'being',  # be verbs
    'have', 'has', 'had', 'do', 'does', 'did',  # auxiliaries
    'shall', 'will', 'would', 'should', 'could', 'may', 'might', 'must',  # modals
    'not', 'no',  # negation
    'i', 'thou', 'he', 'she', 'it', 'we', 'you', 'they',  # pronouns
])

# Minimum words per phrase for meaningful quotes
MIN_PHRASE_WORDS = 3


@dataclass
class PhraseSpan:
    """Represents a phrase within a line with its word boundaries."""

    text: str
    tokens: List[str]
    start_idx: int  # inclusive
    end_idx: int    # inclusive

    @property
    def word_count(self) -> int:
        """Return the number of words in this phrase."""
        return len(self.tokens)

    def merge_with(self, other: 'PhraseSpan') -> 'PhraseSpan':
        """Merge this phrase with another (assumes other comes after self)."""
        if other.start_idx != self.end_idx + 1:
            raise ValueError("Can only merge adjacent phrases")

        # Reconstruct text by joining tokens with space
        # This normalizes whitespace but preserves word order
        merged_tokens = self.tokens + other.tokens
        merged_text = ' '.join(merged_tokens)

        return PhraseSpan(
            text=merged_text,
            tokens=merged_tokens,
            start_idx=self.start_idx,
            end_idx=other.end_idx,
        )


def _find_punctuation_boundaries(text: str, tokens: List[str]) -> List[int]:
    """Find word indices where punctuation suggests a phrase boundary.

    Returns a list of indices indicating the last word before each boundary.
    For example, in "To be, or not to be" with tokens ['To', 'be', 'or', 'not', 'to', 'be'],
    the comma after 'be' suggests a boundary after index 1.

    Args:
        text: The raw text of the line
        tokens: List of word tokens extracted from the line

    Returns:
        List of word indices (0-based) where boundaries occur after that word
    """
    boundaries = []

    if not tokens:
        return boundaries

    # Build a mapping of each token's approximate position in text
    # We'll find punctuation between token positions
    token_positions = []
    search_start = 0

    for token in tokens:
        pos = text.lower().find(token.lower(), search_start)
        if pos == -1:
            # Fallback: just use search_start
            pos = search_start
        token_positions.append((pos, pos + len(token)))
        search_start = pos + len(token)

    # Look for boundary punctuation between consecutive tokens
    for i in range(len(tokens) - 1):
        _, end_pos = token_positions[i]
        next_start, _ = token_positions[i + 1]

        # Check text between this token and next for boundary punctuation
        between = text[end_pos:next_start] if end_pos < next_start else ''

        if any(char in PHRASE_BOUNDARY_CHARS for char in between):
            boundaries.append(i)

    return boundaries


def _split_at_boundaries(tokens: List[str], boundaries: List[int]) -> List[Tuple[int, int]]:
    """Split token range into spans based on boundary indices.

    Args:
        tokens: List of word tokens
        boundaries: List of indices where boundaries occur (after that word)

    Returns:
        List of (start_idx, end_idx) tuples, both inclusive
    """
    if not tokens:
        return []

    if not boundaries:
        return [(0, len(tokens) - 1)]

    spans = []
    start = 0

    for boundary_idx in sorted(set(boundaries)):
        if boundary_idx >= start:
            spans.append((start, boundary_idx))
            start = boundary_idx + 1

    # Don't forget the final span after the last boundary
    if start < len(tokens):
        spans.append((start, len(tokens) - 1))

    return spans


def _is_weak_boundary(tokens: List[str], boundary_idx: int) -> bool:
    """Check if a boundary creates weak phrase starts/ends.

    A boundary is weak if:
    - The word after the boundary is a weak starter
    - The word at the boundary is a weak closer

    Args:
        tokens: List of word tokens
        boundary_idx: Index of the last word before the boundary

    Returns:
        True if this boundary should be avoided
    """
    # Check if word at boundary is a weak closer
    if tokens[boundary_idx].lower() in WEAK_CLOSERS:
        return True

    # Check if next word is a weak starter
    next_idx = boundary_idx + 1
    if next_idx < len(tokens) and tokens[next_idx].lower() in WEAK_STARTERS:
        return True

    return False


def _merge_short_phrases(
    phrases: List[PhraseSpan],
    total_line_words: int,
) -> List[PhraseSpan]:
    """Merge phrases that are too short to stand alone.

    IMPORTANT: The 3-word minimum only applies to FRAGMENTS of longer lines.
    Complete Shakespeare lines are always valid quotes regardless of length.
    A 1-word line like "Barnardo?" or 2-word line like "O speak!" is a valid
    quote because it's the complete original line.

    Strategy:
    1. If there's only one phrase spanning the whole line, keep it as-is
    2. For multi-phrase lines, merge short fragments (< 3 words) with neighbors
    3. Repeat until all fragments meet minimum length or can't be merged

    Args:
        phrases: List of PhraseSpan objects
        total_line_words: Total word count of the source line

    Returns:
        List of PhraseSpan objects where fragments have at least MIN_PHRASE_WORDS
        (complete short lines are preserved regardless of length)
    """
    if not phrases:
        return phrases

    # If there's only one phrase, it spans the complete line - always valid
    if len(phrases) == 1:
        return phrases  # Complete line, valid regardless of word count

    # If the total line is short (< MIN_PHRASE_WORDS), it shouldn't have been
    # split in the first place, but if it was, merge everything back
    if total_line_words < MIN_PHRASE_WORDS:
        if len(phrases) > 1:
            merged = phrases[0]
            for p in phrases[1:]:
                merged = merged.merge_with(p)
            return [merged]
        return phrases

    result = list(phrases)
    changed = True

    while changed and len(result) > 1:
        changed = False
        new_result = []
        i = 0

        while i < len(result):
            current = result[i]

            if current.word_count < MIN_PHRASE_WORDS:
                # Try to merge with next phrase first
                if i + 1 < len(result):
                    merged = current.merge_with(result[i + 1])
                    new_result.append(merged)
                    i += 2  # Skip the merged phrase
                    changed = True
                    continue
                # Try to merge with previous phrase
                elif new_result:
                    prev = new_result.pop()
                    merged = prev.merge_with(current)
                    new_result.append(merged)
                    i += 1
                    changed = True
                    continue

            new_result.append(current)
            i += 1

        result = new_result

    return result


def _extract_phrase_spans(text: str, tokens: List[str]) -> List[PhraseSpan]:
    """Extract phrase spans from a line using punctuation and semantic rules.

    This function:
    1. Finds punctuation-based boundaries
    2. Filters out weak boundaries that would create poor phrases
    3. Splits into initial phrases
    4. Merges short phrases to meet minimum word count

    Args:
        text: The raw text of the line
        tokens: List of word tokens extracted from the line

    Returns:
        List of PhraseSpan objects representing semantic phrases
    """
    if not tokens:
        return []

    # Find all punctuation boundaries
    all_boundaries = _find_punctuation_boundaries(text, tokens)

    # Filter out weak boundaries (but keep strong ones like periods)
    strong_boundaries = []
    for boundary_idx in all_boundaries:
        # Check if this is a strong boundary (sentence-ending punctuation)
        # by looking at the text after the token
        is_strong = False

        # Always keep sentence-ending punctuation as boundaries
        token = tokens[boundary_idx]
        # Find where this token ends in text and check following punctuation
        pos = text.lower().find(token.lower())
        if pos != -1:
            after_token = text[pos + len(token):pos + len(token) + 3]
            if any(c in '.!?;' for c in after_token):
                is_strong = True

        # Keep boundary if strong or not weak
        if is_strong or not _is_weak_boundary(tokens, boundary_idx):
            strong_boundaries.append(boundary_idx)

    # Split into spans
    spans = _split_at_boundaries(tokens, strong_boundaries)

    # Convert to PhraseSpan objects
    phrases = []
    for start_idx, end_idx in spans:
        phrase_tokens = tokens[start_idx:end_idx + 1]
        phrase_text = ' '.join(phrase_tokens)
        phrases.append(PhraseSpan(
            text=phrase_text,
            tokens=phrase_tokens,
            start_idx=start_idx,
            end_idx=end_idx,
        ))

    # Merge short fragments (but preserve complete short lines)
    phrases = _merge_short_phrases(phrases, total_line_words=len(tokens))

    return phrases


def build_phrase_chunks(
    lines: List[CanonicalLine],
    min_words: int = MIN_PHRASE_WORDS,
) -> List[Dict[str, object]]:
    """Build phrase chunks from canonical line entries.

    Each phrase is extracted based on punctuation boundaries and semantic
    rules, ensuring each chunk is meaningful when used independently.
    Phrases maintain exact provenance (play, act, scene, line, word indices)
    for quote tracking and validation.

    Args:
        lines: List of CanonicalLine objects from the canonical index
        min_words: Minimum words per phrase (default 3)

    Returns:
        List of chunk dictionaries with text, tokens, and full provenance
    """
    chunks: List[Dict[str, object]] = []

    for line in lines:
        # Extract semantic phrases from this line
        phrases = _extract_phrase_spans(line.raw_text, line.tokens)

        for phrase_idx, phrase in enumerate(phrases):
            # Generate stable chunk ID
            chunk_id = f"{line.line_id}_p{phrase_idx}"

            # Build the chunk with full provenance
            chunk = {
                "chunk_id": chunk_id,
                "text": phrase.text,
                "tokens": phrase.tokens,
                "token_count": phrase.word_count,
            }

            # Add provenance with word index range
            chunk.update(build_phrase_provenance(
                line=line,
                start_word_idx=phrase.start_idx,
                end_word_idx=phrase.end_idx,
            ))

            chunks.append(chunk)

            logger.debug(
                "Created phrase chunk %s: '%s' (words %d-%d)",
                chunk_id, phrase.text, phrase.start_idx, phrase.end_idx
            )

    logger.info(
        "Built %d phrase chunks from %d lines (avg %.1f phrases/line)",
        len(chunks), len(lines), len(chunks) / max(len(lines), 1)
    )

    return chunks


def get_available_phrases_for_line(
    line: CanonicalLine,
    used_word_indices: Optional[set] = None,
    min_words: int = MIN_PHRASE_WORDS,
) -> List[PhraseSpan]:
    """Get phrases from a line that don't overlap with already-used words.

    This is useful for the quote map system to find remaining usable
    phrases after some words have been used.

    Args:
        line: The canonical line to extract phrases from
        used_word_indices: Set of word indices already used from this line
        min_words: Minimum words per phrase

    Returns:
        List of PhraseSpan objects for still-available phrases
    """
    if used_word_indices is None:
        used_word_indices = set()

    all_phrases = _extract_phrase_spans(line.raw_text, line.tokens)

    available = []
    for phrase in all_phrases:
        # Check if any word in this phrase has been used
        phrase_indices = set(range(phrase.start_idx, phrase.end_idx + 1))
        if not phrase_indices.intersection(used_word_indices):
            if phrase.word_count >= min_words:
                available.append(phrase)

    return available
