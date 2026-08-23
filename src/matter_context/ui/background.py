"""Qt adapter for the framework-independent execution contracts."""

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal

from matter_context.execution.tasks import (
    BackgroundTask,
    CancellationToken,
    TaskCancelled,
    TaskFailure,
    TaskProgress,
    TaskResult,
)


class TaskSignals(QObject):
    progress = Signal(object)
    completed = Signal(object)
    cancelled = Signal(object)
    failed = Signal(object)


class TaskHandle:
    """Owns cancellation and signals for a submitted task."""

    def __init__(self) -> None:
        self.cancellation = CancellationToken()
        self.signals = TaskSignals()

    def cancel(self) -> None:
        self.cancellation.cancel()


class _TaskRunnable(QRunnable):
    def __init__(self, task: BackgroundTask, handle: TaskHandle) -> None:
        super().__init__()
        self._task = task
        self._handle = handle

    def run(self) -> None:
        try:
            result = self._task.run(self._handle.cancellation, self._emit_progress)
        except TaskCancelled:
            self._handle.signals.cancelled.emit(TaskResult("Task cancelled"))
        except TaskFailure as failure:
            self._handle.signals.failed.emit(failure)
        except Exception:
            self._handle.signals.failed.emit(TaskFailure("Background task failed"))
        else:
            self._handle.signals.completed.emit(result)

    def _emit_progress(self, progress: TaskProgress) -> None:
        self._handle.signals.progress.emit(progress)


class QtBackgroundExecutor:
    """Submit internal work without blocking the Qt event loop."""

    def __init__(self, thread_pool: QThreadPool | None = None) -> None:
        self._thread_pool = thread_pool or QThreadPool.globalInstance()

    def submit(self, task: BackgroundTask) -> TaskHandle:
        handle = TaskHandle()
        runnable = _TaskRunnable(task, handle)
        QTimer.singleShot(0, lambda: self._thread_pool.start(runnable))
        return handle
