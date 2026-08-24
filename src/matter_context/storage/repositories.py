"""SQLAlchemy repositories translating rows at the storage boundary."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from matter_context.domain import (
    ActorKind, CaseBriefVersion, Claim, ContentBlock, Matter, MatterStatus, NarrativeUpdateType, ProcessingRun,
    ProcessingRunTransitionError, ProcessingStatus, Provenance, ReviewDecision, ReviewState, SourceKind, SourceRecord,
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
    return SourceRecord(identifier=row.identifier, matter_id=row.matter_id, kind=SourceKind(row.kind), provenance=Provenance(row.provenance), payload_sha256=row.payload_sha256,
                        text=row.text, attachment_path=row.attachment_path, original_filename=row.original_filename, media_type=row.media_type, correction_of_id=row.correction_of_id,
                        ingestion_status=row.ingestion_status, extraction_status=row.extraction_status, duplicate_of_id=row.duplicate_of_id,
                        created_at=_utc(row.created_at), update_type=NarrativeUpdateType(row.update_type) if row.update_type else None)


def _claim(row: ClaimRow) -> Claim:
    return Claim(row.identifier, row.matter_id, row.statement, row.category, Provenance(row.provenance), row.revision_of_id, _utc(row.created_at))


def _reference(row: SourceReferenceRow) -> SourceReference:
    return SourceReference(row.identifier, row.claim_id, row.source_id, row.content_block_id, row.page, row.paragraph,
                           row.character_start, row.character_end, row.excerpt)


def _block(row: ContentBlockRow) -> ContentBlock:
    return ContentBlock(identifier=row.identifier, source_id=row.source_id, ordinal=row.ordinal, text=row.text, locator=row.locator,
                        created_at=_utc(row.created_at), page=row.page, paragraph=row.paragraph,
                        character_start=row.character_start, character_end=row.character_end)


def _review(row: ReviewDecisionRow) -> ReviewDecision:
    return ReviewDecision(row.identifier, row.claim_id, ReviewState(row.state), ActorKind(row.actor_kind), row.actor_id, row.note, _utc(row.created_at))


def _run(row: ProcessingRunRow) -> ProcessingRun:
    return ProcessingRun(row.identifier, row.matter_id, row.operation, tuple(json.loads(row.input_source_ids)),
                         ProcessingStatus(row.status), row.provider, row.model, row.workflow_version,
                         _utc(row.started_at), _utc(row.completed_at), row.error_summary, row.parser_name, row.parser_version, row.duration_ms)


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
                         duplicate_of_id=item.duplicate_of_id,
                         ingestion_status=item.ingestion_status, extraction_status=item.extraction_status, created_at=item.created_at,
                         update_type=item.update_type.value if item.update_type else None))
    def add_document_with_duplicate_detection(self, item: SourceRecord) -> str | None:
        """Insert first, then inspect committed-in-transaction peers under SQLite's writer lock.

        Flushing the insert before the lookup serializes concurrent SQLite writers: a second
        import cannot perform its lookup until the first transaction has committed. Unlike a
        pre-insert lookup, this always links a concurrent attempted import to an existing row.
        """
        self.add(item)
        self.session.flush()
        duplicate_id = self.session.scalar(
            select(SourceRow.identifier).where(
                SourceRow.matter_id == item.matter_id,
                SourceRow.payload_sha256 == item.payload_sha256,
                SourceRow.identifier != item.identifier,
                SourceRow.duplicate_of_id.is_(None),
            ).order_by(SourceRow.created_at, SourceRow.identifier)
        )
        if duplicate_id is not None:
            self.session.execute(
                update(SourceRow).where(SourceRow.identifier == item.identifier).values(duplicate_of_id=duplicate_id)
            )
        return duplicate_id
    def get(self, identifier: str) -> SourceRecord | None:
        row = self.session.get(SourceRow, identifier)
        return _source(row) if row else None
    def list_for_matter(self, matter_id: str) -> list[SourceRecord]:
        return [_source(row) for row in self.session.scalars(select(SourceRow).where(SourceRow.matter_id == matter_id).order_by(SourceRow.created_at)).all()]
    def find_by_hash(self, matter_id: str, payload_sha256: str) -> SourceRecord | None:
        row = self.session.scalar(select(SourceRow).where(SourceRow.matter_id == matter_id, SourceRow.payload_sha256 == payload_sha256).order_by(SourceRow.created_at, SourceRow.identifier))
        return _source(row) if row else None
    def update_status(self, identifier: str, *, ingestion_status: str, extraction_status: str) -> None:
        result = self.session.execute(
            update(SourceRow).where(SourceRow.identifier == identifier).values(
                ingestion_status=ingestion_status, extraction_status=extraction_status,
            )
        )
        if result.rowcount != 1:
            raise ProcessingRunTransitionError("Source status update requires an existing source")


class SqlAlchemyContentBlockRepository:
    def __init__(self, session: Session) -> None: self.session = session
    def add(self, item: ContentBlock) -> None:
        self.session.add(ContentBlockRow(identifier=item.identifier, source_id=item.source_id, ordinal=item.ordinal, text=item.text,
                         locator=item.locator, page=item.page, paragraph=item.paragraph, character_start=item.character_start,
                         character_end=item.character_end, created_at=item.created_at))
    def list_for_source(self, source_id: str) -> list[ContentBlock]:
        return [_block(row) for row in self.session.scalars(select(ContentBlockRow).where(ContentBlockRow.source_id == source_id).order_by(ContentBlockRow.ordinal)).all()]
    def replace_for_source(self, source_id: str, blocks: list[ContentBlock]) -> None:
        self.session.execute(delete(ContentBlockRow).where(ContentBlockRow.source_id == source_id))
        for block in blocks:
            self.add(block)


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
    def start(self, item: ProcessingRun) -> None:
        if item.status is not ProcessingStatus.RUNNING:
            raise ProcessingRunTransitionError("Only a running processing run can be started")
        self.session.add(ProcessingRunRow(identifier=item.identifier, matter_id=item.matter_id, operation=item.operation,
                         input_source_ids=json.dumps(item.input_source_ids), status=item.status.value, provider=item.provider,
                         model=item.model, workflow_version=item.workflow_version, started_at=item.started_at,
                         completed_at=item.completed_at, error_summary=item.error_summary, parser_name=item.parser_name,
                         parser_version=item.parser_version, duration_ms=item.duration_ms))
    def get(self, identifier: str) -> ProcessingRun | None:
        row = self.session.get(ProcessingRunRow, identifier)
        return _run(row) if row else None
    def finish(self, item: ProcessingRun) -> None:
        if item.status is ProcessingStatus.RUNNING:
            raise ProcessingRunTransitionError("A running processing run cannot be finished")
        result = self.session.execute(update(ProcessingRunRow).where(
            ProcessingRunRow.identifier == item.identifier,
            ProcessingRunRow.status == ProcessingStatus.RUNNING.value,
        ).values(
            status=item.status.value, completed_at=item.completed_at, error_summary=item.error_summary,
            parser_name=item.parser_name, parser_version=item.parser_version, duration_ms=item.duration_ms,
        ))
        if result.rowcount != 1:
            raise ProcessingRunTransitionError("Processing run is missing or is no longer running")
    def latest_for_source(self, source_id: str) -> ProcessingRun | None:
        rows = self.session.scalars(select(ProcessingRunRow).order_by(ProcessingRunRow.started_at.desc(), ProcessingRunRow.identifier.desc())).all()
        for row in rows:
            if source_id in json.loads(row.input_source_ids):
                return _run(row)
        return None


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
