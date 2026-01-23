"""Shared NLP context for spaCy document management.

Provides lazy-loaded singleton spaCy model and document caching
for efficient batch processing across feature extraction modules.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Module-level singleton
_nlp: Any = None
_doc_cache: Dict[str, Any] = {}
_cache_max_size = 1000


class NLPContext:
    """Shared NLP processing context with caching."""

    @classmethod
    def get_nlp(cls) -> Any:
        """Lazy-load the spaCy English model (singleton).

        Returns:
            spacy.Language: The loaded spaCy model
        """
        global _nlp
        if _nlp is None:
            try:
                import spacy
                try:
                    _nlp = spacy.load("en_core_web_sm")
                    logger.info("Loaded spaCy model 'en_core_web_sm'")
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

    @classmethod
    def get_doc(cls, text: str, cache_key: Optional[str] = None) -> Any:
        """Get a spaCy Doc for the given text with optional caching.

        Args:
            text: The text to parse
            cache_key: Optional key for caching (if None, uses text as key)

        Returns:
            spacy.Doc: The parsed document
        """
        global _doc_cache

        key = cache_key if cache_key is not None else text

        if key in _doc_cache:
            return _doc_cache[key]

        nlp = cls.get_nlp()
        doc = nlp(text)

        # LRU-style eviction when cache is full
        if len(_doc_cache) >= _cache_max_size:
            # Remove oldest entries (first 10%)
            evict_count = max(1, _cache_max_size // 10)
            keys_to_remove = list(_doc_cache.keys())[:evict_count]
            for k in keys_to_remove:
                del _doc_cache[k]

        _doc_cache[key] = doc
        return doc

    @classmethod
    def batch_process(cls, texts: List[str]) -> List[Any]:
        """Efficient batch processing via nlp.pipe().

        Args:
            texts: List of texts to process

        Returns:
            List[spacy.Doc]: List of parsed documents
        """
        nlp = cls.get_nlp()
        return list(nlp.pipe(texts))

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the document cache."""
        global _doc_cache
        _doc_cache.clear()
        logger.debug("Cleared NLP document cache")

    @classmethod
    def cache_size(cls) -> int:
        """Return current cache size."""
        return len(_doc_cache)
