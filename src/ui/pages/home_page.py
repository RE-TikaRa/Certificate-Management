from __future__ import annotations

from PySide6.QtCore import Qt, QByteArray
from PySide6.QtWidgets import QLabel, QVBoxLayout
from PySide6.QtSvgWidgets import QSvgWidget

from .base_page import BasePage
from ...config import BASE_DIR
from ..styled_theme import ThemeManager


class HomePage(BasePage):
    ASPECT_RATIO = 170 / 100

    def __init__(self, ctx, theme_manager: ThemeManager):
        super().__init__(ctx, theme_manager)
        layout = QVBoxLayout(self)
        layout.addStretch()

        widget: QLabel | QSvgWidget
        logo_path = (BASE_DIR / "img" / "LOGO.svg").resolve()
        if logo_path.exists():
            svg_widget = QSvgWidget()
            try:
                data = logo_path.read_bytes()
                svg_widget.load(QByteArray(data))
            except Exception:
                svg_widget.load(str(logo_path))
            self.svg_widget = svg_widget
            self._update_logo_size()
            widget = svg_widget
        else:
            label = QLabel("Certificate Manager")
            label.setProperty("h1", True)
            widget = label
        layout.addWidget(widget, alignment=Qt.AlignCenter)
        self.logo = widget
        layout.addStretch()

    def refresh(self) -> None:
        pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_logo_size()

    def _update_logo_size(self) -> None:
        svg_widget = getattr(self, "svg_widget", None)
        if not isinstance(svg_widget, QSvgWidget):
            return
        available_width = max(200, int(self.width() * 0.35))
        width = available_width
        height = int(width / self.ASPECT_RATIO)
        max_height = max(150, int(self.height() * 0.35))
        if height > max_height:
            height = max_height
            width = int(height * self.ASPECT_RATIO)
        svg_widget.setFixedSize(width, height)
