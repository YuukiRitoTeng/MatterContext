"""Case-list and workspace application boundaries used by the desktop shell."""

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Protocol

from matter_context.domain import ContentBlock, Matter, NarrativeUpdateType, SourceRecord

from .generation import OrganizedUpdateResult, StructuredGenerationService
from .matters import MatterService
from .persistence import AttachmentStorePort, UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class CaseListItem:
    """A future persisted matter represented for the Cases destination."""

    identifier: str
    title: str
    reference: str | None = None
    status: str = "active"


@dataclass(frozen=True, slots=True)
class CasesList:
    """Application result for the Cases destination."""

    items: tuple[CaseListItem, ...]


class CasesService(Protocol):
    """Application service contract; it deliberately has no Qt dependency."""

    def list_cases(self, search_text: str = "") -> CasesList:
        """Return the visible cases."""


class PersistedCasesService:
    """Lists durable matters without exposing SQLite to Qt."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    def list_cases(self, search_text: str = "") -> CasesList:
        with self._uow_factory() as uow:
            matters = uow.matters.list()
        query = search_text.strip().casefold()
        if query:
            matters = [
                matter for matter in matters
                if query in matter.title.casefold()
                or query in (matter.reference or "").casefold()
                or query in (matter.description or "").casefold()
            ]
        return CasesList(tuple(CaseListItem(m.identifier, m.title, m.reference, m.status.value) for m in matters))


class EmptyCasesService:
    """Empty implementation retained for focused presentation tests."""

    def list_cases(self, search_text: str = "") -> CasesList:
        return CasesList(items=())


@dataclass(frozen=True, slots=True)
class WorkspaceMatter:
    """Minimal matter read model required by the workspace presentation."""

    identifier: str
    title: str
    reference: str | None
    status_label: str


@dataclass(frozen=True, slots=True)
class WorkspaceSource:
    """Immutable source read model required by the workspace presentation."""

    identifier: str
    text: str | None
    correction_of_id: str | None
    created_at: datetime
    update_type: str | None
    update_type_label: str
    excerpt: str
    filename: str | None = None
    media_type: str | None = None
    ingestion_status: str = "ready"
    extraction_status: str = "not_started"
    duplicate_of_id: str | None = None
    blocks: tuple[ContentBlock, ...] = ()
    original_path: str | None = None
    error_summary: str | None = None


@dataclass(frozen=True, slots=True)
class NarrativeUpdateTypeChoice:
    """A submit-safe update-type value paired with its visible label."""

    value: str
    label: str


NARRATIVE_UPDATE_TYPE_CHOICES = (
    NarrativeUpdateTypeChoice("initial_account", "Initial account"),
    NarrativeUpdateTypeChoice("later_information", "Later information"),
    NarrativeUpdateTypeChoice("correction", "Correction"),
    NarrativeUpdateTypeChoice("attorney_note", "Attorney note"),
)
_UPDATE_TYPE_LABELS = {choice.value: choice.label for choice in NARRATIVE_UPDATE_TYPE_CHOICES}


def short_source_excerpt(text: str | None, *, limit: int = 80) -> str:
    """Return a stable, whitespace-normalized source discriminator."""
    normalized = " ".join((text or "").split())
    return normalized if len(normalized) <= limit else f"{normalized[:limit - 1]}…"


class MatterWorkspaceService(Protocol):
    """Application operations required by the one-window matter workspace."""

    def create_matter(
        self, title: str, *, reference: str | None = None, description: str | None = None,
    ) -> WorkspaceMatter: ...
    def get_matter(self, matter_id: str) -> WorkspaceMatter | None: ...
    def list_sources(self, matter_id: str) -> list[WorkspaceSource]: ...
    def append_narrative_update(
        self, matter_id: str, text: str, *, update_type: str,
        correction_of_id: str | None = None,
    ) -> WorkspaceSource: ...
    def ingest_document(self, matter_id: str, file_path: str, *, on_registered: Callable[[object], None] | None = None): ...
    def organize_selected_source(self, matter_id: str, source_id: str) -> OrganizedUpdateResult: ...


class PersistedMatterWorkspaceService:
    """Thin desktop-facing service that reuses the append-only MatterService."""

    def __init__(self, uow_factory: UnitOfWorkFactory, attachment_store: AttachmentStorePort | None = None,
                 generation_service: StructuredGenerationService | None = None) -> None:
        self._matters = MatterService(uow_factory)
        self._uow_factory = uow_factory
        self._attachment_store = attachment_store
        self._generation = generation_service or StructuredGenerationService(uow_factory)

    @staticmethod
    def _workspace_matter(matter: Matter) -> WorkspaceMatter:
        return WorkspaceMatter(matter.identifier, matter.title, matter.reference, matter.status.value.title())

    def _workspace_source(self, source: SourceRecord) -> WorkspaceSource:
        update_type = source.update_type.value if source.update_type is not None else None
        with self._uow_factory() as uow:
            blocks = tuple(uow.content_blocks.list_for_source(source.identifier))
            run = uow.processing_runs.latest_for_source(source.identifier)
        original_path = None
        if self._attachment_store and source.attachment_path:
            try:
                original_path = str(self._attachment_store.resolve(source.attachment_path))
            except ValueError:
                # Legacy or manually constructed paths are never passed to the OS.
                original_path = None
        return WorkspaceSource(
            source.identifier, source.text, source.correction_of_id, source.created_at, update_type,
            _UPDATE_TYPE_LABELS.get(update_type, "Case update" if source.text is not None else "File"),
            short_source_excerpt(source.text or (blocks[0].text if blocks else source.original_filename)),
            source.original_filename, source.media_type, str(source.ingestion_status), str(source.extraction_status),
            source.duplicate_of_id, blocks, original_path, run.error_summary if run else None,
        )

    def create_matter(
        self, title: str, *, reference: str | None = None, description: str | None = None,
    ) -> WorkspaceMatter:
        return self._workspace_matter(self._matters.create_matter(title, reference=reference, description=description))

    def get_matter(self, matter_id: str) -> WorkspaceMatter | None:
        matter = self._matters.get_matter(matter_id)
        return self._workspace_matter(matter) if matter is not None else None

    def list_sources(self, matter_id: str) -> list[WorkspaceSource]:
        return [self._workspace_source(source) for source in self._matters.list_sources(matter_id)]

    def append_narrative_update(
        self, matter_id: str, text: str, *, update_type: str,
        correction_of_id: str | None = None,
    ) -> WorkspaceSource:
        source = self._matters.append_narrative_update(
            matter_id, text, update_type=NarrativeUpdateType(update_type), correction_of_id=correction_of_id,
        )
        return self._workspace_source(source)

    def ingest_document(self, matter_id: str, file_path: str, *, on_registered: Callable[[object], None] | None = None):
        if self._attachment_store is None:
            raise RuntimeError("Document attachment storage is unavailable")
        from .ingestion import DocumentIngestionService
        return DocumentIngestionService(self._uow_factory, self._attachment_store).ingest(matter_id, file_path, on_registered=on_registered)

    def organize_selected_source(self, matter_id: str, source_id: str) -> OrganizedUpdateResult:
        return self._generation.organize_selected_source(matter_id, source_id)
