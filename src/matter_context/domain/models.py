"""Immutable domain records and review invariants for a legal matter."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum

from .errors import DomainInvariantError, UnauthorizedReviewError


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MatterStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class SourceKind(StrEnum):
    NARRATIVE_UPDATE = "narrative_update"
    DOCUMENT = "document"


class NarrativeUpdateType(StrEnum):
    """The user-selected context for a pasted case update."""

    INITIAL_ACCOUNT = "initial_account"
    LATER_INFORMATION = "later_information"
    CORRECTION = "correction"
    ATTORNEY_NOTE = "attorney_note"


class Provenance(StrEnum):
    ORIGINAL_SOURCE = "original_source"
    ATTORNEY_PROVIDED = "attorney_provided"
    AI_ORGANIZED = "ai_organized"
    AI_INFERRED = "ai_inferred"


class ReviewState(StrEnum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    DISPUTED = "disputed"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class ActorKind(StrEnum):
    USER = "user"
    AI = "ai"
    SYSTEM = "system"


class ProcessingStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass(frozen=True, slots=True)
class Matter:
    identifier: str
    title: str
    reference: str | None = None
    description: str | None = None
    status: MatterStatus = MatterStatus.ACTIVE
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)


@dataclass(frozen=True, slots=True)
class SourceRecord:
    identifier: str
    matter_id: str
    kind: SourceKind
    provenance: Provenance
    payload_sha256: str
    text: str | None = None
    attachment_path: str | None = None
    original_filename: str | None = None
    media_type: str | None = None
    correction_of_id: str | None = None
    ingestion_status: str = "ready"
    extraction_status: str = "not_started"
    created_at: datetime = field(default_factory=utcnow)
    update_type: NarrativeUpdateType | None = None

    def __post_init__(self) -> None:
        if len(self.payload_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.payload_sha256):
            raise DomainInvariantError("Source payload_sha256 must be a lowercase SHA-256 digest")
        if self.text is None and self.attachment_path is None:
            raise DomainInvariantError("A source requires text or an attachment path")
        if self.text is not None and self.attachment_path is not None:
            raise DomainInvariantError("A source cannot store text and an attachment path together")


@dataclass(frozen=True, slots=True)
class ContentBlock:
    identifier: str
    source_id: str
    ordinal: int
    text: str
    locator: str | None = None
    created_at: datetime = field(default_factory=utcnow)


@dataclass(frozen=True, slots=True)
class Claim:
    identifier: str
    matter_id: str
    statement: str
    category: str
    provenance: Provenance
    revision_of_id: str | None = None
    created_at: datetime = field(default_factory=utcnow)


@dataclass(frozen=True, slots=True)
class SourceReference:
    identifier: str
    claim_id: str
    source_id: str | None = None
    content_block_id: str | None = None
    page: int | None = None
    paragraph: int | None = None
    character_start: int | None = None
    character_end: int | None = None
    excerpt: str | None = None

    def __post_init__(self) -> None:
        if self.character_start is not None and self.character_end is not None and self.character_end < self.character_start:
            raise DomainInvariantError("Source reference character range is invalid")


@dataclass(frozen=True, slots=True)
class ReviewDecision:
    identifier: str
    claim_id: str
    state: ReviewState
    actor_kind: ActorKind
    actor_id: str
    note: str | None = None
    created_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        if self.actor_kind is not ActorKind.USER and self.state is not ReviewState.PROPOSED:
            raise UnauthorizedReviewError("Only a user can confirm, dispute, reject, or supersede a claim")


@dataclass(frozen=True, slots=True)
class ProcessingRun:
    identifier: str
    matter_id: str
    operation: str
    input_source_ids: tuple[str, ...]
    status: ProcessingStatus
    provider: str | None = None
    model: str | None = None
    workflow_version: str | None = None
    started_at: datetime = field(default_factory=utcnow)
    completed_at: datetime | None = None
    error_summary: str | None = None


@dataclass(frozen=True, slots=True)
class CaseBriefVersion:
    identifier: str
    matter_id: str
    source_ids: tuple[str, ...]
    claim_ids: tuple[str, ...]
    review_decision_ids: tuple[str, ...]
    workflow_version: str
    structured_payload: str
    rendered_text: str
    created_at: datetime = field(default_factory=utcnow)
