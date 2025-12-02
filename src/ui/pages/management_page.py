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
)
from PySide6.QtCore import Qt
from qfluentwidgets import PushButton

from ..theme import create_card, create_page_header, make_section_title, apply_table_style
from ..styled_theme import ThemeManager

from .base_page import BasePage


class ManagementPage(BasePage):
    """成员历史页面 - 显示所有历史成员信息"""
    
    def __init__(self, ctx, theme_manager: ThemeManager):
        super().__init__(ctx, theme_manager)
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
        self.members_table.setColumnCount(13)
        self.members_table.setHorizontalHeaderLabels([
            "姓名", "性别", "年龄", "身份证号", "手机号", "学号",
            "联系电话", "邮箱", "专业", "班级", "学院", "获奖次数", "操作"
        ])
        apply_table_style(self.members_table)
        self.members_table.setMinimumHeight(400)
        
        # 设置列宽
        widths = [80, 60, 50, 100, 90, 80, 90, 100, 80, 80, 80, 80, 60]
        for i, w in enumerate(widths):
            self.members_table.setColumnWidth(i, w)
        
        card_layout.addWidget(self.members_table)
        container_layout.addWidget(card)
        
        container_layout.addStretch()
        
        self.refresh()
    
    def refresh(self) -> None:
        """刷新成员表格"""
        self.members_table.setRowCount(0)
        members = self.ctx.awards.list_members()
        
        for row, member in enumerate(members):
            self.members_table.insertRow(row)
            
            # 基本信息
            fields = [
                member.name or "",
                member.gender or "",
                str(member.age) if member.age else "",
                member.id_card or "",
                member.phone or "",
                member.student_id or "",
                member.contact_phone or "",
                member.email or "",
                member.major or "",
                member.class_name or "",
                member.college or "",
            ]
            
            # 填充信息字段
            for col, value in enumerate(fields):
                item = QTableWidgetItem(value)
                self.members_table.setItem(row, col, item)
            
            # 获奖次数
            award_count = len(member.awards)
            count_item = QTableWidgetItem(str(award_count))
            self.members_table.setItem(row, 11, count_item)
            
            # 操作按钮
            btn = PushButton("编辑")
            btn.clicked.connect(lambda checked, m=member: self._edit_member(m))
            self.members_table.setCellWidget(row, 12, btn)
    
    def _edit_member(self, member) -> None:
        """编辑成员信息"""
        # TODO: 实现成员编辑对话框
        pass

