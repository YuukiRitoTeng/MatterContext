"""SQLAlchemy repositories translating rows at the storage boundary."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from matter_context.domain import (
    ActorKind, CaseBriefVersion, Claim, ContentBlock, Matter, MatterStatus, NarrativeUpdateType, ProcessingRun,
    ProcessingStatus, Provenance, ReviewDecision, ReviewState, SourceKind, SourceRecord,
    SourceReference,
)

from .models import (
    CaseBriefVersionRow, ClaimRow, ContentBlockRow, MatterRow, ProcessingRunRow,
    ReviewDecisionRow, SourceReferenceRow, SourceRow,
)


def _matter(row: MatterRow) -> Matter:
    return Matter(row.identifier, row.title, row.reference, row.description, MatterStatus(row.status), _utc(row.created_at), _utc(row.updated_at))


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _source(row: SourceRow) -> SourceRecord:
    return SourceRecord(row.identifier, row.matter_id, SourceKind(row.kind), Provenance(row.provenance), row.payload_sha256,
                        row.text, row.attachment_path, row.original_filename, row.media_type, row.correction_of_id,
                        row.ingestion_status, row.extraction_status, _utc(row.created_at),
                        NarrativeUpdateType(row.update_type) if row.update_type else None)


def _claim(row: ClaimRow) -> Claim:
    return Claim(row.identifier, row.matter_id, row.statement, row.category, Provenance(row.provenance), row.revision_of_id, _utc(row.created_at))


def _reference(row: SourceReferenceRow) -> SourceReference:
    return SourceReference(row.identifier, row.claim_id, row.source_id, row.content_block_id, row.page, row.paragraph,
                           row.character_start, row.character_end, row.excerpt)


def _block(row: ContentBlockRow) -> ContentBlock:
    return ContentBlock(row.identifier, row.source_id, row.ordinal, row.text, row.locator, _utc(row.created_at))


def _review(row: ReviewDecisionRow) -> ReviewDecision:
    return ReviewDecision(row.identifier, row.claim_id, ReviewState(row.state), ActorKind(row.actor_kind), row.actor_id, row.note, _utc(row.created_at))


def _run(row: ProcessingRunRow) -> ProcessingRun:
    return ProcessingRun(row.identifier, row.matter_id, row.operation, tuple(json.loads(row.input_source_ids)),
                         ProcessingStatus(row.status), row.provider, row.model, row.workflow_version,
                         _utc(row.started_at), _utc(row.completed_at), row.error_summary)


def _brief(row: CaseBriefVersionRow) -> CaseBriefVersion:
    return CaseBriefVersion(row.identifier, row.matter_id, tuple(json.loads(row.source_ids)), tuple(json.loads(row.claim_ids)),
                            tuple(json.loads(row.review_decision_ids)), row.workflow_version, row.structured_payload,
                            row.rendered_text, _utc(row.created_at))


class SqlAlchemyMatterRepository:
    def __init__(self, session: Session) -> None: self.session = session
    def add(self, item: Matter) -> None:
        self.session.add(MatterRow(identifier=item.identifier, title=item.title, reference=item.reference, description=item.description,
                         status=item.status.value, created_at=item.created_at, updated_at=item.updated_at))
    def get(self, identifier: str) -> Matter | None:
        row = self.session.get(MatterRow, identifier)
        return _matter(row) if row else None
    def list(self) -> list[Matter]:
        return [_matter(row) for row in self.session.scalars(select(MatterRow).order_by(MatterRow.created_at)).all()]


class SqlAlchemySourceRepository:
    def __init__(self, session: Session) -> None: self.session = session
    def add(self, item: SourceRecord) -> None:
        self.session.add(SourceRow(identifier=item.identifier, matter_id=item.matter_id, kind=item.kind.value, provenance=item.provenance.value,
                         payload_sha256=item.payload_sha256, text=item.text, attachment_path=item.attachment_path,
                         original_filename=item.original_filename, media_type=item.media_type, correction_of_id=item.correction_of_id,
                         ingestion_status=item.ingestion_status, extraction_status=item.extraction_status, created_at=item.created_at,
                         update_type=item.update_type.value if item.update_type else None))
    def get(self, identifier: str) -> SourceRecord | None:
        row = self.session.get(SourceRow, identifier)
        return _source(row) if row else None
    def list_for_matter(self, matter_id: str) -> list[SourceRecord]:
        return [_source(row) for row in self.session.scalars(select(SourceRow).where(SourceRow.matter_id == matter_id).order_by(SourceRow.created_at)).all()]


class SqlAlchemyContentBlockRepository:
    def __init__(self, session: Session) -> None: self.session = session
    def add(self, item: ContentBlock) -> None:
        self.session.add(ContentBlockRow(identifier=item.identifier, source_id=item.source_id, ordinal=item.ordinal, text=item.text,
                         locator=item.locator, created_at=item.created_at))
    def list_for_source(self, source_id: str) -> list[ContentBlock]:
        return [_block(row) for row in self.session.scalars(select(ContentBlockRow).where(ContentBlockRow.source_id == source_id).order_by(ContentBlockRow.ordinal)).all()]


class SqlAlchemyClaimRepository:
    def __init__(self, session: Session) -> None: self.session = session
    def add(self, item: Claim) -> None:
        self.session.add(ClaimRow(identifier=item.identifier, matter_id=item.matter_id, statement=item.statement, category=item.category,
                         provenance=item.provenance.value, revision_of_id=item.revision_of_id, created_at=item.created_at))
    def get(self, identifier: str) -> Claim | None:
        row = self.session.get(ClaimRow, identifier)
        return _claim(row) if row else None
    def list_for_matter(self, matter_id: str) -> list[Claim]:
        return [_claim(row) for row in self.session.scalars(select(ClaimRow).where(ClaimRow.matter_id == matter_id).order_by(ClaimRow.created_at)).all()]


class SqlAlchemySourceReferenceRepository:
    def __init__(self, session: Session) -> None: self.session = session
    def add(self, item: SourceReference) -> None:
        self.session.add(SourceReferenceRow(identifier=item.identifier, claim_id=item.claim_id, source_id=item.source_id,
                         content_block_id=item.content_block_id, page=item.page, paragraph=item.paragraph,
                         character_start=item.character_start, character_end=item.character_end, excerpt=item.excerpt))
    def list_for_claim(self, claim_id: str) -> list[SourceReference]:
        return [_reference(row) for row in self.session.scalars(select(SourceReferenceRow).where(SourceReferenceRow.claim_id == claim_id)).all()]


class SqlAlchemyReviewRepository:
    def __init__(self, session: Session) -> None: self.session = session
    def add(self, item: ReviewDecision) -> None:
        self.session.add(ReviewDecisionRow(identifier=item.identifier, claim_id=item.claim_id, state=item.state.value,
                         actor_kind=item.actor_kind.value, actor_id=item.actor_id, note=item.note, created_at=item.created_at))
    def list_for_claim(self, claim_id: str) -> list[ReviewDecision]:
        return [_review(row) for row in self.session.scalars(select(ReviewDecisionRow).where(ReviewDecisionRow.claim_id == claim_id).order_by(ReviewDecisionRow.created_at, ReviewDecisionRow.identifier)).all()]


class SqlAlchemyProcessingRunRepository:
    def __init__(self, session: Session) -> None: self.session = session
    def add(self, item: ProcessingRun) -> None:
        self.session.add(ProcessingRunRow(identifier=item.identifier, matter_id=item.matter_id, operation=item.operation,
                         input_source_ids=json.dumps(item.input_source_ids), status=item.status.value, provider=item.provider,
                         model=item.model, workflow_version=item.workflow_version, started_at=item.started_at,
                         completed_at=item.completed_at, error_summary=item.error_summary))
    def get(self, identifier: str) -> ProcessingRun | None:
        row = self.session.get(ProcessingRunRow, identifier)
        return _run(row) if row else None


class SqlAlchemyCaseBriefRepository:
    def __init__(self, session: Session) -> None: self.session = session
    def add(self, item: CaseBriefVersion) -> None:
        self.session.add(CaseBriefVersionRow(identifier=item.identifier, matter_id=item.matter_id,
                         source_ids=json.dumps(item.source_ids), claim_ids=json.dumps(item.claim_ids),
                         review_decision_ids=json.dumps(item.review_decision_ids), workflow_version=item.workflow_version,
                         structured_payload=item.structured_payload, rendered_text=item.rendered_text, created_at=item.created_at))
    def get(self, identifier: str) -> CaseBriefVersion | None:
        row = self.session.get(CaseBriefVersionRow, identifier)
        return _brief(row) if row else None
