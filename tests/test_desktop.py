from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QPushButton

from matter_context.application.cases import EmptyCasesService
from matter_context.ui.application import create_main_window, main
from matter_context.ui.cases import CasesViewModel, CasesWidget


def test_cases_empty_state_is_visible_and_keyboard_focused(qtbot) -> None:
    widget = CasesWidget(CasesViewModel(EmptyCasesService()))
    qtbot.addWidget(widget)
    widget.show()

    action = widget.findChild(QPushButton, "createCaseButton")
    qtbot.waitUntil(action.hasFocus, timeout=1000)
    assert action.hasFocus()
    assert action.isVisible()
    assert action.focusPolicy() & Qt.FocusPolicy.TabFocus
    assert widget.findChild(QLabel, "casesTitle").text() == "Cases"
    assert widget.findChild(QLabel, "casesEmptyHeading").text() == "No cases yet"
    assert widget.findChild(QFrame, "casesEmptyState").isVisible()


def test_main_window_starts_with_cases_destination(qtbot) -> None:
    window = create_main_window()
    qtbot.addWidget(window)
    window.show()

    assert window.centralWidget().objectName() == "casesDestination"
    assert window.windowTitle() == "MatterContext"


def test_smoke_test_exits_zero(qtbot) -> None:
    assert main(["--smoke-test"]) == 0
