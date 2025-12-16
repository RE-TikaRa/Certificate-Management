from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CaptionLabel, IndeterminateProgressRing


class LazyPage(QWidget):
    content_widget: QWidget | None = None

    def __init__(
        self,
        factory: Callable[[], QWidget],
        *,
        placeholder: str = "页面资源加载中…",
        detail: str = "启动软件过程中可能会稍慢",
    ) -> None:
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._factory = factory
        self._page: QWidget | None = None

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self._placeholder = QWidget(self)
        self._placeholder.setObjectName("lazyPlaceholder")
        ph_layout = QVBoxLayout(self._placeholder)
        ph_layout.setContentsMargins(24, 24, 24, 24)
        ph_layout.setSpacing(10)
        ph_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        ring = IndeterminateProgressRing(self._placeholder)
        ring.setFixedSize(36, 36)
        ph_layout.addWidget(ring, 0, Qt.AlignmentFlag.AlignHCenter)

        title = BodyLabel(placeholder, self._placeholder)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setWordWrap(True)
        ph_layout.addWidget(title, 0, Qt.AlignmentFlag.AlignHCenter)

        sub = CaptionLabel(detail, self._placeholder)
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        sub.setStyleSheet("color: #7a7a7a;")
        ph_layout.addWidget(sub, 0, Qt.AlignmentFlag.AlignHCenter)

        self._layout.addWidget(self._placeholder, 1)
        self.content_widget = self

    def _ensure_loaded(self) -> QWidget:
        if self._page is not None:
            return self._page

        page = self._factory()
        self._page = page
        if self._placeholder is not None:
            self._layout.removeWidget(self._placeholder)
            self._placeholder.deleteLater()
            self._placeholder = None
        self._layout.addWidget(page)
        self.content_widget = getattr(page, "content_widget", page)
        return page

    def load(self) -> QWidget:
        return self._ensure_loaded()

    def refresh(self) -> None:
        page: Any = self._ensure_loaded()
        if hasattr(page, "refresh"):
            page.refresh()
