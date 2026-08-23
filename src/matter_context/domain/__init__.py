"""Framework-independent matter domain."""

from .errors import DomainInvariantError, SourceMutationError, UnauthorizedReviewError
from .models import (
    ActorKind,
    CaseBriefVersion,
    Claim,
    ContentBlock,
    Matter,
    MatterStatus,
    NarrativeUpdateType,
    ProcessingRun,
    ProcessingStatus,
    Provenance,
    ReviewDecision,
    ReviewState,
    SourceKind,
    SourceRecord,
    SourceReference,
)

__all__ = [
    "ActorKind", "CaseBriefVersion", "Claim", "ContentBlock", "DomainInvariantError",
    "Matter", "MatterStatus", "NarrativeUpdateType", "ProcessingRun", "ProcessingStatus", "Provenance",
    "ReviewDecision", "ReviewState", "SourceKind", "SourceMutationError", "SourceRecord",
    "SourceReference", "UnauthorizedReviewError",
]
