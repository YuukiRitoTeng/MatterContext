"""Durable, local document ingestion orchestration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from time import monotonic

from matter_context.domain import ContentBlock, ExtractionStatus, IngestionStatus, ProcessingRun, ProcessingStatus, Provenance, SourceKind, SourceRecord, utcnow
from matter_context.ingestion.parsers import ExtractionCompleteness, extract_document, parser_metadata
from matter_context.ingestion.validation import ValidatedDocument, media_type_for_filename, validate_document, validate_storable_path
from .matters import new_identifier
from .persistence import AttachmentStorePort, UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class IngestionResult:
    source_id: str
    run_id: str
    status: IngestionStatus
    duplicate_of_id: str | None = None
    error_summary: str | None = None


class DocumentIngestionService:
    def __init__(self, uow_factory: UnitOfWorkFactory, attachment_store: AttachmentStorePort) -> None:
        self._uow_factory = uow_factory
        self._attachments = attachment_store

    def ingest(self, matter_id: str, file_path: str | Path, *, on_registered: Callable[[IngestionResult], None] | None = None) -> IngestionResult:
        input_path = validate_storable_path(file_path)
        stored = self._attachments.store(input_path, max_bytes=50 * 1024 * 1024)
        registered = ValidatedDocument(input_path, input_path.name, media_type_for_filename(input_path.name))
        try:
            source, run = self._register(matter_id, registered, stored.relative_path, stored.sha256)
        except Exception:
            self._attachments.delete(stored.relative_path)
            raise
        if on_registered is not None:
            on_registered(IngestionResult(source.identifier, run.identifier, IngestionStatus.PROCESSING, source.duplicate_of_id))
        started = monotonic()
        parser_name, parser_version = parser_metadata(registered.media_type)
        try:
            validated = validate_document(self._attachments.resolve(stored.relative_path), filename=registered.filename)
            parser_name, parser_version = parser_metadata(validated.media_type)
            extracted = extract_document(validated.path, validated.media_type)
            blocks = [ContentBlock(identifier=new_identifier(), source_id=source.identifier, ordinal=item.ordinal, text=item.text, locator=item.locator, page=item.page, paragraph=item.paragraph, character_start=item.character_start, character_end=item.character_end) for item in extracted.blocks]
            status, extraction, run_status = _ingestion_outcome(extracted.completeness, validated.media_type)
            completed = replace(run, status=run_status, completed_at=utcnow(), parser_name=extracted.parser_name, parser_version=extracted.parser_version, duration_ms=round((monotonic() - started) * 1000))
            with self._uow_factory() as uow:
                uow.content_blocks.replace_for_source(source.identifier, blocks)
                uow.sources.update_status(source.identifier, ingestion_status=status.value, extraction_status=extraction.value)
                uow.processing_runs.update(completed)
                uow.commit()
            return IngestionResult(source.identifier, run.identifier, status, source.duplicate_of_id)
        except Exception as error:
            summary = _safe_error(error)
            completed = replace(run, status=ProcessingStatus.FAILED, completed_at=utcnow(), error_summary=summary, parser_name=parser_name, parser_version=parser_version, duration_ms=round((monotonic() - started) * 1000))
            with self._uow_factory() as uow:
                uow.sources.update_status(source.identifier, ingestion_status=IngestionStatus.FAILED.value, extraction_status=ExtractionStatus.FAILED.value)
                uow.processing_runs.update(completed)
                uow.commit()
            return IngestionResult(source.identifier, run.identifier, IngestionStatus.FAILED, source.duplicate_of_id, summary)

    def _register(self, matter_id: str, document: ValidatedDocument, attachment_path: str, digest: str) -> tuple[SourceRecord, ProcessingRun]:
        with self._uow_factory() as uow:
            source = SourceRecord(identifier=new_identifier(), matter_id=matter_id, kind=SourceKind.DOCUMENT, provenance=Provenance.ORIGINAL_SOURCE, payload_sha256=digest, attachment_path=attachment_path, original_filename=document.filename, media_type=document.media_type, ingestion_status=IngestionStatus.PROCESSING, extraction_status=ExtractionStatus.RUNNING)
            parser_name, parser_version = parser_metadata(document.media_type)
            run = ProcessingRun(new_identifier(), matter_id, "document_ingestion", (source.identifier,), ProcessingStatus.RUNNING, parser_name=parser_name, parser_version=parser_version)
            duplicate_id = uow.sources.add_document_with_duplicate_detection(source)
            source = replace(source, duplicate_of_id=duplicate_id)
            uow.processing_runs.add(run)
            uow.commit()
        return source, run


def _safe_error(error: Exception) -> str:
    message = " ".join(str(error).split()) or "Document extraction failed"
    return message.replace("/", "").replace("\\", "")[:500]


def _ingestion_outcome(
    completeness: ExtractionCompleteness, media_type: str,
) -> tuple[IngestionStatus, ExtractionStatus, ProcessingStatus]:
    """Map parser truthfulness to durable states without treating partial text as ready."""
    if completeness is ExtractionCompleteness.COMPLETE:
        return IngestionStatus.READY, ExtractionStatus.EXTRACTED, ProcessingStatus.SUCCEEDED
    if completeness is ExtractionCompleteness.PARTIAL:
        return IngestionStatus.NEEDS_REVIEW, ExtractionStatus.PARTIAL, ProcessingStatus.PARTIAL
    if media_type == "application/pdf":
        return IngestionStatus.NEEDS_OCR, ExtractionStatus.NO_TEXT, ProcessingStatus.PARTIAL
    return IngestionStatus.NEEDS_REVIEW, ExtractionStatus.NO_TEXT, ProcessingStatus.PARTIAL
