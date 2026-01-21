"""Fragment chunking using NLP for semantic groupings.

Fragments are 3-8 word semantic units extracted using dependency parsing
and syntactic analysis. Unlike phrase chunking (punctuation-based), fragment
chunking identifies grammatically coherent units that can serve as puzzle
pieces for play construction.

Semantic units identified:
- Noun phrases with modifiers ("the guilty creatures")
- Verb phrases with objects ("murder will speak")
- Prepositional phrases ("of most miraculous organ")
- Clause fragments ("that I have seen")

Each fragment maintains full provenance for quote tracking and validation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from shpoet.chunking.provenance import build_phrase_provenance
from shpoet.ingest.canon_index import CanonicalLine

logger = logging.getLogger(__name__)

# Lazy-loaded spaCy model
_nlp = None

# Fragment size constraints
MIN_FRAGMENT_WORDS = 3
MAX_FRAGMENT_WORDS = 8

# Dependency labels that typically start a new syntactic unit
# These mark boundaries where we might want to split
CLAUSE_BOUNDARY_DEPS = frozenset([
    'ccomp',    # clausal complement ("I think [that] he left")
    'advcl',    # adverbial clause ("he left [when] I arrived")
    'relcl',    # relative clause ("the man [who] left")
    'acl',      # adjectival clause
    'conj',     # conjunction (can mark coordinate clauses)
])

# Dependencies that should stay attached to their head
ATTACHED_DEPS = frozenset([
    'det',      # determiner (the, a, this)
    'poss',     # possessive (my, thy, his)
    'amod',     # adjectival modifier
    'advmod',   # adverbial modifier
    'compound', # compound words
    'neg',      # negation
    'aux',      # auxiliary verb
    'auxpass',  # passive auxiliary
    'mark',     # marker (that, if, when)
    'case',     # case marking (of, in, to)
    'cc',       # coordinating conjunction
])


def _get_nlp():
    """Lazy-load the spaCy English model."""
    global _nlp
    if _nlp is None:
        try:
            import spacy
            # Try to load the small English model
            # Fall back to medium if small isn't available
            try:
                _nlp = spacy.load("en_core_web_sm")
            except OSError:
                logger.warning(
                    "spaCy model 'en_core_web_sm' not found. "
                    "Install with: python -m spacy download en_core_web_sm"
                )
                raise
        except ImportError:
            logger.error("spaCy not installed. Install with: pip install spacy")
            raise
    return _nlp


@dataclass
class FragmentSpan:
    """Represents a semantic fragment within a line with word boundaries."""

    text: str
    tokens: List[str]
    start_idx: int  # inclusive, 0-based word index
    end_idx: int    # inclusive, 0-based word index
    syntactic_type: str = ""  # e.g., "noun_phrase", "verb_phrase", "clause"

    @property
    def word_count(self) -> int:
        """Return the number of words in this fragment."""
        return len(self.tokens)

    def merge_with(self, other: 'FragmentSpan') -> 'FragmentSpan':
        """Merge this fragment with an adjacent one."""
        if other.start_idx != self.end_idx + 1:
            raise ValueError("Can only merge adjacent fragments")

        merged_tokens = self.tokens + other.tokens
        return FragmentSpan(
            text=' '.join(merged_tokens),
            tokens=merged_tokens,
            start_idx=self.start_idx,
            end_idx=other.end_idx,
            syntactic_type="merged",
        )


@dataclass
class _SpanCandidate:
    """Internal candidate for a syntactic span during extraction."""
    start: int
    end: int  # inclusive
    dep_type: str
    score: float = 0.0  # for ranking overlapping candidates


def _align_spacy_to_tokens(
    doc,
    original_tokens: List[str],
) -> Dict[int, int]:
    """Align spaCy token indices to original token indices.

    SpaCy may tokenize differently than our simple word tokenizer.
    This creates a mapping from spaCy token index to original token index.

    Returns:
        Dict mapping spaCy token index to original token index, or -1 if no match
    """
    alignment = {}
    orig_idx = 0
    orig_lower = [t.lower() for t in original_tokens]

    for spacy_idx, token in enumerate(doc):
        token_text = token.text.lower().strip("'\".,;:!?()-")

        # Try to find matching original token
        best_match = -1
        for i in range(orig_idx, min(orig_idx + 3, len(orig_lower))):
            orig_text = orig_lower[i].strip("'\".,;:!?()-")
            if token_text == orig_text or token_text in orig_text or orig_text in token_text:
                best_match = i
                orig_idx = i + 1
                break

        alignment[spacy_idx] = best_match

    return alignment


def _extract_syntactic_spans(
    doc,
    alignment: Dict[int, int],
    total_tokens: int,
) -> List[_SpanCandidate]:
    """Extract syntactic span candidates from spaCy parse.

    Identifies noun phrases, verb phrases, and other constituents
    that form natural semantic units.
    """
    candidates = []

    # Extract noun chunks (spaCy's built-in noun phrase detection)
    for chunk in doc.noun_chunks:
        start_orig = alignment.get(chunk.start, -1)
        end_orig = alignment.get(chunk.end - 1, -1)

        if start_orig >= 0 and end_orig >= 0 and end_orig >= start_orig:
            candidates.append(_SpanCandidate(
                start=start_orig,
                end=end_orig,
                dep_type="noun_phrase",
                score=2.0,  # Noun phrases are high-value semantic units
            ))

    # Extract verb phrases (verb + direct objects + complements)
    for token in doc:
        if token.pos_ == "VERB":
            # Collect the verb and its dependents
            verb_start = alignment.get(token.i, -1)
            if verb_start < 0:
                continue

            # Get the subtree span
            subtree_indices = [alignment.get(t.i, -1) for t in token.subtree]
            valid_indices = [i for i in subtree_indices if i >= 0]

            if valid_indices:
                span_start = min(valid_indices)
                span_end = max(valid_indices)

                # Don't include subject in verb phrase (it's a separate unit)
                for child in token.children:
                    if child.dep_ in ('nsubj', 'nsubjpass'):
                        subj_indices = [alignment.get(t.i, -1) for t in child.subtree]
                        valid_subj = [i for i in subj_indices if i >= 0]
                        if valid_subj:
                            # Adjust span to exclude subject
                            subj_end = max(valid_subj)
                            if span_start <= subj_end < span_end:
                                span_start = subj_end + 1

                if span_start <= span_end and span_start >= 0:
                    candidates.append(_SpanCandidate(
                        start=span_start,
                        end=span_end,
                        dep_type="verb_phrase",
                        score=1.5,
                    ))

    # Extract prepositional phrases
    for token in doc:
        if token.dep_ == "prep" or token.pos_ == "ADP":
            prep_start = alignment.get(token.i, -1)
            if prep_start < 0:
                continue

            # Get prepositional phrase subtree
            subtree_indices = [alignment.get(t.i, -1) for t in token.subtree]
            valid_indices = [i for i in subtree_indices if i >= 0]

            if valid_indices:
                candidates.append(_SpanCandidate(
                    start=min(valid_indices),
                    end=max(valid_indices),
                    dep_type="prep_phrase",
                    score=1.0,
                ))

    # Extract subordinate clauses
    for token in doc:
        if token.dep_ in CLAUSE_BOUNDARY_DEPS:
            clause_start = alignment.get(token.i, -1)
            if clause_start < 0:
                continue

            subtree_indices = [alignment.get(t.i, -1) for t in token.subtree]
            valid_indices = [i for i in subtree_indices if i >= 0]

            if valid_indices:
                candidates.append(_SpanCandidate(
                    start=min(valid_indices),
                    end=max(valid_indices),
                    dep_type="clause",
                    score=1.2,
                ))

    return candidates


def _select_non_overlapping_spans(
    candidates: List[_SpanCandidate],
    total_tokens: int,
    min_words: int = MIN_FRAGMENT_WORDS,
    max_words: int = MAX_FRAGMENT_WORDS,
    prefer_multiple: bool = False,
) -> List[Tuple[int, int, str]]:
    """Select best non-overlapping spans that cover the line.

    When prefer_multiple is True, favors finding multiple smaller fragments
    over a single large one. This helps create more "puzzle pieces" for
    play construction.

    Strategy:
    1. Filter candidates to valid size range
    2. Prefer smaller spans when prefer_multiple is set
    3. Greedily select non-overlapping spans
    4. Fill gaps with remaining words
    """
    if total_tokens == 0:
        return []

    # Track which word positions are covered
    covered = [False] * total_tokens
    selected = []

    # Filter candidates to valid size range
    valid_candidates = []
    for c in candidates:
        span_len = c.end - c.start + 1
        if min_words <= span_len <= max_words:
            valid_candidates.append(c)

    if not valid_candidates:
        # No syntactic candidates - fill entire line as gap
        selected = _fill_gaps(selected, covered, total_tokens, min_words, max_words)
        return selected

    # Sort candidates: when prefer_multiple, favor smaller spans
    # Otherwise favor higher scores
    if prefer_multiple:
        # Prefer smaller spans, then by score
        # This encourages multiple pieces rather than one large piece
        valid_candidates.sort(key=lambda c: (c.end - c.start, -c.score, c.start))
    else:
        # Standard: prefer higher scores
        valid_candidates.sort(key=lambda c: (-c.score, c.start))

    # Greedily select non-overlapping spans
    for candidate in valid_candidates:
        span_len = candidate.end - candidate.start + 1

        # Skip spans that cover the entire line when we prefer multiple
        if prefer_multiple and candidate.start == 0 and candidate.end == total_tokens - 1:
            continue

        # Check if this span overlaps with already selected
        overlaps = any(covered[i] for i in range(candidate.start, candidate.end + 1))
        if not overlaps:
            selected.append((candidate.start, candidate.end, candidate.dep_type))
            for i in range(candidate.start, candidate.end + 1):
                covered[i] = True

    # Fill uncovered gaps
    selected = _fill_gaps(selected, covered, total_tokens, min_words, max_words)

    # Sort by start position
    selected.sort(key=lambda x: x[0])

    return selected


def _fill_gaps(
    selected: List[Tuple[int, int, str]],
    covered: List[bool],
    total_tokens: int,
    min_words: int,
    max_words: int,
) -> List[Tuple[int, int, str]]:
    """Fill gaps between selected spans with appropriately sized fragments."""

    # Find uncovered regions
    gaps = []
    gap_start = None

    for i in range(total_tokens):
        if not covered[i]:
            if gap_start is None:
                gap_start = i
        else:
            if gap_start is not None:
                gaps.append((gap_start, i - 1))
                gap_start = None

    if gap_start is not None:
        gaps.append((gap_start, total_tokens - 1))

    # Process each gap
    for gap_start, gap_end in gaps:
        gap_len = gap_end - gap_start + 1

        if gap_len <= 0:
            continue

        # If gap is within size limits, add as single fragment
        if min_words <= gap_len <= max_words:
            selected.append((gap_start, gap_end, "gap_fill"))
            for i in range(gap_start, gap_end + 1):
                covered[i] = True

        # If gap is too large, split into chunks
        elif gap_len > max_words:
            pos = gap_start
            while pos <= gap_end:
                remaining = gap_end - pos + 1
                # Try to make chunks of reasonable size
                chunk_size = min(max_words, remaining)
                if remaining - chunk_size < min_words and remaining <= max_words:
                    # Take all remaining to avoid tiny leftover
                    chunk_size = remaining

                chunk_end = pos + chunk_size - 1
                if chunk_size >= min_words:
                    selected.append((pos, chunk_end, "gap_fill"))
                    for i in range(pos, chunk_end + 1):
                        covered[i] = True
                pos = chunk_end + 1

        # If gap is too small, try to merge with adjacent spans
        elif gap_len < min_words:
            # Find adjacent selected spans
            left_span = None
            right_span = None

            for s_start, s_end, s_type in selected:
                if s_end == gap_start - 1:
                    left_span = (s_start, s_end, s_type)
                elif s_start == gap_end + 1:
                    right_span = (s_start, s_end, s_type)

            # Try to merge with whichever keeps us under max_words
            merged = False
            if left_span:
                new_len = (gap_end - left_span[0] + 1)
                if new_len <= max_words:
                    selected.remove(left_span)
                    selected.append((left_span[0], gap_end, "merged"))
                    for i in range(gap_start, gap_end + 1):
                        covered[i] = True
                    merged = True

            if not merged and right_span:
                new_len = (right_span[1] - gap_start + 1)
                if new_len <= max_words:
                    selected.remove(right_span)
                    selected.append((gap_start, right_span[1], "merged"))
                    for i in range(gap_start, gap_end + 1):
                        covered[i] = True
                    merged = True

            # If can't merge, leave the gap unfilled
            # These words are "lost" - acceptable for fragment chunking
            # which prioritizes semantic quality over complete coverage

    return selected


def _filter_valid_fragments(
    fragments: List[FragmentSpan],
    total_line_words: int,
) -> List[FragmentSpan]:
    """Filter to keep only valid semantic fragments.

    For fragment chunking, the goal is strong semantic units of 3-8 words.
    Unlike phrase chunking, we don't require complete line coverage.
    Lost words are acceptable if they don't form good fragments.

    Complete short lines (< 3 words) ARE valid as they represent
    full Shakespeare quotes.
    """
    if not fragments:
        return fragments

    # Single fragment spanning whole line is always valid
    # (this handles complete short lines)
    if len(fragments) == 1:
        frag = fragments[0]
        # Valid if: within size range OR is the complete line
        is_complete_line = (frag.start_idx == 0 and
                          frag.end_idx == total_line_words - 1)
        if MIN_FRAGMENT_WORDS <= frag.word_count <= MAX_FRAGMENT_WORDS:
            return fragments
        elif is_complete_line and frag.word_count < MIN_FRAGMENT_WORDS:
            # Complete short line - valid quote
            return fragments
        elif is_complete_line and frag.word_count > MAX_FRAGMENT_WORDS:
            # Will be split later
            return fragments
        else:
            return []

    # Filter to only valid-sized fragments
    # Undersized fragments that aren't complete lines are dropped
    valid = []
    for frag in fragments:
        is_complete_line = (frag.start_idx == 0 and
                          frag.end_idx == total_line_words - 1 and
                          len(fragments) == 1)

        if MIN_FRAGMENT_WORDS <= frag.word_count <= MAX_FRAGMENT_WORDS:
            valid.append(frag)
        # Note: undersized fragments are intentionally dropped
        # This is acceptable - we prioritize semantic quality over coverage

    return valid


def _split_oversized_fragments(
    fragments: List[FragmentSpan],
    doc,
    alignment: Dict[int, int],
    original_tokens: List[str],
) -> List[FragmentSpan]:
    """Split fragments that exceed maximum size at natural breakpoints."""
    result = []

    for frag in fragments:
        if frag.word_count <= MAX_FRAGMENT_WORDS:
            result.append(frag)
            continue

        # Find natural split points within this fragment
        # Look for clause boundaries, conjunctions, or punctuation-like breaks
        split_points = []

        # Check each position for potential split
        for pos in range(frag.start_idx + MIN_FRAGMENT_WORDS,
                         frag.end_idx - MIN_FRAGMENT_WORDS + 2):
            # Find corresponding spaCy token
            for spacy_idx, orig_idx in alignment.items():
                if orig_idx == pos and spacy_idx < len(doc):
                    token = doc[spacy_idx]
                    # Good split points: after conjunctions, before subordinators
                    if token.dep_ in ('cc', 'mark') or token.dep_ in CLAUSE_BOUNDARY_DEPS:
                        split_points.append(pos)
                    # Also consider splitting before prepositions if needed
                    elif token.pos_ == 'ADP' and frag.word_count > MAX_FRAGMENT_WORDS + 2:
                        split_points.append(pos)
                    break

        if split_points:
            # Split at the best point (closest to middle)
            middle = frag.start_idx + frag.word_count // 2
            best_split = min(split_points, key=lambda p: abs(p - middle))

            # Create two fragments
            frag1_tokens = original_tokens[frag.start_idx:best_split]
            frag2_tokens = original_tokens[best_split:frag.end_idx + 1]

            if len(frag1_tokens) >= MIN_FRAGMENT_WORDS:
                result.append(FragmentSpan(
                    text=' '.join(frag1_tokens),
                    tokens=frag1_tokens,
                    start_idx=frag.start_idx,
                    end_idx=best_split - 1,
                    syntactic_type="split",
                ))
            if len(frag2_tokens) >= MIN_FRAGMENT_WORDS:
                result.append(FragmentSpan(
                    text=' '.join(frag2_tokens),
                    tokens=frag2_tokens,
                    start_idx=best_split,
                    end_idx=frag.end_idx,
                    syntactic_type="split",
                ))

            # Handle case where split created invalid fragments
            if len(frag1_tokens) < MIN_FRAGMENT_WORDS or len(frag2_tokens) < MIN_FRAGMENT_WORDS:
                # Fall back to even split
                result = [f for f in result if f.start_idx != frag.start_idx]
                mid = frag.start_idx + MAX_FRAGMENT_WORDS
                frag1_tokens = original_tokens[frag.start_idx:mid]
                frag2_tokens = original_tokens[mid:frag.end_idx + 1]
                result.append(FragmentSpan(
                    text=' '.join(frag1_tokens),
                    tokens=frag1_tokens,
                    start_idx=frag.start_idx,
                    end_idx=mid - 1,
                    syntactic_type="split",
                ))
                # Recursively handle remaining if still too large
                if len(frag2_tokens) > 0:
                    remaining = FragmentSpan(
                        text=' '.join(frag2_tokens),
                        tokens=frag2_tokens,
                        start_idx=mid,
                        end_idx=frag.end_idx,
                        syntactic_type="split",
                    )
                    result.extend(_split_oversized_fragments(
                        [remaining], doc, alignment, original_tokens
                    ))
        else:
            # No natural split points, do mechanical split
            pos = frag.start_idx
            while pos <= frag.end_idx:
                remaining = frag.end_idx - pos + 1
                chunk_size = min(MAX_FRAGMENT_WORDS, remaining)

                # Avoid tiny leftovers
                if remaining - chunk_size < MIN_FRAGMENT_WORDS and remaining <= MAX_FRAGMENT_WORDS:
                    chunk_size = remaining

                chunk_tokens = original_tokens[pos:pos + chunk_size]
                if len(chunk_tokens) >= MIN_FRAGMENT_WORDS or remaining == len(chunk_tokens):
                    result.append(FragmentSpan(
                        text=' '.join(chunk_tokens),
                        tokens=chunk_tokens,
                        start_idx=pos,
                        end_idx=pos + chunk_size - 1,
                        syntactic_type="mechanical_split",
                    ))
                pos += chunk_size

    return result


def extract_fragments_from_line(
    text: str,
    tokens: List[str],
) -> List[FragmentSpan]:
    """Extract semantic fragments from a single line using NLP.

    This function prioritizes creating smaller semantic puzzle pieces
    rather than keeping lines whole. It:
    1. Parses the line with spaCy to find syntactic constituents
    2. Prefers multiple smaller fragments over single large ones
    3. Only uses complete_line for very short lines (< 6 words)
    4. Enforces 3-8 word constraints

    Args:
        text: The raw text of the line
        tokens: List of word tokens from the line

    Returns:
        List of FragmentSpan objects representing semantic fragments
    """
    if not tokens:
        return []

    # Very short lines (< 6 words) can't be split into two valid fragments
    # so they become single fragments (complete short lines are valid quotes)
    if len(tokens) < MIN_FRAGMENT_WORDS * 2:
        return [FragmentSpan(
            text=' '.join(tokens),
            tokens=tokens,
            start_idx=0,
            end_idx=len(tokens) - 1,
            syntactic_type="complete_line",
        )]

    # Parse with spaCy - always try to find syntactic splits
    nlp = _get_nlp()
    doc = nlp(text)

    # Align spaCy tokens to our tokens
    alignment = _align_spacy_to_tokens(doc, tokens)

    # Extract syntactic span candidates
    candidates = _extract_syntactic_spans(doc, alignment, len(tokens))

    # For lines that could be a single fragment (6-8 words), prefer splitting
    # if we find good syntactic boundaries
    prefer_split = len(tokens) <= MAX_FRAGMENT_WORDS

    # Select non-overlapping spans, preferring smaller pieces
    selected_spans = _select_non_overlapping_spans(
        candidates, len(tokens), MIN_FRAGMENT_WORDS, MAX_FRAGMENT_WORDS,
        prefer_multiple=prefer_split
    )

    # Convert to FragmentSpan objects
    fragments = []
    for start, end, dep_type in selected_spans:
        frag_tokens = tokens[start:end + 1]
        fragments.append(FragmentSpan(
            text=' '.join(frag_tokens),
            tokens=frag_tokens,
            start_idx=start,
            end_idx=end,
            syntactic_type=dep_type,
        ))

    # Sort by position
    fragments.sort(key=lambda f: f.start_idx)

    # Split oversized fragments first
    fragments = _split_oversized_fragments(fragments, doc, alignment, tokens)

    # Filter to valid fragments only (3-8 words, or complete short lines)
    # Undersized fragments are dropped - we prioritize quality over coverage
    fragments = _filter_valid_fragments(fragments, len(tokens))

    # Final sort
    fragments.sort(key=lambda f: f.start_idx)

    return fragments


def build_fragment_chunks(
    lines: List[CanonicalLine],
    min_words: int = MIN_FRAGMENT_WORDS,
    max_words: int = MAX_FRAGMENT_WORDS,
) -> List[Dict[str, object]]:
    """Build fragment chunks from canonical line entries using NLP.

    Each fragment is a 3-8 word semantic unit extracted using dependency
    parsing. Fragments are non-overlapping and maintain full provenance
    for quote tracking and validation.

    Args:
        lines: List of CanonicalLine objects from the canonical index
        min_words: Minimum words per fragment (default 3)
        max_words: Maximum words per fragment (default 8)

    Returns:
        List of chunk dictionaries with text, tokens, and full provenance
    """
    chunks: List[Dict[str, object]] = []

    for line_idx, line in enumerate(lines):
        # Extract semantic fragments from this line
        fragments = extract_fragments_from_line(line.raw_text, line.tokens)

        for frag_idx, fragment in enumerate(fragments):
            # Generate stable chunk ID
            chunk_id = f"{line.line_id}_f{frag_idx}"

            # Build the chunk with full provenance
            chunk = {
                "chunk_id": chunk_id,
                "text": fragment.text,
                "tokens": fragment.tokens,
                "token_count": fragment.word_count,
                "syntactic_type": fragment.syntactic_type,
            }

            # Add provenance with word index range
            chunk.update(build_phrase_provenance(
                line=line,
                start_word_idx=fragment.start_idx,
                end_word_idx=fragment.end_idx,
            ))

            chunks.append(chunk)

            logger.debug(
                "Created fragment chunk %s [%s]: '%s' (words %d-%d)",
                chunk_id, fragment.syntactic_type,
                fragment.text, fragment.start_idx, fragment.end_idx
            )

        if (line_idx + 1) % 100 == 0:
            logger.info("Processed %d/%d lines", line_idx + 1, len(lines))

    logger.info(
        "Built %d fragment chunks from %d lines (avg %.2f fragments/line)",
        len(chunks), len(lines), len(chunks) / max(len(lines), 1)
    )

    return chunks


def get_available_fragments_for_line(
    line: CanonicalLine,
    used_word_indices: Optional[Set[int]] = None,
    min_words: int = MIN_FRAGMENT_WORDS,
    max_words: int = MAX_FRAGMENT_WORDS,
) -> List[FragmentSpan]:
    """Get fragments from a line that don't overlap with already-used words.

    Useful for the quote map system to find remaining usable fragments
    after some words have been consumed.

    Args:
        line: The canonical line to extract fragments from
        used_word_indices: Set of word indices already used from this line
        min_words: Minimum words per fragment
        max_words: Maximum words per fragment

    Returns:
        List of FragmentSpan objects for still-available fragments
    """
    if used_word_indices is None:
        used_word_indices = set()

    all_fragments = extract_fragments_from_line(line.raw_text, line.tokens)

    available = []
    for fragment in all_fragments:
        # Check if any word in this fragment has been used
        frag_indices = set(range(fragment.start_idx, fragment.end_idx + 1))
        if not frag_indices.intersection(used_word_indices):
            if min_words <= fragment.word_count <= max_words:
                available.append(fragment)

    return available
