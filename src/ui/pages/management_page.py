from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QScrollArea,
    QFrame,
    QDialog,
    QGridLayout,
    QLineEdit,
    QMessageBox,
)
from PySide6.QtCore import Qt

from PySide6.QtGui import QColor, QPalette
from qfluentwidgets import PushButton

from ..theme import create_card, create_page_header, make_section_title, apply_table_style
from ..styled_theme import ThemeManager

from .base_page import BasePage


class ManagementPage(BasePage):
    """成员历史页面 - 显示所有历史成员信息"""
    
    def __init__(self, ctx, theme_manager: ThemeManager):
        super().__init__(ctx, theme_manager)
        self.last_members_data = None  # 保存上次数据用于变化检测
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(scroll)
        
        # 容器
        container = QWidget()
        container.setObjectName("pageRoot")
        scroll.setWidget(container)
        
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(32, 24, 32, 32)
        container_layout.setSpacing(28)
        
        # 页面头
        container_layout.addWidget(create_page_header("成员管理", "查看历史成员信息"))
        
        # 成员表格卡片
        card, card_layout = create_card()
        card_layout.addWidget(make_section_title("历史成员"))
        
        # 创建表格
        self.members_table = QTableWidget()
        self.members_table.setColumnCount(6)
        self.members_table.setHorizontalHeaderLabels([
            "姓名", "性别", "电话", "学院", "班级", "详情"
        ])
        apply_table_style(self.members_table)
        self.members_table.setMinimumHeight(400)
        self.members_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 设置列宽
        widths = [80, 60, 120, 100, 80, 70]
        for i, w in enumerate(widths):
            self.members_table.setColumnWidth(i, w)
        
        card_layout.addWidget(self.members_table)
        container_layout.addWidget(card)
        
        container_layout.addStretch()
        self.refresh()
    
    def _auto_refresh(self):
        """自动刷新 - 检测数据变化后刷新"""
        members = self.ctx.awards.list_members()
        
        # 转换为可比较的格式（包含所有字段以检测所有变化）
        current_data = [
            (m.id, m.name, m.gender, m.id_card, m.phone, m.student_id, 
             m.email, m.major, m.class_name, m.college) 
            for m in members
        ]
        
        # 如果数据有变化，刷新表格
        if current_data != self.last_members_data:
            self.last_members_data = current_data
            self.refresh()
    
    def refresh(self) -> None:
        """刷新成员表格"""
        self.members_table.setRowCount(0)
        members = self.ctx.awards.list_members()
        
        # 保存当前数据用于变化检测
        self.last_members_data = [(m.id, m.name, m.gender, m.phone, m.college, m.class_name) for m in members]
        
        for row, member in enumerate(members):
            self.members_table.insertRow(row)
            
            # 基本信息 - 只显示关键字段
            fields = [
                member.name or "",
                member.gender or "",
                member.phone or "",
                member.college or "",
                member.class_name or "",
            ]
            
            # 填充信息字段
            for col, value in enumerate(fields):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.members_table.setItem(row, col, item)
            
            # 详情按钮
            detail_btn = PushButton("详情")
            detail_btn.clicked.connect(lambda checked, m=member: self._show_member_detail(m))
            self.members_table.setCellWidget(row, 5, detail_btn)
    
    def _show_member_detail(self, member) -> None:
        """显示成员详情对话框"""
        dialog = MemberDetailDialog(member, parent=self)
        if dialog.exec():
            # 如果删除了成员，刷新表格
            if dialog.member_deleted:
                self.refresh()


