"""Syntactic feature extraction using spaCy.

Provides POS tags, grammatical roles, clause types, and syntax-based
adjacency checking for chunk concatenation.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from shpoet.features.nlp_context import NLPContext

logger = logging.getLogger(__name__)

# POS tags that typically end complete phrases
PHRASE_ENDING_POS = frozenset(["NOUN", "VERB", "ADJ", "ADV", "PROPN", "NUM"])

# POS tags that typically need continuation
CONTINUATION_POS = frozenset(["DET", "ADP", "CCONJ", "SCONJ", "PART"])

# Dependencies that indicate grammatical roles
SUBJECT_DEPS = frozenset(["nsubj", "nsubjpass", "csubj", "csubjpass"])
OBJECT_DEPS = frozenset(["dobj", "iobj", "pobj", "obj"])
VERB_DEPS = frozenset(["ROOT", "ccomp", "xcomp", "advcl", "relcl"])


def _get_pos_tags(doc: Any) -> List[str]:
    """Extract POS tags from spaCy doc."""
    return [token.pos_ for token in doc]


def _get_grammatical_role(doc: Any) -> str:
    """Determine the primary grammatical role of the chunk.

    Returns one of: 'subject', 'predicate', 'object', 'modifier', 'clause', 'fragment'
    """
    deps = [token.dep_ for token in doc]

    # Check for subject
    if any(d in SUBJECT_DEPS for d in deps):
        # Check if there's also a verb (complete clause)
        if any(token.pos_ == "VERB" for token in doc):
            return "clause"
        return "subject"

    # Check for verb (predicate)
    if any(token.pos_ == "VERB" and token.dep_ != "aux" for token in doc):
        # Check if it has an object
        if any(d in OBJECT_DEPS for d in deps):
            return "predicate"
        return "predicate"

    # Check for object
    if any(d in OBJECT_DEPS for d in deps):
        return "object"

    # Check for prepositional phrase (modifier)
    if any(token.dep_ == "prep" or token.pos_ == "ADP" for token in doc):
        return "modifier"

    # Check for noun phrase
    if any(token.pos_ in ("NOUN", "PROPN") for token in doc):
        return "noun_phrase"

    return "fragment"


def _get_clause_type(doc: Any) -> str:
    """Determine the clause type if this is a clause.

    Returns: 'main', 'subordinate', 'relative', 'conditional', or 'none'
    """
    deps = [token.dep_ for token in doc]

    # Check for subordinating markers
    subordinators = {"if", "when", "while", "because", "although", "though", "unless", "since", "after", "before", "until"}
    text_lower = doc.text.lower()

    for sub in subordinators:
        if text_lower.startswith(sub + " ") or f" {sub} " in text_lower:
            if sub == "if":
                return "conditional"
            return "subordinate"

    # Check for relative pronouns
    relative_markers = {"who", "whom", "whose", "which", "that", "where", "when"}
    for token in doc:
        if token.text.lower() in relative_markers and token.dep_ in ("nsubj", "dobj", "pobj"):
            return "relative"

    # Check for relative clause dependency
    if any(d == "relcl" for d in deps):
        return "relative"

    # Check for adverbial clause
    if any(d == "advcl" for d in deps):
        return "subordinate"

    # Check if it has a main verb (could be main clause)
    if any(token.dep_ == "ROOT" and token.pos_ == "VERB" for token in doc):
        return "main"

    return "none"


def extract_syntax_features(text: str, tokens: Optional[List[str]] = None) -> Dict[str, Any]:
    """Extract syntactic features for a text chunk.

    Args:
        text: The text to analyze
        tokens: Optional pre-tokenized list (used for token alignment)

    Returns:
        Dict with keys:
        - pos_tags: JSON list of POS tags
        - pos_first: POS of first token
        - pos_last: POS of last token
        - grammatical_role: Primary grammatical role
        - has_verb: Whether chunk contains a verb
        - has_noun: Whether chunk contains a noun
        - clause_type: Type of clause (if applicable)
    """
    if not text or not text.strip():
        return {
            "pos_tags": "[]",
            "pos_first": "",
            "pos_last": "",
            "grammatical_role": "empty",
            "has_verb": False,
            "has_noun": False,
            "clause_type": "none",
        }

    doc = NLPContext.get_doc(text)

    pos_tags = _get_pos_tags(doc)
    pos_first = pos_tags[0] if pos_tags else ""
    pos_last = pos_tags[-1] if pos_tags else ""

    has_verb = any(token.pos_ == "VERB" for token in doc)
    has_noun = any(token.pos_ in ("NOUN", "PROPN") for token in doc)

    grammatical_role = _get_grammatical_role(doc)
    clause_type = _get_clause_type(doc)

    return {
        "pos_tags": json.dumps(pos_tags),
        "pos_first": pos_first,
        "pos_last": pos_last,
        "grammatical_role": grammatical_role,
        "has_verb": has_verb,
        "has_noun": has_noun,
        "clause_type": clause_type,
    }


def check_syntax_adjacency(
    prev_chunk: Dict[str, Any],
    curr_chunk: Dict[str, Any],
) -> Tuple[bool, str]:
    """Check if two chunks can be syntactically adjacent.

    Uses POS tags and grammatical roles to determine if concatenation
    produces grammatically sensible text.

    Args:
        prev_chunk: Feature dict of previous chunk
        curr_chunk: Feature dict of current chunk

    Returns:
        Tuple of (acceptable, reason) where reason explains rejection
    """
    prev_last = prev_chunk.get("pos_last", "")
    curr_first = curr_chunk.get("pos_first", "")

    # Rule 1: Don't end with determiner/preposition unless next is noun/verb
    if prev_last in ("DET", "ADP"):
        if curr_first not in ("NOUN", "PROPN", "ADJ", "NUM", "VERB", "ADV"):
            return False, "dangling_determiner"

    # Rule 2: Don't start with punctuation-like words after non-clause
    if curr_first == "PUNCT":
        return False, "orphan_punctuation"

    # Rule 3: Coordinating conjunctions need valid continuation
    if prev_last == "CCONJ":
        # Conjunction should be followed by similar structure
        prev_role = prev_chunk.get("grammatical_role", "")
        curr_role = curr_chunk.get("grammatical_role", "")
        # Allow conjunction + most structures
        if curr_role == "empty":
            return False, "dangling_conjunction"

    # Rule 4: Relative pronouns need to start clauses
    prev_role = prev_chunk.get("grammatical_role", "")
    curr_role = curr_chunk.get("grammatical_role", "")

    # Rule 5: Check for verb agreement
    # (Simplified: ensure we don't have verb-verb without connector)
    prev_verb = prev_chunk.get("has_verb", False)
    curr_verb = curr_chunk.get("has_verb", False)

    if prev_verb and curr_verb:
        # Both have verbs - check if there's a connector
        if prev_last not in ("CCONJ", "SCONJ", "PUNCT") and curr_first not in ("CCONJ", "SCONJ"):
            # Two verbs without connector is suspicious but not always wrong
            # (e.g., "I came, I saw, I conquered")
            pass  # Allow but could flag

    # Default: accept
    return True, "ok"


def get_compatible_roles(role: str) -> List[str]:
    """Get grammatical roles that can follow a given role.

    Args:
        role: The preceding grammatical role

    Returns:
        List of compatible following roles
    """
    compatibility = {
        "subject": ["predicate", "modifier", "clause"],
        "predicate": ["object", "modifier", "clause", "noun_phrase"],
        "object": ["modifier", "clause", "predicate"],
        "modifier": ["subject", "predicate", "object", "noun_phrase", "modifier", "clause"],
        "noun_phrase": ["predicate", "modifier", "clause"],
        "clause": ["clause", "modifier", "predicate"],
        "fragment": ["subject", "predicate", "object", "modifier", "noun_phrase", "clause", "fragment"],
        "empty": [],
    }
    return compatibility.get(role, ["fragment"])
