"""
学校搜索自动完成组件。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QVBoxLayout, QWidget
from qfluentwidgets import LineEdit
from shiboken6 import isValid

from src.services.school_service import SchoolService
from src.ui.styled_theme import ThemeManager
from src.ui.utils.async_utils import run_in_thread


class SchoolSearchWidget(QWidget):
    schoolSelected = Signal(str, str)

    def __init__(self, school_service: SchoolService, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.school_service = school_service
        self.theme_manager = theme_manager
        self._selected_code: str | None = None
        self._region: str | None = None
        self._pending_text = ""
        self._search_seq = 0
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(200)
        self._debounce_timer.timeout.connect(self._perform_search)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.input = LineEdit()
        self.input.setPlaceholderText("输入学校名称或代码...")
        self.input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.input)

        self.results = QListWidget()
        self.results.setVisible(False)
        self.results.setMaximumHeight(160)
        self.results.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.results)

        self._apply_theme()
        self.theme_manager.themeChanged.connect(self._apply_theme)

    def _apply_theme(self) -> None:
        if self.theme_manager.is_dark:
            style = """
                QListWidget { background-color: #2a2a3a; color: #e0e0e0; border: 1px solid #4a4a5e; border-radius: 4px; }
                QListWidget::item { padding: 8px 10px; }
                QListWidget::item:hover { background-color: #3a3a4a; }
                QListWidget::item:selected { background-color: #5a80f3; color: white; }
            """
        else:
            style = """
                QListWidget { background-color: #ffffff; color: #333; border: 1px solid #ddd; border-radius: 4px; }
                QListWidget::item { padding: 8px 10px; }
                QListWidget::item:hover { background-color: #f5f5f5; }
                QListWidget::item:selected { background-color: #1890ff; color: white; }
            """
        self.results.setStyleSheet(style)

    def _on_text_changed(self, text: str) -> None:
        text = text.strip()
        self._pending_text = text
        self._selected_code = None
        if not text:
            self.results.setVisible(False)
            self._debounce_timer.stop()
            return
        self._debounce_timer.start()

    def _perform_search(self) -> None:
        text = self._pending_text
        if not text:
            self.results.setVisible(False)
            return

        self._search_seq += 1
        seq = self._search_seq
        query = text
        region = self._region

        def task():
            return self.school_service.search(query, limit=8, region=region)

        def on_done(result) -> None:
            if seq != self._search_seq:
                return
            if not isValid(self):
                return
            if query != self._pending_text:
                return
            if isinstance(result, Exception):
                self.results.setVisible(False)
                return
            schools = result
            if not schools:
                self.results.setVisible(False)
                return

            self.results.clear()
            for school in schools:
                display = school.name
                if school.code:
                    display = f"{school.name}（{school.code}）"
                item = QListWidgetItem(display)
                item.setData(Qt.ItemDataRole.UserRole, school.name)
                item.setData(Qt.ItemDataRole.UserRole + 1, school.code or "")
                self.results.addItem(item)
            self.results.setVisible(True)

        run_in_thread(task, on_done)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        name = item.data(Qt.ItemDataRole.UserRole)
        code = item.data(Qt.ItemDataRole.UserRole + 1) or ""
        self._selected_code = code or None
        self.input.blockSignals(True)
        self.input.setText(name)
        self.input.blockSignals(False)
        self._debounce_timer.stop()
        self.results.setVisible(False)
        self.schoolSelected.emit(name, code)

    def set_school(self, name: str, code: str | None = None) -> None:
        self.input.blockSignals(True)
        self.input.setText(name or "")
        self.input.blockSignals(False)
        self._pending_text = name or ""
        self._debounce_timer.stop()
        self._selected_code = code

    def text(self) -> str:
        return self.input.text()

    def selected_code(self) -> str | None:
        return self._selected_code

    def set_region_filter(self, region: str | None) -> None:
        self._region = region or None
        # 更换区域后清空当前结果，避免跨区数据混淆
        self.clear()

    def clear(self) -> None:
        self.input.blockSignals(True)
        self.input.clear()
        self.input.blockSignals(False)
        self.results.clear()
        self.results.setVisible(False)
        self._selected_code = None
        self._pending_text = ""
        self._debounce_timer.stop()
