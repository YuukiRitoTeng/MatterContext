from __future__ import annotations

import ast
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPlainTextEdit, QPushButton

from matter_context.application.cases import (
    PersistedCasesService, PersistedMatterWorkspaceService, short_source_excerpt,
)
from matter_context.application.matters import MatterService
from matter_context.domain import NarrativeUpdateType
from matter_context.storage.database import Database, upgrade_database
from matter_context.storage.unit_of_work import SqlAlchemyUnitOfWork
from matter_context.ui.cases import CasesViewModel
from matter_context.ui.main_window import MainWindow
from matter_context.ui.workspace import CaseUpdateDialog


def _services(tmp_path):
    database = Database.from_url(f"sqlite:///{tmp_path / 'workspace.sqlite3'}")
    upgrade_database(str(database.engine.url))
    factory = lambda: SqlAlchemyUnitOfWork(database.session_factory)
    return PersistedCasesService(factory), PersistedMatterWorkspaceService(factory), database


def test_workspace_persists_case_creation_and_keeps_two_matters_isolated(tmp_path) -> None:
    _, workspace, _ = _services(tmp_path)
    first = workspace.create_matter("First matter", reference="MC-1", description="First description")
    second = workspace.create_matter("Second matter")
    workspace.append_narrative_update(first.identifier, "First matter only", update_type="initial_account")
    workspace.append_narrative_update(second.identifier, "Second matter only", update_type="attorney_note")

    assert workspace.get_matter(first.identifier).title == "First matter"
    assert [source.text for source in workspace.list_sources(first.identifier)] == ["First matter only"]
    assert [source.text for source in workspace.list_sources(second.identifier)] == ["Second matter only"]


def test_chinese_narrative_round_trips_across_application_instances(tmp_path) -> None:
    database = Database.from_url(f"sqlite:///{tmp_path / 'narrative.sqlite3'}")
    upgrade_database(str(database.engine.url))
    factory = lambda: SqlAlchemyUnitOfWork(database.session_factory)
    first = MatterService(factory)
    matter = first.create_matter("中文案件")
    text = "当事人称：2026年8月24日已支付全部款项。\n请保留原文。"
    first.append_narrative_update(matter.identifier, text, update_type=NarrativeUpdateType.INITIAL_ACCOUNT)
    database.engine.dispose()

    reopened = Database.from_url(str(database.engine.url))
    second = MatterService(lambda: SqlAlchemyUnitOfWork(reopened.session_factory))
    assert second.list_sources(matter.identifier)[0].text == text


def test_correction_link_preserves_earlier_source_text(tmp_path) -> None:
    _, workspace, _ = _services(tmp_path)
    matter = workspace.create_matter("Correction matter")
    original = workspace.append_narrative_update(
        matter.identifier, "The amount is 100.", update_type="initial_account",
    )
    correction = workspace.append_narrative_update(
        matter.identifier, "Correction: the amount is 120.", update_type="correction",
        correction_of_id=original.identifier,
    )

    sources = workspace.list_sources(matter.identifier)
    assert [source.text for source in sources] == ["The amount is 100.", "Correction: the amount is 120."]
    assert correction.correction_of_id == original.identifier
    assert sources[0].text == "The amount is 100."


def test_switching_matters_does_not_mix_sources(qtbot, tmp_path) -> None:
    cases, workspace, _ = _services(tmp_path)
    first = workspace.create_matter("First")
    second = workspace.create_matter("Second")
    workspace.append_narrative_update(first.identifier, "first source", update_type="initial_account")
    workspace.append_narrative_update(second.identifier, "second source", update_type="later_information")
    window = MainWindow(CasesViewModel(cases), workspace)
    qtbot.addWidget(window)
    window.show()

    window.open_matter(first.identifier)
    assert "first source" in window._workspace.source_list.item(0).text()
    window.open_matter(second.identifier)
    assert window._workspace.source_list.count() == 1
    assert "second source" in window._workspace.source_list.item(0).text()
    assert "first source" not in window._workspace.source_list.item(0).text()


def test_add_case_update_is_directly_reachable_and_plain_text(qtbot, tmp_path) -> None:
    cases, workspace, _ = _services(tmp_path)
    matter = workspace.create_matter("Reachable update")
    window = MainWindow(CasesViewModel(cases), workspace)
    qtbot.addWidget(window)
    window.show()
    window.open_matter(matter.identifier)

    action = window._workspace.findChild(QPushButton, "addCaseUpdateButton")
    qtbot.mouseClick(action, Qt.MouseButton.LeftButton)
    editor = window._workspace.update_dialog.findChild(QPlainTextEdit, "caseUpdateEditor")
    qtbot.waitUntil(window._workspace.update_dialog.isVisible)
    assert editor is not None
    assert editor.focusPolicy() & Qt.FocusPolicy.TabFocus
    assert not window._workspace.findChild(QPushButton, "addFilesButton").isEnabled()


