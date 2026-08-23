"""The single top-level MatterContext window."""

from PySide6.QtWidgets import QMainWindow

from matter_context.ui.cases import CasesViewModel, CasesWidget


class MainWindow(QMainWindow):
    def __init__(self, cases_view_model: CasesViewModel) -> None:
        super().__init__()
        self.setObjectName("matterContextMainWindow")
        self.setWindowTitle("MatterContext")
        self.resize(960, 640)
        self.setCentralWidget(CasesWidget(cases_view_model, self))
