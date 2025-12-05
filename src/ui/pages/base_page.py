from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

if TYPE_CHECKING:
    from ...app_context import AppContext
    from ..styled_theme import ThemeManager


class BasePage(QWidget):
    """页面基类"""

    content_widget: QWidget | None = None

    def __init__(self, ctx: AppContext, theme_manager: ThemeManager):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.ctx = ctx
        self.theme_manager = theme_manager

    def refresh(self) -> None:  # pragma: no cover - optional override
        pass
