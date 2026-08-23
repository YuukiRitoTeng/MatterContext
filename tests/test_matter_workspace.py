from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QFileDialog, QPlainTextEdit, QPushButton

from matter_context.application.cases import (
    PersistedCasesService, PersistedMatterWorkspaceService, WorkspaceMatter, WorkspaceSource, short_source_excerpt,
)
from matter_context.application.matters import MatterService
from matter_context.domain import ContentBlock, NarrativeUpdateType
from matter_context.storage.database import Database, upgrade_database
from matter_context.storage.attachments import AttachmentStore
from matter_context.storage.unit_of_work import SqlAlchemyUnitOfWork
from matter_context.ui.cases import CasesViewModel
from matter_context.ui.main_window import MainWindow
from matter_context.ui.workspace import CaseUpdateDialog, MatterWorkspaceWidget


class _DocumentWorkspaceService:
    def __init__(self, sources: list[WorkspaceSource]) -> None:
        self.sources = sources

    def get_matter(self, _: str) -> WorkspaceMatter:
        return WorkspaceMatter("matter", "Document matter", None, "Active")

    def list_sources(self, _: str) -> list[WorkspaceSource]:
        return self.sources

    def ingest_document(self, _: str, __: str):
        raise AssertionError("UI submission test replaces _submit_file")


def _document_source(*, media_type: str = "text/plain", text: str = "Extracted 中文 text", duplicate: bool = False, original_path: str | None = None, status: str = "ready", error_summary: str | None = None) -> WorkspaceSource:
    return WorkspaceSource(
        "document", None, None, datetime.now(timezone.utc), None, "File", text[:20],
        "证据.pdf" if media_type == "application/pdf" else "证据.txt", media_type, status, "failed" if status == "failed" else "extracted",
        "existing-document" if duplicate else None,
        (ContentBlock("block", "document", 0, text, "page:1" if media_type == "application/pdf" else "characters:0-1", page=1 if media_type == "application/pdf" else None),),
        original_path, error_summary,
    )


def _write_two_page_native_pdf(path: Path) -> None:
    def stream(text: bytes) -> bytes:
        content = b"BT /F1 12 Tf 72 720 Td (" + text + b") Tj ET"
        return b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream"

    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [4 0 R 6 0 R] /Count 2 >>",
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        4: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents 5 0 R >>",
        5: stream(b"First page selectable native text."),
        6: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents 7 0 R >>",
        7: stream(b"Second page selectable native text."),
    }
    payload = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number in range(1, 8):
        offsets.append(len(payload))
        payload.extend(f"{number} 0 obj\n".encode() + objects[number] + b"\nendobj\n")
    startxref = len(payload)
    payload.extend(b"xref\n0 8\n0000000000 65535 f \n")
    payload.extend(b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:]))
    payload.extend(f"trailer\n<< /Size 8 /Root 1 0 R >>\nstartxref\n{startxref}\n%%EOF\n".encode())
    path.write_bytes(payload)


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
    assert window._workspace.findChild(QPushButton, "addFilesButton").isEnabled()


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


def test_picker_and_drop_share_document_submission_path(qtbot, monkeypatch) -> None:
    widget = MatterWorkspaceWidget(_DocumentWorkspaceService([]), "matter", on_cases=lambda: None)
    qtbot.addWidget(widget)
    submitted: list[str] = []
    monkeypatch.setattr(widget, "_submit_file", submitted.append)
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *args: (["/tmp/picker.txt"], "Documents"))

    widget.choose_files()
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile("/tmp/drop.txt")])
    widget.sources_page.dropEvent(QDropEvent(QPointF(1, 1), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))

    assert submitted == ["/tmp/picker.txt", "/tmp/drop.txt"]


def test_document_preview_duplicate_notice_and_open_original(qtbot, monkeypatch, tmp_path) -> None:
    original = tmp_path / "managed-original.txt"
    original.write_text("preserved", encoding="utf-8")
    widget = MatterWorkspaceWidget(
        _DocumentWorkspaceService([_document_source(duplicate=True, original_path=str(original))]), "matter", on_cases=lambda: None,
    )
    qtbot.addWidget(widget)
    widget.show()
    widget.sections.setCurrentWidget(widget.sources_page)
    widget.source_list.setCurrentRow(0)
    opened = []
    monkeypatch.setattr("matter_context.ui.workspace.QDesktopServices.openUrl", lambda url: opened.append(url) or True)

    assert "duplicate content already exists" in widget.source_list.item(0).text()
    assert "Extracted 中文 text" in widget.preview.toPlainText()
    assert widget.open_original.isEnabled()
    qtbot.mouseClick(widget.open_original, Qt.MouseButton.LeftButton)
    assert opened and opened[0].toLocalFile() == str(original)


def test_failed_document_status_and_sanitized_error_are_visible(qtbot, tmp_path) -> None:
    database = Database.from_url(f"sqlite:///{tmp_path / 'failed-ui.sqlite3'}")
    upgrade_database(str(database.engine.url))
    factory = lambda: SqlAlchemyUnitOfWork(database.session_factory)
    workspace = PersistedMatterWorkspaceService(factory, AttachmentStore(tmp_path / "attachments"))
    matter = workspace.create_matter("Failed document")
    corrupt = tmp_path / "corrupt.pdf"
    corrupt.write_bytes(b"%PDF-1.7 malformed")
    result = workspace.ingest_document(matter.identifier, str(corrupt))
    assert result.status.value == "failed"
    widget = MatterWorkspaceWidget(workspace, matter.identifier, on_cases=lambda: None)
    qtbot.addWidget(widget)
    widget.show()
    widget.sections.setCurrentWidget(widget.sources_page)

    label = widget.source_list.item(0).text()
    assert "[failed]" in label
    assert "malformed" in label.lower() or "pdf" in label.lower()
    assert str(tmp_path) not in label


def test_pdf_preview_opens_referenced_one_based_page_in_real_native_pdf(qtbot, tmp_path) -> None:
    database = Database.from_url(f"sqlite:///{tmp_path / 'preview.sqlite3'}")
    upgrade_database(str(database.engine.url))
    factory = lambda: SqlAlchemyUnitOfWork(database.session_factory)
    workspace = PersistedMatterWorkspaceService(factory, AttachmentStore(tmp_path / "attachments"))
    matter = workspace.create_matter("PDF preview")
    original = tmp_path / "native.pdf"
    _write_two_page_native_pdf(original)
    result = workspace.ingest_document(matter.identifier, str(original))
    assert result.status.value == "ready"
    assert [block.page for block in workspace.list_sources(matter.identifier)[0].blocks] == [1, 2]
    widget = MatterWorkspaceWidget(workspace, matter.identifier, on_cases=lambda: None)
    qtbot.addWidget(widget)
    widget.show()
    widget.sections.setCurrentWidget(widget.sources_page)
    widget.source_list.setCurrentRow(0)

    qtbot.waitUntil(lambda: widget._pdf_document.pageCount() == 2, timeout=1500)
    assert widget.pdf_preview.isVisible()
    assert widget.pdf_page.value() == 1
    assert widget.pdf_page.maximum() == 2
    widget.pdf_page.setValue(2)
    qtbot.mouseClick(widget.open_pdf_page_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: widget.pdf_preview.pageNavigator().currentPage() == 1, timeout=1500)
