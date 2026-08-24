"""Domain invariant failures."""


class DomainInvariantError(ValueError):
    """Raised when domain data would violate a durable business rule."""


class SourceMutationError(DomainInvariantError):
    """Raised when an immutable source is changed rather than appended."""


class ProcessingRunTransitionError(DomainInvariantError):
    """Raised when a durable processing run cannot make its declared transition."""


class UnauthorizedReviewError(DomainInvariantError):
    """Raised when a non-user attempts a user-only review state."""
