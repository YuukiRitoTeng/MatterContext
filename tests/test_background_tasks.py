from matter_context.execution.tasks import (
    CancellationToken,
    FakeTask,
    FakeTaskMode,
    TaskCancelled,
    TaskFailure,
)
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


def test_qt_executor_completes_while_event_loop_processes_events(qtbot) -> None:
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
