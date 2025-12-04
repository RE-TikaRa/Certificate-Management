"""
专业搜索自动完成组件
提供模糊搜索和一键填充功能
"""
from typing import Callable, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import LineEdit

from src.data.models import Major
from src.services.major_service import MajorService
from src.ui.styled_theme import ThemeManager


class MajorSearchWidget(QWidget):
    """专业搜索自动完成组件"""
    
    # 信号：当选择专业时触发
    majorSelected = Signal(str)
    
    def __init__(
        self, 
        major_service: MajorService,
        theme_manager: ThemeManager,
        parent=None
    ):
        super().__init__(parent)
        self.major_service = major_service
        self.theme_manager = theme_manager
        self._init_ui()
        
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # 输入框 - 使用 Fluent LineEdit
        self.input = LineEdit()
        self.input.setPlaceholderText("输入专业名称搜索...")
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
        # 清理输入文本
        import re
        cleaned = re.sub(r'\s+', '', text)
        if cleaned != text:
            # 更新输入框
            self.input.blockSignals(True)
            self.input.setText(cleaned)
            self.input.blockSignals(False)
            text = cleaned
        
        if not text:
            self.results_list.setVisible(False)
            return
        
        # 搜索专业
        majors = self.major_service.search_majors(text, limit=8)
        
        if not majors:
            self.results_list.setVisible(False)
            return
        
        # 显示搜索结果
        self.results_list.clear()
        for major in majors:
            item = QListWidgetItem(major.name)
            item.setData(Qt.ItemDataRole.UserRole, major.name)
            self.results_list.addItem(item)
        
        self.results_list.setVisible(True)
    
    def _on_item_clicked(self, item: QListWidgetItem):
        """点击搜索结果项"""
        major_name = item.data(Qt.ItemDataRole.UserRole)
        
        # 填充输入框
        self.input.setText(major_name)
        
        # 隐藏搜索结果
        self.results_list.setVisible(False)
        
        # 发送信号
        self.majorSelected.emit(major_name)
    
    def set_text(self, text: str):
        """设置输入框文本"""
        self.input.setText(text)
    
    def text(self) -> str:
        """获取输入框文本"""
        return self.input.text()
    
    def clear(self):
        """清空输入框和搜索结果"""
        self.input.clear()
        self.results_list.clear()
        self.results_list.setVisible(False)
