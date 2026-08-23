"""Desktop startup and bounded smoke-test entry point."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from matter_context.application.cases import PersistedCasesService
from matter_context.application.runtime_paths import RuntimePaths
from matter_context.storage import SqlAlchemyUnitOfWork, database_for_runtime_paths
from matter_context.ui.cases import CasesViewModel
from matter_context.ui.main_window import MainWindow


def create_application(argv: Sequence[str] | None = None) -> QApplication:
    """Create the sole QApplication, or return the existing test instance."""
    app = QApplication.instance()
    if app is not None:
        return app
    return QApplication(list(argv if argv is not None else sys.argv))


def create_main_window() -> MainWindow:
    database = database_for_runtime_paths(RuntimePaths.for_current_platform())
    return MainWindow(CasesViewModel(PersistedCasesService(
        lambda: SqlAlchemyUnitOfWork(database.session_factory),
    )))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="matter-context")
    parser.add_argument("--smoke-test", action="store_true", help="Start the desktop shell and exit promptly.")
    arguments = parser.parse_args(argv)

    app = create_application()
    window = create_main_window()
    window.show()
    if arguments.smoke_test:
        QTimer.singleShot(100, app.quit)
    return app.exec()
