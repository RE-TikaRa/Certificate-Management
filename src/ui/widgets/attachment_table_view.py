from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import QTableView


class AttachmentTableView(QTableView):
    """QTableView that accepts file drops and emits resolved Path objects."""

    fileDropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setProperty("dragActive", False)
        self.setMouseTracking(True)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # pragma: no cover - UI event
        if self._has_valid_files(event.mimeData()):
            event.acceptProposedAction()
            self._set_drag_active(True)
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # pragma: no cover - UI event
        if self._has_valid_files(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # pragma: no cover - UI event
        files = self._extract_files(event.mimeData())
        if files:
            event.acceptProposedAction()
            self.fileDropped.emit(files)
        else:
            event.ignore()
        self._set_drag_active(False)

    def dragLeaveEvent(self, _event: QDragLeaveEvent) -> None:  # pragma: no cover - UI event
        self._set_drag_active(False)

    def _has_valid_files(self, mime_data: QMimeData) -> bool:
        if not mime_data.hasUrls():
            return False
        return any(url.isLocalFile() for url in mime_data.urls())

    def _extract_files(self, mime_data: QMimeData) -> list[Path]:
        paths: list[Path] = []
        for url in mime_data.urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile()).resolve()
            if path.exists():
                paths.append(path)
        return paths

    def _set_drag_active(self, active: bool) -> None:
        if self.property("dragActive") == active:
            return
        self.setProperty("dragActive", active)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
