"""
专业搜索自动完成组件
提供模糊搜索和一键填充功能
"""

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import LineEdit

from src.services.major_service import MajorService
from src.ui.styled_theme import ThemeManager


class MajorSearchWidget(QWidget):
    """专业搜索自动完成组件"""

    # 信号：当选择专业时触发 (名称, 代码, 学院)
    majorSelected = Signal(str, str, str)

    MIN_QUERY_LENGTH = 2

    def __init__(self, major_service: MajorService, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.major_service = major_service
        self.theme_manager = theme_manager
        self._school_code: str | None = None
        self._school_name: str | None = None
        self._selected_code: str | None = None
        self._selected_college: str | None = None
        self._pending_text = ""
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(200)
        self._debounce_timer.timeout.connect(self._perform_search)
        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 输入框 - 使用 Fluent LineEdit
        self.input = LineEdit()
        self.input.setPlaceholderText("输入专业名称/代码...")
        self.input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.input)

        # 搜索结果列表
        self.results_list = QListWidget()
        self.results_list.setVisible(False)
        self.results_list.setMaximumHeight(150)
        self.results_list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.results_list)

        # 应用主题（仅针对列表，LineEdit 已是 Fluent 组件）
        self._apply_theme()
        self.theme_manager.themeChanged.connect(self._apply_theme)

    def _apply_theme(self):
        """应用主题样式（仅列表，LineEdit 使用 Fluent 自带样式）"""
        is_dark = self.theme_manager.is_dark

        if is_dark:
            list_style = """
                QListWidget {
                    background-color: #2a2a3a;
                    color: #e0e0e0;
                    border: 1px solid #4a4a5e;
                    border-radius: 4px;
                    outline: none;
                }
                QListWidget::item {
                    padding: 8px 12px;
                    border-bottom: 1px solid #3a3a4a;
                }
                QListWidget::item:hover {
                    background-color: #3a3a4a;
                }
                QListWidget::item:selected {
                    background-color: #5a80f3;
                    color: white;
                }
            """
        else:
            list_style = """
                QListWidget {
                    background-color: white;
                    color: #333;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    outline: none;
                }
                QListWidget::item {
                    padding: 8px 12px;
                    border-bottom: 1px solid #f0f0f0;
                }
                QListWidget::item:hover {
                    background-color: #f5f5f5;
                }
                QListWidget::item:selected {
                    background-color: #1890ff;
                    color: white;
                }
            """

        self.results_list.setStyleSheet(list_style)

    def _on_text_changed(self, text: str):
        """输入框文本变化时搜索"""
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
        majors = self.major_service.search_majors(
            text,
            limit=8,
            school_code=self._school_code,
            school_name=self._school_name,
        )

        if not majors:
            self.results_list.setVisible(False)
            return

        # 显示搜索结果
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

    def _on_item_clicked(self, item: QListWidgetItem):
        """点击搜索结果项"""
        major_name = item.data(Qt.ItemDataRole.UserRole)
        major_code = item.data(Qt.ItemDataRole.UserRole + 1) or ""
        college = item.data(Qt.ItemDataRole.UserRole + 2) or ""

        self._selected_code = major_code or None
        self._selected_college = college or None

        # 填充输入框
        self.input.blockSignals(True)
        self.input.setText(major_name)
        self.input.blockSignals(False)
        self._debounce_timer.stop()

        # 隐藏搜索结果
        self.results_list.setVisible(False)

        # 发送信号
        self.majorSelected.emit(major_name, major_code, college)

    def set_text(self, text: str):
        """设置输入框文本"""
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
        """获取输入框文本"""
        return self.input.text()

    def set_school_filter(self, *, name: str | None = None, code: str | None = None) -> None:
        self._school_name = name
        self._school_code = code

    def selected_code(self) -> str | None:
        return self._selected_code

    def selected_college(self) -> str | None:
        return self._selected_college

    def clear(self):
        """清空输入框和搜索结果"""
        self.input.clear()
        self.results_list.clear()
        self.results_list.setVisible(False)
        self._selected_code = None
        self._selected_college = None
        self._pending_text = ""
        self._debounce_timer.stop()
