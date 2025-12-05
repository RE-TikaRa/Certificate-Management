from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QTableView,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import InfoBar, MaskDialogBase, MessageBox, PushButton

from ..styled_theme import ThemeManager
from ..table_models import MembersTableModel
from ..theme import (
    apply_table_style,
    create_card,
    create_page_header,
    make_section_title,
)
from ..utils.async_utils import run_in_thread
from .base_page import BasePage

logger = logging.getLogger(__name__)


def clean_input_text(line_edit: QLineEdit) -> None:
    """
    为 QLineEdit 添加自动清理空白字符功能
    自动删除用户输入中的所有空格、制表符、换行符等空白字符

    Args:
        line_edit: 要应用清理功能的 QLineEdit 组件
    """
    import re

    def on_text_changed(text: str):
        # 删除所有空白字符（空格、制表符、换行符等）
        cleaned = re.sub(r"\s+", "", text)
        if cleaned != text:
            # 临时断开信号避免递归
            line_edit.textChanged.disconnect(on_text_changed)
            line_edit.setText(cleaned)
            line_edit.setCursorPosition(len(cleaned))  # 保持光标位置
            # 重新连接信号
            line_edit.textChanged.connect(on_text_changed)

    line_edit.textChanged.connect(on_text_changed)


class ManagementPage(BasePage):
    """成员历史页面"""

    def __init__(self, ctx, theme_manager: ThemeManager):
        super().__init__(ctx, theme_manager)
        self._cached_member_ids = set()
        self.setObjectName("pageRoot")

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

        # 标题和刷新按钮
        header_layout = QHBoxLayout()
        header_layout.addWidget(make_section_title("成员列表"))
        header_layout.addStretch()
        from qfluentwidgets import FluentIcon, TransparentToolButton

        refresh_btn = TransparentToolButton(FluentIcon.SYNC)
        refresh_btn.setToolTip("刷新数据")
        refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(refresh_btn)
        card_layout.addLayout(header_layout)

        # 创建表格
        self.members_model = MembersTableModel(self)
        self.members_table = QTableView()
        self.members_table.setModel(self.members_model)
        apply_table_style(self.members_table)
        self.members_table.setMinimumHeight(400)
        self.members_table.horizontalHeader().setStretchLastSection(False)
        self.members_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.members_table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.members_table.horizontalHeader().setDefaultSectionSize(110)
        self.members_table.verticalHeader().setDefaultSectionSize(44)
        self.members_table.clicked.connect(self._on_table_clicked)
        widths = [80, 60, 120, 120, 90, 80]
        for i, w in enumerate(widths):
            self.members_table.setColumnWidth(i, w)

        card_layout.addWidget(self.members_table)
        container_layout.addWidget(card)

        container_layout.addStretch()
        self.refresh()

    def _auto_refresh(self):
        """检测成员数据变化，通过 ID 集合比较判断是否需要刷新"""
        try:
            from sqlalchemy import select

            from ..data.models import TeamMember

            with self.ctx.db.session_scope() as session:
                member_ids = set(session.scalars(select(TeamMember.id)).all())

            if member_ids != self._cached_member_ids:
                self._cached_member_ids = member_ids
                self.refresh()
        except Exception as e:
            logger.debug(f"成员自动刷新失败: {e}")

    def refresh(self) -> None:
        """异步刷新成员表格"""
        run_in_thread(self.ctx.awards.list_members, self._on_members_loaded)

    def _on_members_loaded(self, members) -> None:
        self._cached_member_ids = {m.id for m in members}
        self.members_model.set_objects(members)
        self.members_table.resizeColumnsToContents()

    def _on_table_clicked(self, index):
        if index.column() == 5:
            member = self.members_model.object_at(index.row())
            self._show_member_detail(member)

    def _show_member_detail(self, member) -> None:
        """显示成员详情对话框"""
        dialog = MemberDetailDialog(member, parent=self)
        if dialog.exec():
            # 如果删除了成员，刷新表格
            if dialog.member_deleted:
                self.refresh()


