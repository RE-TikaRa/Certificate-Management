from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget

from ..theme import PAGE_STYLE

if TYPE_CHECKING:
    from ...app_context import AppContext


class BasePage(QWidget):
    def __init__(self, ctx: "AppContext"):
        super().__init__()
        self.ctx = ctx
        self.setObjectName("pageRoot")
        self.setStyleSheet(PAGE_STYLE)

    def refresh(self) -> None:  # pragma: no cover - optional override
        pass
