"""Read-only Cases application boundary used by the initial desktop shell."""

from dataclasses import dataclass
from typing import Protocol


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


class EmptyCasesService:
    """Foundation implementation until matter persistence is introduced."""

    def list_cases(self) -> CasesList:
        return CasesList(items=())