class MemberDetailDialog(MaskDialogBase):
    """成员详情对话框 - 多分栏网格布局"""

    def __init__(self, member, parent=None):
        super().__init__(parent)
        self.member = member
        self.original_data = self._get_member_data()
        self.is_editing = False
        self.field_widgets = {}  # 存储字段 widget
        self.input_field_cache = {}  # 缓存所有 QLineEdit 实例
        self.member_deleted = False  # 标记成员是否被删除

        self.setWindowTitle(f"成员详情 - {member.name}")
        self.setModal(True)
        self.setMinimumWidth(900)
        self.setMinimumHeight(600)
        self.widget.setGraphicsEffect(None)

        # 设置中心 widget 的圆角
        self.widget.setObjectName("centerWidget")

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
        layout = QVBoxLayout(self.widget)  # 添加到 self.widget 而不是 self
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
        content_layout.addWidget(
            self._create_section(
                "基本信息",
                [
                    ("姓名", "name"),
                    ("性别", "gender"),
                    ("身份证号", "id_card"),
                    ("手机号", "phone"),
                    ("邮箱", "email"),
                ],
            )
        )

        # 学生信息区域
        content_layout.addWidget(
            self._create_section(
                "学生信息",
                [
                    ("学号", "student_id"),
                    ("专业", "major"),
                    ("班级", "class_name"),
                    ("学院", "college"),
                ],
            )
        )

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
            # 确保显示文本，避免 None 或空值显示为"口"
            display_value = str(value) if value else "-"
            value_label = QLabel(display_value)
            value_label.setObjectName("memberDetailValue")
            value_label.setWordWrap(True)

            # 存储 widget
            self.field_widgets[field_key] = value_label

            # 创建输入框并缓存（初始隐藏）
            input_field = QLineEdit()
            clean_input_text(input_field)  # 自动删除空白字符
            input_field.setText(value)
            input_field.setObjectName("memberDetailInput")
            input_field.hide()  # 初始隐藏
            self.input_field_cache[field_key] = input_field
            grid.addWidget(input_field, row * 2 + 1, col)

            # 值标签添加到网格
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
        """启用编辑模式"""
        for field_key in list(self.field_widgets.keys()):
            value_label = self.field_widgets[field_key]
            input_field = self.input_field_cache[field_key]

            # 同步当前值到输入框
            input_field.setText(value_label.text())

            # 隐藏标签，显示输入框
            value_label.hide()
            input_field.show()

    def _disable_edit(self):
        """禁用编辑模式"""
        for field_key in list(self.field_widgets.keys()):
            value_label = self.field_widgets[field_key]
            input_field = self.input_field_cache[field_key]

            # 显示标签，隐藏输入框
            value_label.show()
            input_field.hide()

    def _save_changes(self):
        """保存数据到数据库"""
        from src.services.member_service import MemberService

        try:
            service = MemberService()

            # 更新成员数据 - 从输入框缓存中读取
            def get_field_value(key: str) -> str:
                input_field = self.input_field_cache.get(key)
                if input_field:
                    return input_field.text()
                # 备选：从标签读取（防御）
                label = self.field_widgets.get(key)
                if label and isinstance(label, QLabel):
                    return label.text()
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
            InfoBar.error("错误", f"保存失败: {str(e)}", parent=self.window())

    def _confirm_delete(self):
        """确认删除"""
        box = MessageBox("确认删除", f"确定要删除成员 {self.member.name} 吗？", self.window())

        if box.exec():
            self._delete_member()

    def _delete_member(self):
        """删除成员"""
        from src.services.member_service import MemberService

        try:
            service = MemberService()
            service.delete_member(self.member.id)
            self.member_deleted = True  # 标记删除
            InfoBar.success("成功", "成员已删除", parent=self.window())
            self.accept()
        except Exception as e:
            InfoBar.error("错误", f"删除失败: {str(e)}", parent=self.window())

    def _apply_theme(self):
        """应用主题样式 - 包括对话框背景色和标题栏"""
        from ..styled_theme import ThemeManager

        theme_mgr = ThemeManager.instance()
        is_dark = theme_mgr.current_theme == "dark"

        # 根据主题选择颜色
        if is_dark:
            dialog_bg = "#1c1f2e"  # 对话框背景跟随主窗口深色
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
            dialog_bg = "#f4f6fb"  # 对话框背景跟随主窗口浅色
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

        # 首先设置中心 widget 的圆角和对话框背景色
        self.setStyleSheet(f"""
            #centerWidget {{
                background-color: {dialog_bg};
                border-radius: 12px;
                border: 1px solid {card_border};
            }}
            QDialog {{
                background-color: {dialog_bg};
                color: {title_color};
            }}
            QLabel {{
                color: {title_color};
            }}
        """)

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
            palette.setColor(
                palette.ColorRole.Window,
                {"#2a2a3a": QColor(42, 42, 58), "#f5f5f5": QColor(245, 245, 245)}[scroll_bg],
            )
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
            card_stylesheet
            + title_stylesheet
            + label_stylesheet
            + value_stylesheet
            + separator_stylesheet
            + input_stylesheet
        )

        self.setStyleSheet(full_stylesheet)

        # 设置 Palette 使标题栏也跟随主题
        palette = QPalette()
        if is_dark:
            palette.setColor(QPalette.ColorRole.Window, QColor("#1c1f2e"))
            palette.setColor(QPalette.ColorRole.WindowText, QColor("#e0e0e0"))
            palette.setColor(QPalette.ColorRole.Base, QColor("#2a2d3f"))
            palette.setColor(QPalette.ColorRole.Text, QColor("#e0e0e0"))
            palette.setColor(QPalette.ColorRole.Button, QColor("#2a2d3f"))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor("#e0e0e0"))
        else:
            palette.setColor(QPalette.ColorRole.Window, QColor("#f4f6fb"))
            palette.setColor(QPalette.ColorRole.WindowText, QColor("#1a1a1a"))
            palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
            palette.setColor(QPalette.ColorRole.Text, QColor("#1a1a1a"))
            palette.setColor(QPalette.ColorRole.Button, QColor("#ffffff"))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor("#1a1a1a"))
        self.setPalette(palette)

        # 关键：在Windows上强制设置标题栏颜色
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
