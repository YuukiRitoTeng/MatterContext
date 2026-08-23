"""Qt-independent contracts for cancellable background work."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from threading import Event
from time import sleep
from typing import Protocol


@dataclass(frozen=True, slots=True)
class TaskProgress:
    completed: int
    total: int
    message: str


@dataclass(frozen=True, slots=True)
class TaskResult:
    message: str


class TaskFailure(Exception):
    """Sanitized failure returned through the execution boundary."""


class TaskCancelled(Exception):
    """Raised internally when cooperative cancellation is requested."""


class CancellationToken:
    def __init__(self) -> None:
        self._cancelled = Event()

    def cancel(self) -> None:
        self._cancelled.set()

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled.is_set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled:
            raise TaskCancelled("Task cancelled")


ProgressReporter = Callable[[TaskProgress], None]


class BackgroundTask(Protocol):
    def run(self, cancellation: CancellationToken, report_progress: ProgressReporter) -> TaskResult:
        """Run a unit of work without Qt types."""


class FakeTaskMode(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"


@dataclass(frozen=True, slots=True)
class FakeTask:
    """Deterministic task used to exercise every execution outcome."""

    steps: int = 3
    mode: FakeTaskMode = FakeTaskMode.SUCCESS
    step_delay_seconds: float = 0.01

    def run(self, cancellation: CancellationToken, report_progress: ProgressReporter) -> TaskResult:
        if self.steps < 1:
            raise ValueError("steps must be at least one")
        for completed in range(1, self.steps + 1):
            cancellation.raise_if_cancelled()
            if self.step_delay_seconds:
                sleep(self.step_delay_seconds)
            cancellation.raise_if_cancelled()
            report_progress(TaskProgress(completed, self.steps, f"Step {completed} of {self.steps}"))
        if self.mode is FakeTaskMode.FAILURE:
            raise TaskFailure("Fake task failed")
        return TaskResult("Fake task completed")
