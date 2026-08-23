"""Cases presentation models and the case-selection widget."""

from dataclasses import dataclass
from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout, QWidget,
)

from matter_context.application.cases import CaseListItem, CasesService


@dataclass(frozen=True, slots=True)
class CasesViewState:
    title: str
    empty_heading: str | None
    empty_body: str | None
    primary_action_text: str
    cases: tuple[CaseListItem, ...]


class CasesViewModel:
    """Qt-free mapping of the application result to presentation state."""

    def __init__(self, service: CasesService) -> None:
        self._service = service

    def load(self, search_text: str = "") -> CasesViewState:
        # Calling the no-argument form retains compatibility with small focused
        # read-only service fakes while production services receive searches.
        cases = (
            self._service.list_cases(search_text).items if search_text
            else self._service.list_cases().items
        )
        if not cases and not search_text.strip():
            return CasesViewState(
                title="Cases",
                empty_heading="No cases yet",
                empty_body="Create a case to keep its sources, review, and work together.",
                primary_action_text="Create a case",
                cases=(),
            )
        return CasesViewState(
            title="Cases",
            empty_heading=None,
            empty_body="No cases match your search." if not cases else None,
            primary_action_text="Create a case",
            cases=cases,
        )


class CasesWidget(QWidget):
    """Initial destination for finding, creating, and reopening cases."""

    def __init__(
        self, view_model: CasesViewModel, *, on_create: Callable[[], None] | None = None,
        on_open: Callable[[str], None] | None = None, parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("casesDestination")
        self._view_model = view_model
        self._on_create = on_create
        self._on_open = on_open

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)

        title = QLabel("Cases")
        title.setObjectName("casesTitle")
        title.setProperty("heading", True)
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(title)

        controls = QHBoxLayout()
        self.search = QLineEdit(self)
        self.search.setObjectName("caseSearchInput")
        self.search.setPlaceholderText("Search cases")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)
        self.primary_action = QPushButton("Create a case", self)
        self.primary_action.setObjectName("createCaseButton")
        self.primary_action.setDefault(True)
        self.primary_action.setAccessibleName("Create a case")
        self.primary_action.clicked.connect(self._create)
        controls.addWidget(self.search)
        controls.addWidget(self.primary_action)
        layout.addLayout(controls)

        self.empty_state = QFrame(self)
        self.empty_state.setObjectName("casesEmptyState")
        empty_layout = QVBoxLayout(self.empty_state)
        self.empty_heading = QLabel(self.empty_state)
        self.empty_heading.setObjectName("casesEmptyHeading")
        self.empty_body = QLabel(self.empty_state)
        self.empty_body.setObjectName("casesEmptyBody")
        self.empty_body.setWordWrap(True)
        empty_layout.addWidget(self.empty_heading)
        empty_layout.addWidget(self.empty_body)
        layout.addWidget(self.empty_state)

        self.case_list = QListWidget(self)
        self.case_list.setObjectName("caseList")
        self.case_list.setAccessibleName("Cases")
        self.case_list.itemActivated.connect(self._open_item)
        self.case_list.itemDoubleClicked.connect(self._open_item)
        layout.addWidget(self.case_list, 1)
        self.refresh()

    def refresh(self, *_: object) -> None:
        state = self._view_model.load(self.search.text())
        self.case_list.clear()
        for case in state.cases:
            item = QListWidgetItem(case.title)
            item.setData(Qt.ItemDataRole.UserRole, case.identifier)
            detail = " · ".join(part for part in (case.reference, case.status.replace("_", " ").title()) if part)
            item.setToolTip(detail or case.title)
            self.case_list.addItem(item)
        self.empty_state.setVisible(state.empty_heading is not None or bool(state.empty_body))
        self.empty_heading.setText(state.empty_heading or "")
        self.empty_body.setText(state.empty_body or "")
        self.case_list.setVisible(bool(state.cases))

    def _create(self) -> None:
        if self._on_create:
            self._on_create()

    def _open_item(self, item: QListWidgetItem) -> None:
        identifier = item.data(Qt.ItemDataRole.UserRole)
        if self._on_open and isinstance(identifier, str):
            self._on_open(identifier)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.primary_action.setFocus(Qt.FocusReason.OtherFocusReason)
