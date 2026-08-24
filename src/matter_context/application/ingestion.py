"""Durable, local document ingestion orchestration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from time import monotonic
from zipfile import BadZipFile

from pypdf.errors import PdfReadError

from matter_context.domain import ContentBlock, ExtractionStatus, IngestionStatus, ProcessingRun, ProcessingRunTransitionError, Provenance, SourceKind, SourceRecord
from matter_context.ingestion.parsers import ExtractionCompleteness, extract_document, parser_metadata
from matter_context.ingestion.validation import DocumentValidationError, ValidatedDocument, media_type_for_filename, validate_document, validate_storable_path
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
        started = monotonic()
        if on_registered is not None:
            try:
                on_registered(IngestionResult(source.identifier, run.identifier, IngestionStatus.PROCESSING, source.duplicate_of_id))
            except Exception as error:
                self._fail(source, run, error, started)
                raise
        try:
            validated = validate_document(self._attachments.resolve(stored.relative_path), filename=registered.filename)
            extracted = extract_document(validated.path, validated.media_type)
        except Exception as error:
            return self._fail(source, run, error, started)

        try:
            blocks = [ContentBlock(identifier=new_identifier(), source_id=source.identifier, ordinal=item.ordinal, text=item.text, locator=item.locator, page=item.page, paragraph=item.paragraph, character_start=item.character_start, character_end=item.character_end) for item in extracted.blocks]
            status, extraction, completed = _ingestion_completion(run, extracted.completeness, validated.media_type, round((monotonic() - started) * 1000))
            with self._uow_factory() as uow:
                uow.content_blocks.replace_for_source(source.identifier, blocks)
                uow.sources.update_status(source.identifier, ingestion_status=status.value, extraction_status=extraction.value)
                uow.processing_runs.finish(completed)
                uow.commit()
            return IngestionResult(source.identifier, run.identifier, status, source.duplicate_of_id)
        except Exception as error:
            self._fail(source, run, error, started)
            raise

    def _register(self, matter_id: str, document: ValidatedDocument, attachment_path: str, digest: str) -> tuple[SourceRecord, ProcessingRun]:
        with self._uow_factory() as uow:
            source = SourceRecord(identifier=new_identifier(), matter_id=matter_id, kind=SourceKind.DOCUMENT, provenance=Provenance.ORIGINAL_SOURCE, payload_sha256=digest, attachment_path=attachment_path, original_filename=document.filename, media_type=document.media_type, ingestion_status=IngestionStatus.PROCESSING, extraction_status=ExtractionStatus.RUNNING)
            parser_name, parser_version = parser_metadata(document.media_type)
            run = ProcessingRun.start(new_identifier(), matter_id, "document_ingestion", (source.identifier,), parser_name=parser_name, parser_version=parser_version)
            duplicate_id = uow.sources.add_document_with_duplicate_detection(source)
            source = replace(source, duplicate_of_id=duplicate_id)
            uow.processing_runs.start(run)
            uow.commit()
        return source, run

    def _fail(
        self, source: SourceRecord, run: ProcessingRun, error: Exception, started: float,
    ) -> IngestionResult:
        summary = _safe_error(error)
        failed = run.fail(summary, duration_ms=round((monotonic() - started) * 1000))
        with self._uow_factory() as uow:
            uow.sources.update_status(
                source.identifier,
                ingestion_status=IngestionStatus.FAILED.value,
                extraction_status=ExtractionStatus.FAILED.value,
            )
            uow.processing_runs.finish(failed)
            uow.commit()
        return IngestionResult(source.identifier, run.identifier, IngestionStatus.FAILED, source.duplicate_of_id, summary)


def _safe_error(error: Exception) -> str:
    """Classify failures without persisting exception-controlled text in matter data."""
    if isinstance(error, DocumentValidationError):
        return "Document validation failed."
    if isinstance(error, FileNotFoundError):
        return "Stored document is unavailable."
    if isinstance(error, PermissionError):
        return "Document file access was denied."
    if isinstance(error, OSError):
        return "Document file access failed."
    if isinstance(error, UnicodeError):
        return "Document text encoding could not be read."
    if isinstance(error, BadZipFile):
        return "DOCX content could not be read."
    if isinstance(error, PdfReadError):
        return "PDF content could not be read."
    if isinstance(error, ProcessingRunTransitionError):
        return "Document processing state could not be finalized."
    if isinstance(error, ValueError):
        return "Document content could not be processed."
    return "Document processing failed."


def _ingestion_completion(
    run: ProcessingRun, completeness: ExtractionCompleteness, media_type: str, duration_ms: int,
) -> tuple[IngestionStatus, ExtractionStatus, ProcessingRun]:
    """Map parser truthfulness to durable states without treating partial text as ready."""
    if completeness is ExtractionCompleteness.COMPLETE:
        return IngestionStatus.READY, ExtractionStatus.EXTRACTED, run.succeed(duration_ms=duration_ms)
    if completeness is ExtractionCompleteness.PARTIAL:
        return IngestionStatus.NEEDS_REVIEW, ExtractionStatus.PARTIAL, run.complete_partially(duration_ms=duration_ms)
    if media_type == "application/pdf":
        return IngestionStatus.NEEDS_OCR, ExtractionStatus.NO_TEXT, run.complete_partially(duration_ms=duration_ms)
    return IngestionStatus.NEEDS_REVIEW, ExtractionStatus.NO_TEXT, run.complete_partially(duration_ms=duration_ms)
