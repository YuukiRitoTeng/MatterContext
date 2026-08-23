"""Domain invariant failures."""


class DomainInvariantError(ValueError):
    """Raised when domain data would violate a durable business rule."""


class SourceMutationError(DomainInvariantError):
    """Raised when an immutable source is changed rather than appended."""


class UnauthorizedReviewError(DomainInvariantError):
    """Raised when a non-user attempts a user-only review state."""