class MemberDetailDialog(QDialog):
    """成员详情对话框 - 多分栏网格布局"""
    
    def __init__(self, member, parent=None):
        super().__init__(parent)
        self.member = member
        self.original_data = self._get_member_data()
        self.is_editing = False
        self.field_widgets = {}  # 存储字段 widget
        self.member_deleted = False  # 标记成员是否被删除
        
        self.setWindowTitle(f"成员详情 - {member.name}")
        self.setModal(True)
        self.setMinimumWidth(900)
        self.setMinimumHeight(600)
        self._init_ui()
        self._apply_theme()
    
    def _get_member_data(self) -> dict:
        """获取成员数据"""
        return {
            "name": self.member.name or "",
            "gender": self.member.gender or "",
            "id_card": self.member.id_card or "",
            "phone": self.member.phone or "",
            "email": self.member.email or "",
            "student_id": self.member.student_id or "",
            "major": self.member.major or "",
            "class_name": self.member.class_name or "",
            "college": self.member.college or "",
        }
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # 滚动区域
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        
        # 内容容器
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)
        
        # 基本信息区域
        content_layout.addWidget(self._create_section("基本信息", [
            ("姓名", "name"),
            ("性别", "gender"),
            ("身份证号", "id_card"),
            ("手机号", "phone"),
            ("邮箱", "email"),
        ]))
        
        # 学生信息区域
        content_layout.addWidget(self._create_section("学生信息", [
            ("学号", "student_id"),
            ("专业", "major"),
            ("班级", "class_name"),
            ("学院", "college"),
        ]))
        
        content_layout.addStretch()
        self.scroll.setWidget(content)
        layout.addWidget(self.scroll)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        # 编辑/保存按钮
        self.edit_btn = PushButton("编辑")
        self.edit_btn.clicked.connect(self._toggle_edit_mode)
        btn_layout.addWidget(self.edit_btn)
        
        # 删除按钮
        self.delete_btn = PushButton("删除")
        self.delete_btn.clicked.connect(self._confirm_delete)
        btn_layout.addWidget(self.delete_btn)
        
        btn_layout.addStretch()
        
        # 关闭按钮
        close_btn = PushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)
    
    def _create_section(self, title: str, fields: list[tuple[str, str]]) -> QWidget:
        """创建信息分区卡片"""
        section = QFrame()
        section.setObjectName("memberDetailCard")
        
        layout = QVBoxLayout(section)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        # 标题
        title_label = QLabel(title)
        title_label.setObjectName("memberDetailTitle")
        layout.addWidget(title_label)
        
        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setObjectName("memberDetailSeparator")
        separator.setFixedHeight(1)
        layout.addWidget(separator)
        
        # 信息网格 - 3列布局
        grid = QGridLayout()
        grid.setSpacing(16)
        
        for idx, (label_text, field_key) in enumerate(fields):
            row = idx // 3
            col = idx % 3
            
            # 标签
            label = QLabel(f"{label_text}:")
            label.setObjectName("memberDetailLabel")
            grid.addWidget(label, row * 2, col)
            
            # 值
            value = self.original_data.get(field_key, "")
            value_label = QLabel(value)
            value_label.setObjectName("memberDetailValue")
            value_label.setWordWrap(True)
            
            # 存储 widget
            self.field_widgets[field_key] = value_label
            
            grid.addWidget(value_label, row * 2 + 1, col)
        
        layout.addLayout(grid)
        return section
    
    def _toggle_edit_mode(self):
        """切换编辑模式"""
        self.is_editing = not self.is_editing
        
        if self.is_editing:
            self.edit_btn.setText("保存")
            self._enable_edit()
        else:
            self.edit_btn.setText("编辑")
            self._save_changes()
            self._disable_edit()
    
    def _enable_edit(self):
        """启用编辑模式 - 将标签转换为输入框"""
        for field_key, widget in list(self.field_widgets.items()):
            if isinstance(widget, QLabel):
                current_value = widget.text()
                
                # 创建输入框
                input_field = QLineEdit()
                input_field.setText(current_value)
                input_field.setObjectName("memberDetailInput")
                
                # 获取布局并替换
                parent = widget.parent()
                if parent:
                    layout = parent.layout()
                    if layout and isinstance(layout, QGridLayout):
                        # 在网格布局中查找并替换
                        for i in range(layout.count()):
                            if layout.itemAt(i).widget() == widget:
                                item = layout.takeAt(i)
                                layout.addWidget(input_field, *layout.getItemPosition(i))
                                break
                
                self.field_widgets[field_key] = input_field
    
    def _disable_edit(self):
        """禁用编辑模式 - 将输入框转换回标签"""
        for field_key, widget in list(self.field_widgets.items()):
            if isinstance(widget, QLineEdit):
                current_value = widget.text()
                
                # 创建标签
                label = QLabel(current_value)
                label.setObjectName("memberDetailValue")
                label.setWordWrap(True)
                
                # 获取布局并替换
                parent = widget.parent()
                if parent:
                    layout = parent.layout()
                    if layout and isinstance(layout, QGridLayout):
                        # 在网格布局中查找并替换
                        for i in range(layout.count()):
                            if layout.itemAt(i).widget() == widget:
                                item = layout.takeAt(i)
                                layout.addWidget(label, *layout.getItemPosition(i))
                                break
                
                self.field_widgets[field_key] = label
    
    def _save_changes(self):
        """保存数据到数据库"""
        from src.services.member_service import MemberService
        
        try:
            service = MemberService()
            
            # 更新成员数据
            def get_field_value(key: str) -> str:
                widget = self.field_widgets.get(key)
                if isinstance(widget, QLineEdit):
                    return widget.text()
                elif isinstance(widget, QLabel):
                    return widget.text()
                return ""
            
            self.member.name = get_field_value("name")
            self.member.gender = get_field_value("gender")
            self.member.id_card = get_field_value("id_card")
            
            self.member.phone = get_field_value("phone")
            self.member.email = get_field_value("email")
            self.member.student_id = get_field_value("student_id")
            self.member.major = get_field_value("major")
            self.member.class_name = get_field_value("class_name")
            self.member.college = get_field_value("college")
            
            service.update_member(self.member)
            
            # 更新原始数据
            self.original_data = self._get_member_data()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {str(e)}")
    
    def _confirm_delete(self):
        """确认删除"""
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除成员 {self.member.name} 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._delete_member()
    
    def _delete_member(self):
        """删除成员"""
        from src.services.member_service import MemberService
        
        try:
            service = MemberService()
            service.delete_member(self.member.id)
            self.member_deleted = True  # 标记删除
            QMessageBox.information(self, "成功", "成员已删除")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"删除失败: {str(e)}")
    
    def _apply_theme(self):
        """应用主题样式"""
        from ..styled_theme import ThemeManager
        
        theme_mgr = ThemeManager.instance()
        is_dark = theme_mgr.current_theme == "dark"
        
        # 根据主题选择颜色
        if is_dark:
            scroll_bg = "#2a2a3a"
            card_bg = "#353751"
            card_border = "rgba(138, 159, 255, 0.1)"
            title_color = "#e0e0e0"
            label_color = "#b0b0c0"  # 提亮标签颜色
            value_color = "#e0e0e0"
            separator_color = "#4a4a5e"
            input_bg = "#2a2d3f"
            input_border = "rgba(138, 159, 255, 0.3)"
            input_text = "#e0e0e0"
            btn_delete_style = "background-color: #c92a2a; color: white;"
        else:
            scroll_bg = "#f5f5f5"
            card_bg = "#ffffff"
            card_border = "#e0e0e0"
            title_color = "#1a1a1a"
            label_color = "#666666"
            value_color = "#333333"
            separator_color = "#ddd"
            input_bg = "#ffffff"
            input_border = "#d0d0d0"
            input_text = "#333333"
            btn_delete_style = "background-color: #ff6b6b; color: white;"
        
        # 应用滚动区域样式 - 设置滚动区域和其内部 widget 的背景色
        scroll_stylesheet = f"""
            QScrollArea {{
                border: none;
                background-color: {scroll_bg};
            }}
            QScrollArea > QWidget {{
                background-color: {scroll_bg};
            }}
            QWidget#scrollContent {{
                background-color: {scroll_bg};
            }}
        """
        self.scroll.setStyleSheet(scroll_stylesheet)
        # 确保内部容器也有正确的背景色
        scroll_widget = self.scroll.widget()
        if scroll_widget:
            scroll_widget.setObjectName("scrollContent")
            scroll_widget.setAutoFillBackground(True)
            palette = scroll_widget.palette()
            palette.setColor(palette.ColorRole.Window, 
                           {"#2a2a3a": QColor(42, 42, 58), "#f5f5f5": QColor(245, 245, 245)}[scroll_bg])
            scroll_widget.setPalette(palette)
        
        # 应用卡片样式
        card_stylesheet = f"""
            QFrame#memberDetailCard {{
                background-color: {card_bg};
                border-radius: 8px;
                border: 1px solid {card_border};
                padding: 0px;
            }}
        """
        
        # 应用标题样式
        title_stylesheet = f"""
            QLabel#memberDetailTitle {{
                font-weight: bold;
                font-size: 13px;
                color: {title_color};
            }}
        """
        
        # 应用标签样式 - 增加颜色对比度
        label_stylesheet = f"""
            QLabel#memberDetailLabel {{
                color: {label_color};
                font-size: 12px;
                font-weight: 500;
            }}
        """
        
        # 应用值样式
        value_stylesheet = f"""
            QLabel#memberDetailValue {{
                color: {value_color};
                font-size: 12px;
                font-weight: 500;
                border: 1px solid {card_border};
                border-radius: 4px;
                padding: 4px 6px;
                background-color: {input_bg};
            }}
        """
        
        # 应用分隔线样式
        separator_stylesheet = f"""
            QFrame#memberDetailSeparator {{
                color: {separator_color};
            }}
        """
        
        # 应用输入框样式
        input_stylesheet = f"""
            QLineEdit#memberDetailInput {{
                border: 1px solid {input_border};
                border-radius: 4px;
                padding: 4px 6px;
                background-color: {input_bg};
                color: {input_text};
                selection-background-color: #4a90e2;
                font-size: 12px;
            }}
            QLineEdit#memberDetailInput:focus {{
                border: 2px solid #4a90e2;
            }}
        """
        
        # 应用删除按钮样式
        self.delete_btn.setStyleSheet(btn_delete_style)
        
        # 构建完整的样式表
        full_stylesheet = (
            card_stylesheet +
            title_stylesheet +
            label_stylesheet +
            value_stylesheet +
            separator_stylesheet +
            input_stylesheet
        )
        
        self.setStyleSheet(full_stylesheet)

