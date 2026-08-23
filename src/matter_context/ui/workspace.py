"""Single-window case workspace widgets backed only by application services."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton, QTabWidget,
    QVBoxLayout, QWidget,
)

from matter_context.application.cases import (
    NARRATIVE_UPDATE_TYPE_CHOICES, MatterWorkspaceService, WorkspaceSource,
)


def _format_timestamp(value: datetime) -> str:
    return value.astimezone().strftime("%Y-%m-%d %H:%M")


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
        self._service = service
        self._matter_id = matter_id
        self._on_cases = on_cases
        self._sources: list[WorkspaceSource] = []
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
        self.add_files.setEnabled(False)
        self.add_files.setToolTip("File import is not available yet.")
        header.addWidget(self.add_update)
        header.addWidget(self.add_files)
        layout.addLayout(header)

        self.sections = QTabWidget(self)
        self.sections.setObjectName("workspaceSections")
        self.overview = self._placeholder("Overview", "This case is ready for updates. Recent updates appear in Sources.")
        self.sources_page = QWidget(self)
        source_layout = QVBoxLayout(self.sources_page)
        source_layout.setContentsMargins(12, 12, 12, 12)
        self.source_list = QListWidget(self.sources_page)
        self.source_list.setObjectName("matterSourceList")
        self.source_list.setAccessibleName("Case sources and updates")
        source_layout.addWidget(self.source_list)
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
            if source.text is not None:
                label += f"\n{source.text}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, source.identifier)
            item.setToolTip(label)
            self.source_list.addItem(item)

    def open_update_editor(self) -> None:
        dialog = CaseUpdateDialog(self._service, self._matter_id, self._sources, self)
        self.update_dialog = dialog
        dialog.finished.connect(lambda result: self.reload() if result == QDialog.DialogCode.Accepted else None)
        dialog.open()
        QTimer.singleShot(0, lambda: dialog.editor.setFocus(Qt.FocusReason.OtherFocusReason))
