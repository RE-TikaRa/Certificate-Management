import logging
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

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
        try:
            result = self.func()
        except Exception as exc:
            logger.exception("Async task failed: %s", exc)
            return
        # Emit from worker thread; Qt delivers to connected slot in GUI thread
        self.invoker.finished.emit(result)


def run_in_thread(func: Callable[[], Any], on_done: Callable[[Any], None]) -> None:
    """
    Run func in Qt thread pool, then invoke on_done in the GUI thread with the result.
    """
    worker = _Worker(func, on_done)
    QThreadPool.globalInstance().start(worker)
