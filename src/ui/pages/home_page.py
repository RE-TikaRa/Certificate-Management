from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import QLabel, QVBoxLayout

from ...config import BASE_DIR
from ..styled_theme import ThemeManager
from .base_page import BasePage


class HomePage(BasePage):
    ASPECT_RATIO = 170 / 100

    def __init__(self, ctx, theme_manager: ThemeManager):
        super().__init__(ctx, theme_manager)
        self.setObjectName("pageRoot")
        layout = QVBoxLayout(self)
        layout.addStretch()

        widget: QLabel | QSvgWidget
        logo_path = (BASE_DIR / "img" / "LOGO.svg").resolve()
        if logo_path.exists():
            svg_widget = QSvgWidget()
            try:
                self._logo_path = logo_path
                self._apply_logo_for_theme(svg_widget)
            except Exception:
                svg_widget.load(str(logo_path))
            self.svg_widget = svg_widget
            self._update_logo_size()
            widget = svg_widget
            self.theme_manager.themeChanged.connect(self._on_theme_changed)
        else:
            label = QLabel("Certificate Manager")
            label.setProperty("h1", True)
            widget = label
        layout.addWidget(widget, alignment=Qt.AlignmentFlag.AlignCenter)
        self.logo = widget
        layout.addStretch()

    def refresh(self) -> None:
        pass

    def _apply_logo_for_theme(self, svg_widget: QSvgWidget) -> None:
        data = self._logo_path.read_bytes()
        if self.theme_manager.is_dark:
            data = data.replace(b'fill="#000000"', b'fill="#FFFFFF"')
        svg_widget.load(QByteArray(data))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_logo_size()

    def _on_theme_changed(self) -> None:
        svg_widget = getattr(self, "svg_widget", None)
        if isinstance(svg_widget, QSvgWidget):
            self._apply_logo_for_theme(svg_widget)

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
