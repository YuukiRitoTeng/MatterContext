"""Case-list and workspace application boundaries used by the desktop shell."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from matter_context.domain import Matter, NarrativeUpdateType, SourceRecord

from .matters import MatterService
from .persistence import UnitOfWorkFactory


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


class PersistedMatterWorkspaceService:
    """Thin desktop-facing service that reuses the append-only MatterService."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._matters = MatterService(uow_factory)

    @staticmethod
    def _workspace_matter(matter: Matter) -> WorkspaceMatter:
        return WorkspaceMatter(matter.identifier, matter.title, matter.reference, matter.status.value.title())

    @staticmethod
    def _workspace_source(source: SourceRecord) -> WorkspaceSource:
        update_type = source.update_type.value if source.update_type is not None else None
        return WorkspaceSource(
            source.identifier, source.text, source.correction_of_id, source.created_at, update_type,
            _UPDATE_TYPE_LABELS.get(update_type, "Case update" if source.text is not None else "File"),
            short_source_excerpt(source.text),
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
