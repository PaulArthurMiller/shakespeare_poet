"""Feature extraction modules for corpus chunks.

Tier-1 (Raw): Basic text features - token counts, punctuation, etc.
Tier-2 (Derived): NLP features - phonetics, meter, syntax, semantics
Tier-3 (Lazy): On-demand expensive features with caching
"""

from shpoet.features.tier1_raw import apply_tier1_features, extract_tier1_features
from shpoet.features.tier2_derived import apply_tier2_features, extract_tier2_features
from shpoet.features.nlp_context import NLPContext
from shpoet.features.syllables import count_syllables, count_text_syllables
from shpoet.features.phonetics import get_phonemes, words_rhyme, words_alliterate
from shpoet.features.meter import analyze_meter, MeterAnalysis
from shpoet.features.syntax import extract_syntax_features
from shpoet.features.semantics import extract_semantic_features

__all__ = [
    # Tier-1
    "apply_tier1_features",
    "extract_tier1_features",
    # Tier-2
    "apply_tier2_features",
    "extract_tier2_features",
    # NLP Context
    "NLPContext",
    # Syllables
    "count_syllables",
    "count_text_syllables",
    # Phonetics
    "get_phonemes",
    "words_rhyme",
    "words_alliterate",
    # Meter
    "analyze_meter",
    "MeterAnalysis",
    # Syntax
    "extract_syntax_features",
    # Semantics
    "extract_semantic_features",
]
