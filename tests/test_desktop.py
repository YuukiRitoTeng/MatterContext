from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QPushButton

from matter_context.application.cases import EmptyCasesService
from matter_context.ui.application import create_main_window, main
from matter_context.ui.cases import CasesViewModel, CasesWidget


def _set_runtime_paths(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MATTER_CONTEXT_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("MATTER_CONTEXT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("MATTER_CONTEXT_ATTACHMENTS_DIR", str(tmp_path / "data" / "attachments"))
    monkeypatch.setenv("MATTER_CONTEXT_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("MATTER_CONTEXT_DIAGNOSTICS_DIR", str(tmp_path / "data" / "diagnostics"))


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


def test_main_window_starts_with_cases_destination(qtbot, monkeypatch, tmp_path) -> None:
    _set_runtime_paths(monkeypatch, tmp_path)
    window = create_main_window()
    qtbot.addWidget(window)
    window.show()

    assert window.centralWidget().objectName() == "casesDestination"
    assert window.windowTitle() == "MatterContext"


def test_smoke_test_exits_zero(qtbot, monkeypatch, tmp_path) -> None:
    _set_runtime_paths(monkeypatch, tmp_path)
    assert main(["--smoke-test"]) == 0
