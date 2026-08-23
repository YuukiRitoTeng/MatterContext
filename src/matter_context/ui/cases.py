"""Cases presentation models and widget."""

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

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

    def load(self) -> CasesViewState:
        cases = self._service.list_cases().items
        if not cases:
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
            empty_body=None,
            primary_action_text="Create a case",
            cases=cases,
        )


class CasesWidget(QWidget):
    """Initial destination; persistence and case creation arrive in later work."""

    def __init__(self, view_model: CasesViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("casesDestination")
        state = view_model.load()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)

        title = QLabel(state.title)
        title.setObjectName("casesTitle")
        title.setProperty("heading", True)
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(title)

        if state.empty_heading:
            empty_state = QFrame(self)
            empty_state.setObjectName("casesEmptyState")
            empty_layout = QVBoxLayout(empty_state)
            empty_heading = QLabel(state.empty_heading)
            empty_heading.setObjectName("casesEmptyHeading")
            empty_body = QLabel(state.empty_body or "")
            empty_body.setObjectName("casesEmptyBody")
            empty_body.setWordWrap(True)
            self.primary_action = QPushButton(state.primary_action_text)
            self.primary_action.setObjectName("createCaseButton")
            self.primary_action.setDefault(True)
            self.primary_action.setAccessibleName(state.primary_action_text)
            empty_layout.addWidget(empty_heading)
            empty_layout.addWidget(empty_body)
            empty_layout.addWidget(self.primary_action, alignment=Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(empty_state)
        else:
            self.primary_action = QPushButton(state.primary_action_text)
            self.primary_action.setObjectName("createCaseButton")
            layout.addWidget(self.primary_action, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addStretch(1)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.primary_action.setFocus(Qt.FocusReason.OtherFocusReason)
