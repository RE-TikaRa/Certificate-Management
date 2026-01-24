"""
专业搜索自动完成组件
提供模糊搜索和一键填充功能
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QListWidgetItem, QVBoxLayout, QWidget
from qfluentwidgets import LineEdit, ListWidget
from shiboken6 import isValid

from src.services.major_service import MajorService
from src.ui.utils.async_utils import run_in_thread


class MajorSearchWidget(QWidget):
    """专业搜索自动完成组件"""

    # 信号：当选择专业时触发 (名称, 代码, 学院)
    majorSelected = Signal(str, str, str)

    MIN_QUERY_LENGTH = 2

    def __init__(self, major_service: MajorService, theme_manager, parent=None):
        super().__init__(parent)
        self.major_service = major_service
        self._school_code: str | None = None
        self._school_name: str | None = None
        self._selected_code: str | None = None
        self._selected_college: str | None = None
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
        self.input.setPlaceholderText("输入专业名称/代码...")
        self.input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.input)

        self.results_list = ListWidget()
        self.results_list.setVisible(False)
        self.results_list.setMaximumHeight(150)
        self.results_list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.results_list)

    def _on_text_changed(self, text: str) -> None:
        cleaned = text.strip()
        self._pending_text = cleaned
        self._selected_code = None
        self._selected_college = None
        if not cleaned:
            self.results_list.setVisible(False)
            self._debounce_timer.stop()
            return
        self._debounce_timer.start()

    def _perform_search(self) -> None:
        text = self._pending_text
        if not text:
            self.results_list.setVisible(False)
            return
        if len(text) < self.MIN_QUERY_LENGTH and not text.isdigit():
            self.results_list.setVisible(False)
            return
        self._search_seq += 1
        seq = self._search_seq
        query = text
        school_code = self._school_code
        school_name = self._school_name

        def task():
            return self.major_service.search_majors(
                query,
                limit=8,
                school_code=school_code,
                school_name=school_name,
            )

        def on_done(result) -> None:
            if seq != self._search_seq:
                return
            if not isValid(self):
                return
            if query != self._pending_text:
                return
            if isinstance(result, Exception):
                self.results_list.setVisible(False)
                return
            majors = result
            if not majors:
                self.results_list.setVisible(False)
                return

            self.results_list.clear()
            for major in majors:
                display = major.name
                if major.code:
                    display = f"{major.name}（{major.code}）"
                if major.college:
                    display = f"{display} - {major.college}"
                item = QListWidgetItem(display)
                item.setData(Qt.ItemDataRole.UserRole, major.name)
                item.setData(Qt.ItemDataRole.UserRole + 1, major.code or "")
                item.setData(Qt.ItemDataRole.UserRole + 2, major.college or "")
                self.results_list.addItem(item)

            self.results_list.setVisible(True)

        run_in_thread(task, on_done)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        major_name = item.data(Qt.ItemDataRole.UserRole)
        major_code = item.data(Qt.ItemDataRole.UserRole + 1) or ""
        college = item.data(Qt.ItemDataRole.UserRole + 2) or ""

        self._selected_code = major_code or None
        self._selected_college = college or None

        self.input.blockSignals(True)
        self.input.setText(major_name)
        self.input.blockSignals(False)
        self._debounce_timer.stop()
        self.results_list.setVisible(False)
        self.majorSelected.emit(major_name, major_code, college)

    def set_text(self, text: str) -> None:
        self.input.blockSignals(True)
        self.input.setText(text)
        self.input.blockSignals(False)
        if not text:
            self._selected_code = None
            self._selected_college = None
            self.results_list.setVisible(False)
            self._debounce_timer.stop()
        else:
            self._pending_text = text.strip()

    def text(self) -> str:
        return self.input.text()

    def set_school_filter(self, *, name: str | None = None, code: str | None = None) -> None:
        self._school_name = name
        self._school_code = code

    def selected_code(self) -> str | None:
        return self._selected_code

    def selected_college(self) -> str | None:
        return self._selected_college

    def clear(self) -> None:
        self.input.clear()
        self.results_list.clear()
        self.results_list.setVisible(False)
        self._selected_code = None
        self._selected_college = None
        self._pending_text = ""
        self._debounce_timer.stop()
