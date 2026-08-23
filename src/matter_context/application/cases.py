"""Read-only Cases application boundary used by the desktop shell."""

from dataclasses import dataclass
from typing import Protocol

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

    def list_cases(self) -> CasesList:
        """Return the visible cases."""


class PersistedCasesService:
    """Lists durable matters without exposing SQLite to Qt."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    def list_cases(self) -> CasesList:
        with self._uow_factory() as uow:
            matters = uow.matters.list()
        return CasesList(tuple(CaseListItem(m.identifier, m.title, m.reference, m.status.value) for m in matters))


class EmptyCasesService:
    """Empty implementation retained for focused presentation tests."""

    def list_cases(self) -> CasesList:
        return CasesList(items=())
