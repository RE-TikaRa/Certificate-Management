import logging
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from shiboken6 import isValid

logger = logging.getLogger(__name__)


class _Invoker(QObject):
    finished = Signal(object)


class _Worker(QRunnable):
    def __init__(self, func: Callable[[], Any], callback: Callable[[Any], None]):
        super().__init__()
        self.func = func
        self.invoker = _Invoker()
        self.invoker.finished.connect(callback)

    def run(self) -> None:  # Runs in thread pool worker thread
        result: Any
        try:
            result = self.func()
        except Exception as exc:
            logger.exception("Async task failed: %s", exc)
            result = exc
        # Always emit so GUI thread can clean up state even when errors occur
        self.invoker.finished.emit(result)


_ACTIVE_WORKERS: set[_Worker] = set()


def run_in_thread(func: Callable[[], Any], on_done: Callable[[Any], None]) -> None:
    """
    Run func in Qt thread pool, then invoke on_done in the GUI thread with the result.
    """
    run_in_thread_guarded(func, on_done, guard=None)


def run_in_thread_guarded(func: Callable[[], Any], on_done: Callable[[Any], None], *, guard: QObject | None) -> None:
    """
    Like run_in_thread, but skips invoking on_done when guard is no longer valid.

    This avoids updating widgets that have been deleted while a background task is running.
    """

    def _wrapped(result: Any) -> None:
        try:
            if guard is not None and not isValid(guard):
                return
            on_done(result)
        finally:
            _ACTIVE_WORKERS.discard(worker)

    worker = _Worker(func, _wrapped)
    worker.setAutoDelete(False)
    _ACTIVE_WORKERS.add(worker)
    QThreadPool.globalInstance().start(worker)
