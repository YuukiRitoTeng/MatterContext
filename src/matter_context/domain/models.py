"""Immutable domain records and review invariants for a legal matter."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import StrEnum

from .errors import DomainInvariantError, ProcessingRunTransitionError, UnauthorizedReviewError


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


class IngestionStatus(StrEnum):
    PROCESSING = "processing"
    READY = "ready"
    NEEDS_REVIEW = "needs_review"
    NEEDS_OCR = "needs_ocr"
    FAILED = "failed"


class ExtractionStatus(StrEnum):
    NOT_STARTED = "not_started"
    RUNNING = "running"
    EXTRACTED = "extracted"
    PARTIAL = "partial"
    NO_TEXT = "no_text"
    NEEDS_OCR = "needs_ocr"
    FAILED = "failed"


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
    ingestion_status: IngestionStatus | str = IngestionStatus.READY
    extraction_status: ExtractionStatus | str = ExtractionStatus.NOT_STARTED
    created_at: datetime = field(default_factory=utcnow)
    update_type: NarrativeUpdateType | None = None
    duplicate_of_id: str | None = None

    def __post_init__(self) -> None:
        if len(self.payload_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.payload_sha256):
            raise DomainInvariantError("Source payload_sha256 must be a lowercase SHA-256 digest")
        if self.text is None and self.attachment_path is None:
            raise DomainInvariantError("A source requires text or an attachment path")
        if self.text is not None and self.attachment_path is not None:
            raise DomainInvariantError("A source cannot store text and an attachment path together")

    @property
    def is_ready_for_downstream(self) -> bool:
        """Whether this source may be treated as complete input by a later workflow."""
        if str(self.ingestion_status) != IngestionStatus.READY:
            return False
        return self.kind is SourceKind.NARRATIVE_UPDATE or str(self.extraction_status) == ExtractionStatus.EXTRACTED


@dataclass(frozen=True, slots=True)
class ContentBlock:
    identifier: str
    source_id: str
    ordinal: int
    text: str
    locator: str | None = None
    created_at: datetime = field(default_factory=utcnow)
    page: int | None = None
    paragraph: int | None = None
    character_start: int | None = None
    character_end: int | None = None


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
    parser_name: str | None = None
    parser_version: str | None = None
    duration_ms: int | None = None

    def __post_init__(self) -> None:
        if self.status is ProcessingStatus.RUNNING:
            if self.completed_at is not None:
                raise DomainInvariantError("A running processing run cannot have a completion time")
            if self.error_summary is not None:
                raise DomainInvariantError("A running processing run cannot have a failure summary")
            return
        if self.completed_at is None:
            raise DomainInvariantError("A terminal processing run requires a completion time")
        if self.status is ProcessingStatus.FAILED and not (self.error_summary or "").strip():
            raise DomainInvariantError("A failed processing run requires a failure summary")
        if self.status is not ProcessingStatus.FAILED and self.error_summary is not None:
            raise DomainInvariantError("Only a failed processing run may have a failure summary")

    @classmethod
    def start(
        cls, identifier: str, matter_id: str, operation: str, input_source_ids: tuple[str, ...], *,
        provider: str | None = None, model: str | None = None, workflow_version: str | None = None,
        started_at: datetime | None = None, parser_name: str | None = None, parser_version: str | None = None,
    ) -> ProcessingRun:
        return cls(
            identifier, matter_id, operation, input_source_ids, ProcessingStatus.RUNNING,
            provider=provider, model=model, workflow_version=workflow_version, started_at=started_at or utcnow(),
            parser_name=parser_name, parser_version=parser_version,
        )

    def succeed(self, *, completed_at: datetime | None = None, duration_ms: int | None = None) -> ProcessingRun:
        return self._finish(ProcessingStatus.SUCCEEDED, completed_at=completed_at, duration_ms=duration_ms)

    def complete_partially(self, *, completed_at: datetime | None = None, duration_ms: int | None = None) -> ProcessingRun:
        return self._finish(ProcessingStatus.PARTIAL, completed_at=completed_at, duration_ms=duration_ms)

    def fail(self, error_summary: str, *, completed_at: datetime | None = None, duration_ms: int | None = None) -> ProcessingRun:
        return self._finish(
            ProcessingStatus.FAILED, completed_at=completed_at, error_summary=error_summary, duration_ms=duration_ms,
        )

    def _finish(
        self, status: ProcessingStatus, *, completed_at: datetime | None, duration_ms: int | None,
        error_summary: str | None = None,
    ) -> ProcessingRun:
        if self.status is not ProcessingStatus.RUNNING:
            raise ProcessingRunTransitionError("Only a running processing run can be completed")
        return replace(
            self, status=status, completed_at=completed_at or utcnow(), error_summary=error_summary,
            duration_ms=duration_ms,
        )


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
