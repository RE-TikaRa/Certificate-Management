from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget

if TYPE_CHECKING:
    from ...app_context import AppContext


class BasePage(QWidget):
    def __init__(self, ctx: "AppContext"):
        super().__init__()
        self.ctx = ctx

    def refresh(self) -> None:  # pragma: no cover - optional override
        pass
