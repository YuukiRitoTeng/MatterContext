"""Desktop startup and bounded smoke-test entry point."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from matter_context.ai import ProviderError, provider_from_environment
from matter_context.application.cases import PersistedCasesService, PersistedMatterWorkspaceService
from matter_context.application.generation import StructuredGenerationService
from matter_context.application.runtime_paths import RuntimePaths
from matter_context.storage.attachments import AttachmentStore
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
    paths = RuntimePaths.for_current_platform()
    database = database_for_runtime_paths(paths)
    factory = lambda: SqlAlchemyUnitOfWork(database.session_factory)
    return MainWindow(
        CasesViewModel(PersistedCasesService(factory)),
        PersistedMatterWorkspaceService(factory, AttachmentStore(paths.attachments), StructuredGenerationService(factory, provider_from_environment())),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="matter-context")
    parser.add_argument("--smoke-test", action="store_true", help="Start the desktop shell and exit promptly.")
    parser.add_argument("--check-model-connection", action="store_true", help="Check configured model access without matter data.")
    arguments = parser.parse_args(argv)

    if arguments.check_model_connection:
        try:
            StructuredGenerationService(lambda: (_ for _ in ()).throw(RuntimeError("not used")), provider_from_environment()).check_connection()
        except ProviderError as error:
            print(f"Model connection check failed: {error}", file=sys.stderr)
            return 1
        except ValueError:
            print("Model connection check failed: invalid structured response.", file=sys.stderr)
            return 1
        print("Model connection check succeeded.")
        return 0

    app = create_application()
    window = create_main_window()
    window.show()
    if arguments.smoke_test:
        QTimer.singleShot(100, app.quit)
    return app.exec()
