from pathlib import Path
from threading import Event

from matter_context.execution.tasks import (
    CancellationToken,
    DocumentIngestionTask,
    FakeTask,
    FakeTaskMode,
    TaskCancelled,
    TaskFailure,
)
from matter_context.application.ingestion import IngestionResult
from matter_context.application.cases import PersistedMatterWorkspaceService
from matter_context.application.matters import MatterService
from matter_context.domain import IngestionStatus
from matter_context.storage.attachments import AttachmentStore
from matter_context.storage.database import Database, upgrade_database
from matter_context.storage.unit_of_work import SqlAlchemyUnitOfWork
from PySide6.QtCore import QTimer
from matter_context.ui.background import QtBackgroundExecutor


def test_fake_task_reports_progress_and_success() -> None:
    progress = []

    result = FakeTask(steps=2, step_delay_seconds=0).run(CancellationToken(), progress.append)

    assert result.message == "Fake task completed"
    assert [event.completed for event in progress] == [1, 2]


def test_fake_task_reports_typed_failure() -> None:
    try:
        FakeTask(mode=FakeTaskMode.FAILURE, step_delay_seconds=0).run(CancellationToken(), lambda _event: None)
    except TaskFailure as error:
        assert str(error) == "Fake task failed"
    else:
        raise AssertionError("FakeTask failure mode must raise TaskFailure")


def test_fake_task_honors_cancellation() -> None:
    cancellation = CancellationToken()
    cancellation.cancel()

    try:
        FakeTask(step_delay_seconds=0).run(cancellation, lambda _event: None)
    except TaskCancelled:
        pass
    else:
        raise AssertionError("Cancelled FakeTask must not complete")


def test_qt_executor_remains_responsive_while_event_loop_processes_events(qtbot) -> None:
    executor = QtBackgroundExecutor()
    handle = executor.submit(FakeTask(steps=3, step_delay_seconds=0.02))
    ticks = []
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(True))
    timer.start(1)

    with qtbot.waitSignal(handle.signals.completed, timeout=1500) as completed:
        qtbot.wait(10)

    timer.stop()
    assert completed.args[0].message == "Fake task completed"
    assert ticks


def test_qt_executor_emits_failure_and_cancellation(qtbot) -> None:
    executor = QtBackgroundExecutor()
    failed = executor.submit(FakeTask(mode=FakeTaskMode.FAILURE, step_delay_seconds=0))
    with qtbot.waitSignal(failed.signals.failed, timeout=1000) as failure:
        pass
    assert isinstance(failure.args[0], TaskFailure)

    cancelled = executor.submit(FakeTask(steps=50, step_delay_seconds=0.01))
    cancelled.cancel()
    with qtbot.waitSignal(cancelled.signals.cancelled, timeout=1000) as event:
        pass
    assert event.args[0].message == "Task cancelled"


def test_document_ingestion_task_reports_registration_and_extraction_transitions() -> None:
    class Service:
        def ingest_document(self, matter_id: str, file_path: str, *, on_registered) -> IngestionResult:
            assert (matter_id, file_path) == ("matter", "/tmp/evidence.txt")
            on_registered(IngestionResult("source", "run", IngestionStatus.PROCESSING))
            return IngestionResult("source", "run", IngestionStatus.READY)

    progress = []
    result = DocumentIngestionTask(Service(), "matter", "/tmp/evidence.txt").run(CancellationToken(), progress.append)

    assert [event.message for event in progress] == ["Original registered; extracting document", "Extraction complete"]
    assert (result.source_id, result.run_id, result.status) == ("source", "run", "ready")


def test_real_background_ingestion_persists_running_to_terminal_transition(qtbot, monkeypatch, tmp_path: Path) -> None:
    database = Database.from_url(f"sqlite:///{tmp_path / 'background.sqlite3'}")
    upgrade_database(str(database.engine.url))
    factory = lambda: SqlAlchemyUnitOfWork(database.session_factory)
    workspace = PersistedMatterWorkspaceService(factory, AttachmentStore(tmp_path / "attachments"))
    matter = MatterService(factory).create_matter("Background import")
    document = tmp_path / "evidence.txt"
    document.write_text("background document", encoding="utf-8")
    extraction_started = Event()
    allow_extraction = Event()
    from matter_context.application import ingestion

    original_extract = ingestion.extract_document

    def delayed_extract(path, media_type):
        extraction_started.set()
        assert allow_extraction.wait(2)
        return original_extract(path, media_type)

    monkeypatch.setattr(ingestion, "extract_document", delayed_extract)
    executor = QtBackgroundExecutor()
    handle = executor.submit(DocumentIngestionTask(workspace, matter.identifier, str(document)))
    with qtbot.waitSignal(handle.signals.progress, timeout=1500) as progress:
        pass
    assert progress.args[0].message == "Original registered; extracting document"
    assert extraction_started.wait(1)
    with factory() as uow:
        source = uow.sources.list_for_matter(matter.identifier)[0]
        run = uow.processing_runs.latest_for_source(source.identifier)
    assert str(source.ingestion_status) == "processing"
    assert str(source.extraction_status) == "running"
    assert run and run.status.value == "running"

    allow_extraction.set()
    with qtbot.waitSignal(handle.signals.completed, timeout=1500) as completed:
        pass
    with factory() as uow:
        source = uow.sources.get(completed.args[0].source_id)
        run = uow.processing_runs.get(completed.args[0].run_id)
    assert source and str(source.ingestion_status) == "ready" and str(source.extraction_status) == "extracted"
    assert run and run.status.value == "succeeded" and run.completed_at is not None
