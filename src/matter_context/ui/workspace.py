"""Single-window case workspace widgets backed only by application services."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import QPointF, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QDragEnterEvent, QDropEvent, QShowEvent
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QFileDialog, QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton, QSpinBox, QTabWidget,
    QVBoxLayout, QWidget,
)
from matter_context.execution.tasks import DocumentIngestionTask, StructuredGenerationTask
from matter_context.ui.background import QtBackgroundExecutor

from matter_context.application.cases import (
    NARRATIVE_UPDATE_TYPE_CHOICES, MatterWorkspaceService, WorkspaceSource,
)


def _format_timestamp(value: datetime) -> str:
    return value.astimezone().strftime("%Y-%m-%d %H:%M")


def _extraction_notice_kind(source: WorkspaceSource) -> str | None:
    """Return the most specific extraction outcome shown to the user."""
    if source.ingestion_status == "needs_ocr":
        return "needs_ocr"
    if source.extraction_status == "no_text":
        return "no_text"
    if source.ingestion_status == "needs_review":
        return "incomplete"
    return None


def _source_preview_message(source: WorkspaceSource, preview: str) -> str:
    """Keep useful extracted text visible without hiding that it is incomplete."""
    notice = _extraction_notice_kind(source)
    if notice == "needs_ocr":
        heading = "No extractable text was found. This document needs OCR before use."
    elif notice == "no_text":
        heading = "No extractable text was found. Review the original document before use."
    elif notice == "incomplete":
        heading = "Extracted text is incomplete. Review or reprocess the original before using this source."
    else:
        return preview
    return f"{heading}\n\n{preview}" if preview else heading


class SourceDropSurface(QWidget):
    """Dedicated drop target that shares the workspace file-submission path."""

    def __init__(self, submit_files: Callable[[list[str]], None], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._submit_files = submit_files
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        self._submit_files([url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()])
        event.acceptProposedAction()


class CreateCaseDialog(QDialog):
    """Collect the small amount of information needed to start a case."""

    def __init__(self, service: MatterWorkspaceService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create a case")
        self.setObjectName("createCaseDialog")
        self._service = service
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.title_input = QLineEdit(self)
        self.title_input.setObjectName("caseTitleInput")
        self.title_input.setAccessibleName("Case title")
        self.reference_input = QLineEdit(self)
        self.reference_input.setObjectName("caseReferenceInput")
        self.description_input = QPlainTextEdit(self)
        self.description_input.setObjectName("caseDescriptionInput")
        self.description_input.setPlaceholderText("Optional short description")
        self.description_input.setFixedHeight(84)
        form.addRow("Case title", self.title_input)
        form.addRow("Reference (optional)", self.reference_input)
        form.addRow("Short description (optional)", self.description_input)
        layout.addLayout(form)
        self.error = QLabel(self)
        self.error.setObjectName("createCaseError")
        self.error.setWordWrap(True)
        self.error.setStyleSheet("color: #a00000;")
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save, self)
        buttons.accepted.connect(self.submit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.title_input.setFocus()

    def submit(self) -> None:
        title = self.title_input.text()
        if not title.strip():
            self.error.setText("Enter a case title before saving.")
            self.title_input.setFocus()
            return
        try:
            self.matter = self._service.create_matter(
                title, reference=self.reference_input.text().strip() or None,
                description=self.description_input.toPlainText() or None,
            )
        except Exception:
            self.error.setText("The case could not be saved. Your entered information is still here; please try again.")
            return
        self.accept()


class CaseUpdateDialog(QDialog):
    """A normal plain-text editor for append-only case updates."""

    def __init__(self, service: MatterWorkspaceService, matter_id: str, sources: list[WorkspaceSource], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add case update")
        self.setObjectName("caseUpdateDialog")
        self.resize(680, 500)
        self._service = service
        self._matter_id = matter_id
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.update_type = QComboBox(self)
        self.update_type.setObjectName("updateTypeCombo")
        for choice in NARRATIVE_UPDATE_TYPE_CHOICES:
            self.update_type.addItem(choice.label, choice.value)
        self.correction_source = QComboBox(self)
        self.correction_source.setObjectName("correctionSourceCombo")
        self.correction_source.addItem("Select an earlier update", None)
        for source in sources:
            if source.text is not None:
                self.correction_source.addItem(
                    f'{_format_timestamp(source.created_at)} — {source.update_type_label} — "{source.excerpt}"',
                    source.identifier,
                )
        form.addRow("Update type", self.update_type)
        form.addRow("Earlier update", self.correction_source)
        layout.addLayout(form)
        self.correction_source.setEnabled(False)
        self.update_type.currentIndexChanged.connect(self._update_correction_availability)
        self.editor = QPlainTextEdit(self)
        self.editor.setObjectName("caseUpdateEditor")
        self.editor.setAccessibleName("Case update text")
        self.editor.setPlaceholderText("Enter the case update exactly as provided.")
        self.editor.setMinimumHeight(280)
        layout.addWidget(self.editor, 1)
        self.error = QLabel(self)
        self.error.setObjectName("caseUpdateError")
        self.error.setWordWrap(True)
        self.error.setStyleSheet("color: #a00000;")
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save, self)
        buttons.accepted.connect(self.submit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.editor.setFocus()

    def _update_correction_availability(self) -> None:
        is_correction = self.update_type.currentData() == "correction"
        self.correction_source.setEnabled(is_correction)
        if not is_correction:
            self.correction_source.setCurrentIndex(0)

    def submit(self) -> None:
        text = self.editor.toPlainText()
        update_type = self.update_type.currentData()
        correction_of_id = self.correction_source.currentData() if update_type == "correction" else None
        if not text.strip():
            self.error.setText("Enter a case update before saving.")
            self.editor.setFocus()
            return
        if update_type == "correction" and not correction_of_id:
            self.error.setText("Choose the earlier update this correction refers to.")
            self.correction_source.setFocus()
            return
        try:
            self.source = self._service.append_narrative_update(
                self._matter_id, text, update_type=update_type, correction_of_id=correction_of_id,
            )
        except Exception:
            self.error.setText("The update could not be saved. Your entered text is still here; please try again.")
            return
        self.accept()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.editor.setFocus(Qt.FocusReason.OtherFocusReason)


class MatterWorkspaceWidget(QWidget):
    """One matter at a time, with persistent identity and four workspace sections."""

    def __init__(
        self, service: MatterWorkspaceService, matter_id: str, *, on_cases: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("matterWorkspace")
        self.setAcceptDrops(True)
        self._service = service
        self._matter_id = matter_id
        self._on_cases = on_cases
        self._sources: list[WorkspaceSource] = []
        self._executor = QtBackgroundExecutor()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)

        header = QHBoxLayout()
        self.cases_button = QPushButton("All cases", self)
        self.cases_button.setObjectName("allCasesButton")
        self.cases_button.clicked.connect(on_cases)
        header.addWidget(self.cases_button)
        identity = QVBoxLayout()
        self.title = QLabel(self)
        self.title.setObjectName("matterTitle")
        self.title.setProperty("heading", True)
        self.reference = QLabel(self)
        self.reference.setObjectName("matterReference")
        identity.addWidget(self.title)
        identity.addWidget(self.reference)
        header.addLayout(identity, 1)
        self.add_update = QPushButton("Add case update", self)
        self.add_update.setObjectName("addCaseUpdateButton")
        self.add_update.setDefault(True)
        self.add_update.setAccessibleName("Add case update")
        self.add_update.clicked.connect(self.open_update_editor)
        self.add_files = QPushButton("Add files", self)
        self.add_files.setObjectName("addFilesButton")
        self.add_files.clicked.connect(self.choose_files)
        header.addWidget(self.add_update)
        header.addWidget(self.add_files)
        layout.addLayout(header)

        self.sections = QTabWidget(self)
        self.sections.setObjectName("workspaceSections")
        self.overview = self._placeholder("Overview", "This case is ready for updates. Recent updates appear in Sources.")
        self.sources_page = SourceDropSurface(self.submit_files, self)
        source_layout = QVBoxLayout(self.sources_page)
        source_layout.setContentsMargins(12, 12, 12, 12)
        self.source_list = QListWidget(self.sources_page)
        self.source_list.setObjectName("matterSourceList")
        self.source_list.setAccessibleName("Case sources and updates")
        self.source_list.currentItemChanged.connect(self.show_selected_source)
        source_layout.addWidget(self.source_list)
        self.organize_selected_source = QPushButton("Organize selected source", self.sources_page)
        self.organize_selected_source.setObjectName("organizeSelectedSourceButton")
        self.organize_selected_source.setAccessibleName("Organize selected source")
        self.organize_selected_source.setEnabled(False)
        self.organize_selected_source.clicked.connect(self.organize_current_source)
        source_layout.addWidget(self.organize_selected_source)
        self.source_state = QLabel("Drop TXT, DOCX, or PDF files here, or use Add files.", self.sources_page)
        self.source_state.setObjectName("sourceIngestionStatus")
        self.source_state.setWordWrap(True)
        source_layout.addWidget(self.source_state)
        self.preview = QPlainTextEdit(self.sources_page)
        self.preview.setObjectName("sourcePreview")
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("Select a text source to preview extracted content.")
        self.preview.setMinimumHeight(130)
        source_layout.addWidget(self.preview)
        self._pdf_document = QPdfDocument(self)
        self.pdf_preview = QPdfView(self.sources_page)
        self.pdf_preview.setObjectName("pdfSourcePreview")
        self.pdf_preview.setDocument(self._pdf_document)
        self.pdf_preview.setVisible(False)
        self.pdf_preview.setMinimumHeight(220)
        source_layout.addWidget(self.pdf_preview)
        page_actions = QHBoxLayout()
        self.pdf_page = QSpinBox(self.sources_page)
        self.pdf_page.setObjectName("pdfPageReference")
        self.pdf_page.setMinimum(1)
        self.pdf_page.setEnabled(False)
        self.open_pdf_page_button = QPushButton("Open page", self.sources_page)
        self.open_pdf_page_button.setObjectName("openPdfPageButton")
        self.open_pdf_page_button.setEnabled(False)
        self.open_pdf_page_button.clicked.connect(lambda: self.open_pdf_page(self.pdf_page.value()))
        page_actions.addWidget(QLabel("PDF page", self.sources_page))
        page_actions.addWidget(self.pdf_page)
        page_actions.addWidget(self.open_pdf_page_button)
        page_actions.addStretch(1)
        source_layout.addLayout(page_actions)
        self.open_original = QPushButton("Open original", self.sources_page)
        self.open_original.setObjectName("openOriginalButton")
        self.open_original.setEnabled(False)
        self.open_original.clicked.connect(self.open_selected_original)
        source_layout.addWidget(self.open_original)
        self.review = self._placeholder("Review", "Review items will appear here when available.")
        self.work = self._placeholder("Work", "Case work will appear here when available.")
        self.sections.addTab(self.overview, "Overview")
        self.sections.addTab(self.sources_page, "Sources")
        self.sections.addTab(self.review, "Review")
        self.sections.addTab(self.work, "Work")
        layout.addWidget(self.sections, 1)
        self.reload()

    def _placeholder(self, heading: str, message: str) -> QWidget:
        page = QWidget(self)
        page_layout = QVBoxLayout(page)
        title = QLabel(heading, page)
        title.setProperty("heading", True)
        body = QLabel(message, page)
        body.setWordWrap(True)
        page_layout.addWidget(title)
        page_layout.addWidget(body)
        page_layout.addStretch(1)
        return page

    def reload(self) -> None:
        matter = self._service.get_matter(self._matter_id)
        if matter is None:
            self._on_cases()
            return
        self.title.setText(matter.title)
        identity = [part for part in (matter.reference, matter.status_label) if part]
        self.reference.setText(" · ".join(identity))
        self._sources = self._service.list_sources(self._matter_id)
        self.source_list.clear()
        source_by_id = {source.identifier: source for source in self._sources}
        for source in self._sources:
            label = f"{_format_timestamp(source.created_at)} — {source.update_type_label}"
            if source.correction_of_id in source_by_id:
                target = source_by_id[source.correction_of_id]
                label += f' (refers to {_format_timestamp(target.created_at)} — {target.update_type_label} — "{target.excerpt}")'
            if source.text:
                label += f"\n{source.text}"
            else:
                label += f" — {source.filename or 'Document'} [{source.ingestion_status}]"
            if source.duplicate_of_id:
                label += " (duplicate content already exists in this case)"
            notice = _extraction_notice_kind(source)
            if notice == "needs_ocr":
                label += " (no extractable text; needs OCR)"
            elif notice == "no_text":
                label += " (no extractable text; review the original document)"
            elif notice == "incomplete":
                label += " (extracted text is incomplete; review or reprocess before use)"
            if source.error_summary:
                label += f"\n{source.error_summary}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, source.identifier)
            item.setToolTip(label)
            self.source_list.addItem(item)

    def choose_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Add source files", "", "Documents (*.txt *.docx *.pdf)")
        self.submit_files(paths)

    def submit_files(self, paths: list[str]) -> None:
        for path in paths:
            self._submit_file(path)

    def _submit_file(self, path: str) -> None:
        self.source_state.setText("Registering and extracting document…")
        handle = self._executor.submit(DocumentIngestionTask(self._service, self._matter_id, path))
        handle.signals.progress.connect(lambda event: self.source_state.setText(event.message))
        handle.signals.completed.connect(self._ingestion_finished)
        handle.signals.failed.connect(lambda failure: self.source_state.setText(str(failure)))

    def _ingestion_finished(self, result: object) -> None:
        status = getattr(result, "status", "ready")
        duplicate = getattr(result, "duplicate_of_id", None)
        message = "Document imported" if status == "ready" else f"Document status: {status}"
        if duplicate:
            message += "; duplicate content already exists in this case"
        self.source_state.setText(message)
        self.reload()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        self.submit_files([url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()])
        event.acceptProposedAction()

    def show_selected_source(self, item: QListWidgetItem | None) -> None:
        source = next((entry for entry in self._sources if item and entry.identifier == item.data(Qt.ItemDataRole.UserRole)), None)
        if source is None:
            self.preview.clear()
            self.pdf_preview.setVisible(False)
            self.pdf_page.setEnabled(False)
            self.open_pdf_page_button.setEnabled(False)
            self.open_original.setEnabled(False)
            self.organize_selected_source.setEnabled(False)
            return
        self.organize_selected_source.setEnabled(True)
        self.open_original.setEnabled(source.original_path is not None)
        if source.text is not None:
            self.pdf_preview.setVisible(False)
            self.pdf_page.setEnabled(False)
            self.open_pdf_page_button.setEnabled(False)
            self.preview.setPlainText(_source_preview_message(source, source.text))
        elif source.media_type == "application/pdf":
            self.pdf_preview.setVisible(bool(source.original_path))
            pages = [block.page for block in source.blocks if block.page is not None]
            self.pdf_page.setRange(1, max(pages, default=1))
            self.pdf_page.setValue(min(pages, default=1))
            self.pdf_page.setEnabled(bool(source.original_path))
            self.open_pdf_page_button.setEnabled(bool(source.original_path))
            if source.original_path:
                self._pdf_document.load(source.original_path)
            preview = "\n\n".join(f"Page {block.page}:\n{block.text}" for block in source.blocks)
            self.preview.setPlainText(_source_preview_message(source, preview))
        else:
            self.pdf_preview.setVisible(False)
            self.pdf_page.setEnabled(False)
            self.open_pdf_page_button.setEnabled(False)
            self.preview.setPlainText(_source_preview_message(source, "\n\n".join(block.text for block in source.blocks)))

    def open_pdf_page(self, page: int) -> None:
        """Navigate a one-based source page reference in the embedded PDF viewer."""
        if page < 1:
            raise ValueError("PDF page references are one-based")
        self.pdf_preview.pageNavigator().jump(page - 1, QPointF(), 0)

    def open_selected_original(self) -> None:
        item = self.source_list.currentItem()
        source = next((entry for entry in self._sources if item and entry.identifier == item.data(Qt.ItemDataRole.UserRole)), None)
        if source and source.original_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(source.original_path))

    def organize_current_source(self) -> None:
        item = self.source_list.currentItem()
        source_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not source_id:
            return
        self.organize_selected_source.setEnabled(False)
        self.source_state.setText("Organizing selected source…")
        handle = self._executor.submit(StructuredGenerationTask(self._service, self._matter_id, source_id))
        handle.signals.progress.connect(lambda event: self.source_state.setText(event.message))
        handle.signals.completed.connect(self._generation_finished)
        handle.signals.failed.connect(self._generation_failed)

    def _generation_finished(self, result: object) -> None:
        self.source_state.setText(f"Organized update ready: {getattr(result, 'summary', '')}")
        self.reload()

    def _generation_failed(self, failure: object) -> None:
        self.source_state.setText(str(failure))
        self.organize_selected_source.setEnabled(self.source_list.currentItem() is not None)

    def open_update_editor(self) -> None:
        dialog = CaseUpdateDialog(self._service, self._matter_id, self._sources, self)
        self.update_dialog = dialog
        dialog.finished.connect(lambda result: self.reload() if result == QDialog.DialogCode.Accepted else None)
        dialog.open()
        QTimer.singleShot(0, lambda: dialog.editor.setFocus(Qt.FocusReason.OtherFocusReason))
