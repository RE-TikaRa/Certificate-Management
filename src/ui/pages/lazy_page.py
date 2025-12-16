from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class LazyPage(QWidget):
    content_widget: QWidget | None = None

    def __init__(self, factory: Callable[[], QWidget], *, placeholder: str = "页面资源加载中…") -> None:
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._factory = factory
        self._page: QWidget | None = None

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self._placeholder_label = QLabel(placeholder)
        self._placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder_label.setStyleSheet("color: #7a7a7a;")
        self._layout.addWidget(self._placeholder_label)
        self.content_widget = self

    def _ensure_loaded(self) -> QWidget:
        if self._page is not None:
            return self._page

        page = self._factory()
        self._page = page
        if self._placeholder_label is not None:
            self._layout.removeWidget(self._placeholder_label)
            self._placeholder_label.deleteLater()
            self._placeholder_label = None
        self._layout.addWidget(page)
        self.content_widget = getattr(page, "content_widget", page)
        return page

    def refresh(self) -> None:
        page: Any = self._ensure_loaded()
        if hasattr(page, "refresh"):
            page.refresh()
