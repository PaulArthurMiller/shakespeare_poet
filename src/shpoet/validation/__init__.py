"""Post-generation validation of finished play artifacts.

Distinct from ``micro/constraints``: constraints prune candidates *during*
search, while validation judges the artifact the search produced.  A validator
must be able to fail a play the search believed was legal, and must be runnable
against a play exported weeks ago, so it lives outside the search path.
"""

from shpoet.validation.quote_integrity import (
    IntegrityReport,
    IntegrityViolation,
    QuoteUsage,
    check_quote_integrity,
    check_used_chunks,
    usage_from_chunk,
)

__all__ = [
    "IntegrityReport",
    "IntegrityViolation",
    "QuoteUsage",
    "check_quote_integrity",
    "check_used_chunks",
    "usage_from_chunk",
]