def test_editor_submission_uses_application_update_type_values(qtbot, tmp_path) -> None:
    _, workspace, _ = _services(tmp_path)
    matter = workspace.create_matter("Saved through editor")
    dialog = CaseUpdateDialog(workspace, matter.identifier, [])
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.update_type.setCurrentIndex(dialog.update_type.findData("attorney_note"))
    dialog.editor.setPlainText("Attorney's exact note.")
    dialog.submit()

    sources = workspace.list_sources(matter.identifier)
    assert dialog.result() == dialog.DialogCode.Accepted
    assert [(source.update_type, source.text) for source in sources] == [
        ("attorney_note", "Attorney's exact note."),
    ]


def test_all_update_types_reopen_and_render_with_distinct_correction_target(qtbot, tmp_path) -> None:
    _, workspace, database = _services(tmp_path)
    matter = workspace.create_matter("All update types")
    original_text = "The original account says the payment was due on the first business day."
    original = workspace.append_narrative_update(matter.identifier, original_text, update_type="initial_account")
    later = workspace.append_narrative_update(
        matter.identifier, "Later information confirms the bank transfer.", update_type="later_information",
    )
    correction = workspace.append_narrative_update(
        matter.identifier, "Correction: the due date was actually Tuesday.", update_type="correction",
        correction_of_id=original.identifier,
    )
    attorney = workspace.append_narrative_update(
        matter.identifier, "Attorney note: preserve the client wording.", update_type="attorney_note",
    )
    database.engine.dispose()

    reopened_database = Database.from_url(str(database.engine.url))
    reopened = PersistedMatterWorkspaceService(lambda: SqlAlchemyUnitOfWork(reopened_database.session_factory))
    sources = reopened.list_sources(matter.identifier)
    assert [(source.identifier, source.update_type) for source in sources] == [
        (original.identifier, "initial_account"), (later.identifier, "later_information"),
        (correction.identifier, "correction"), (attorney.identifier, "attorney_note"),
    ]
    assert sources[0].text == original_text
    assert sources[2].correction_of_id == original.identifier

    from matter_context.ui.workspace import CaseUpdateDialog, MatterWorkspaceWidget

    widget = MatterWorkspaceWidget(reopened, matter.identifier, on_cases=lambda: None)
    qtbot.addWidget(widget)
    widget.show()
    rendered = "\n".join(widget.source_list.item(index).text() for index in range(widget.source_list.count()))
    assert all(label in rendered for label in ("Initial account", "Later information", "Correction", "Attorney note"))
    assert "refers to " in rendered
    assert f'— {sources[0].update_type_label} — "{sources[0].excerpt}"' in rendered
    assert original_text in rendered

    dialog = CaseUpdateDialog(reopened, matter.identifier, sources)
    target_index = dialog.correction_source.findData(original.identifier)
    assert target_index > 0
    assert sources[0].excerpt in dialog.correction_source.itemText(target_index)
    assert short_source_excerpt(original_text) == sources[0].excerpt


def test_update_failure_preserves_editor_text_and_shows_clear_error(qtbot) -> None:
    class FailingService:
        def __init__(self) -> None:
            self.calls = []

        def append_narrative_update(self, *args, **kwargs):
            self.calls.append((args, kwargs))
            raise RuntimeError("unavailable")

    service = FailingService()
    dialog = CaseUpdateDialog(service, "matter", [])
    qtbot.addWidget(dialog)
    dialog.show()
    text = "Keep this exact update."
    dialog.editor.setPlainText(text)
    dialog.submit()

    assert dialog.editor.toPlainText() == text
    assert "could not be saved" in dialog.error.text()
    assert service.calls == [(("matter", text), {"update_type": "initial_account", "correction_of_id": None})]


def test_qt_widgets_use_only_application_boundaries() -> None:
    root = Path(__file__).parents[1] / "src" / "matter_context" / "ui"
    for path in root.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            imported_modules = (
                [node.module] if isinstance(node, ast.ImportFrom) else [alias.name for alias in node.names]
            )
            for module in filter(None, imported_modules):
                assert not module.startswith("matter_context.domain"), f"{path.name} imports {module}"
                if module.startswith(("matter_context.storage", "matter_context.persistence", "matter_context.application.persistence")):
                    assert path.name == "application.py", f"{path.name} imports {module}"
