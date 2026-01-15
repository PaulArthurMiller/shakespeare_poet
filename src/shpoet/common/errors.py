"""Domain-specific error types for the Shakespearean Poet pipeline."""


class ShakespearePoetError(Exception):
    """Base exception for domain errors."""


class PlanInvalidError(ShakespearePoetError):
    """Raised when a play plan fails validation."""


class ConstraintViolationError(ShakespearePoetError):
    """Raised when a candidate violates a hard constraint."""


class DeadEndError(ShakespearePoetError):
    """Raised when search exhausts all valid candidates."""
