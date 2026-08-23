"""The single top-level MatterContext window."""

from PySide6.QtWidgets import QDialog, QMainWindow

from matter_context.application.cases import MatterWorkspaceService
from matter_context.ui.cases import CasesViewModel, CasesWidget
from matter_context.ui.workspace import CreateCaseDialog, MatterWorkspaceWidget


class MainWindow(QMainWindow):
    def __init__(self, cases_view_model: CasesViewModel, workspace_service: MatterWorkspaceService | None = None) -> None:
        super().__init__()
        self.setObjectName("matterContextMainWindow")
        self.setWindowTitle("MatterContext")
        self.resize(960, 640)
        self._workspace_service = workspace_service
        self._cases = CasesWidget(
            cases_view_model,
            on_create=self.open_create_case if workspace_service else None,
            on_open=self.open_matter if workspace_service else None,
            parent=self,
        )
        self.setCentralWidget(self._cases)

    def show_cases(self) -> None:
        self._cases.refresh()
        current = self.takeCentralWidget()
        if current is not None and current is not self._cases:
            current.deleteLater()
        self.setCentralWidget(self._cases)
        self._cases.primary_action.setFocus()

    def open_create_case(self) -> None:
        if self._workspace_service is None:
            return
        dialog = CreateCaseDialog(self._workspace_service, self)
        self.create_dialog = dialog
        dialog.finished.connect(self._created_case)
        dialog.open()

    def _created_case(self, result: int) -> None:
        if result == QDialog.DialogCode.Accepted:
            self.open_matter(self.create_dialog.matter.identifier)

    def open_matter(self, matter_id: str) -> None:
        if self._workspace_service is None:
            return
        current = self.takeCentralWidget()
        if current is not None and current is not self._cases:
            current.deleteLater()
        self._workspace = MatterWorkspaceWidget(
            self._workspace_service, matter_id, on_cases=self.show_cases, parent=self,
        )
        self.setCentralWidget(self._workspace)
        self._workspace.add_update.setFocus()
