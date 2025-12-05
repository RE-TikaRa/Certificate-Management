from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

if TYPE_CHECKING:
    from ...app_context import AppContext
    from ..styled_theme import ThemeManager


class BasePage(QWidget):
    def __init__(self, ctx: AppContext, theme_manager: ThemeManager = None):
        super().__init__()
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.ctx = ctx
        self.theme_manager = theme_manager

    def refresh(self) -> None:  # pragma: no cover - optional override
        pass
