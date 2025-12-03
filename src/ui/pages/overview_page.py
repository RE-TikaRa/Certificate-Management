from __future__ import annotations

import logging
from datetime import datetime
from PySide6.QtCore import Qt, QTimer, QSize, QDate
from PySide6.QtWidgets import (
    QLabel, QVBoxLayout, QHBoxLayout, QScrollArea, QWidget, 
    QMessageBox, QGridLayout, QFrame, QDialog, QLineEdit, QSpinBox, QComboBox
)
from PySide6.QtGui import QFont, QColor, QPalette
from qfluentwidgets import (
    PrimaryPushButton, PushButton, TitleLabel, BodyLabel, CaptionLabel
)

from .base_page import BasePage
from ..styled_theme import ThemeManager
from ..theme import create_card, create_page_header, make_section_title

logger = logging.getLogger(__name__)


class OverviewPage(BasePage):
    """总览页面 - 显示所有已输入的荣誉项目"""
    
    def __init__(self, ctx, theme_manager: ThemeManager):
        super().__init__(ctx, theme_manager)
        self.awards_list = []
        
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        
        self.scrollArea = QScrollArea()
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer_layout.addWidget(self.scrollArea)
        
        container = QWidget()
        container.setObjectName("pageRoot")
        self.scrollArea.setWidget(container)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 24, 32, 32)
        layout.setSpacing(28)
        
        # 页面标题
        layout.addWidget(create_page_header("所有荣誉项目", "查看和管理已输入的所有荣誉信息"))
        
        # 荣誉项目卡片
        card, card_layout = create_card()
        card_layout.addWidget(make_section_title("荣誉列表"))
        
        # 刷新按钮
        refresh_layout = QHBoxLayout()
        refresh_layout.addStretch()
        refresh_btn = PrimaryPushButton("刷新数据")
        refresh_btn.setFixedWidth(100)
        refresh_btn.clicked.connect(self.refresh)
        refresh_layout.addWidget(refresh_btn)
        card_layout.addLayout(refresh_layout)
        
        # 荣誉项目容器
        self.awards_container = QWidget()
        self.awards_layout = QVBoxLayout(self.awards_container)
        self.awards_layout.setContentsMargins(0, 0, 0, 0)
        self.awards_layout.setSpacing(12)
        
        card_layout.addWidget(self.awards_container)
        
        layout.addWidget(card)
        layout.addStretch()
        
        # 自动刷新定时器（每5秒检查一次数据）
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._auto_refresh)
        self.refresh_timer.start(5000)  # 5秒更新一次
        
        self._apply_theme()
        self.refresh()
    
    def _auto_refresh(self) -> None:
        """自动刷新数据"""
        try:
            current_count = len(self.awards_list)
            awards = self.ctx.awards.list_awards()
            new_count = len(awards)
            
            # 只在数据有变化时刷新UI
            if current_count != new_count:
                self.refresh()
        except Exception as e:
            logger.debug(f"自动刷新失败: {e}")
    
    def refresh(self) -> None:
        """刷新荣誉列表"""
        try:
            # 清空现有项目
            while self.awards_layout.count():
                item = self.awards_layout.takeAt(0)
                if item.widget():
                    widget = item.widget()
                    if widget:
                        widget.hide()
                        widget.deleteLater()
            
            # 获取所有荣誉
            self.awards_list = self.ctx.awards.list_awards()
            
            if not self.awards_list:
                # 空状态：显示提示
                self.awards_layout.addStretch()
                
                empty_container = QWidget()
                empty_layout = QVBoxLayout(empty_container)
                empty_layout.setContentsMargins(0, 0, 0, 0)
                empty_layout.setSpacing(12)
                empty_layout.addStretch()
                
                # 图标 - 使用 QLabel 并设置大字体
                empty_icon = QLabel("📋")
                icon_font = QFont()
                icon_font.setPointSize(72)
                empty_icon.setFont(icon_font)
                empty_layout.addWidget(empty_icon, alignment=Qt.AlignCenter)
                
                empty_text = BodyLabel("暂无项目数据")
                empty_layout.addWidget(empty_text, alignment=Qt.AlignCenter)
                
                empty_hint = CaptionLabel("点击「录入」页添加新项目")
                empty_layout.addWidget(empty_hint, alignment=Qt.AlignCenter)
                
                empty_layout.addStretch()
                self.awards_layout.addWidget(empty_container)
                
                self.awards_layout.addStretch()
                return
            
            # 按日期排序（最新优先）
            sorted_awards = sorted(self.awards_list, key=lambda a: a.award_date, reverse=True)
            
            # 创建每个荣誉的卡片
            for award in sorted_awards:
                card = self._create_award_card(award)
                self.awards_layout.addWidget(card)
            
            self.awards_layout.addStretch()
            
            logger.debug(f"已加载 {len(self.awards_list)} 个荣誉项目")
        except Exception as e:
            logger.exception(f"刷新荣誉列表失败: {e}")
            QMessageBox.warning(self, "错误", f"刷新失败: {str(e)}")
    
    def _create_award_card(self, award) -> QWidget:
        """创建单个荣誉卡片"""
        card = QFrame()
        card.setObjectName("awardItemCard")
        card.setMinimumHeight(100)
        
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(6)
        
        # 顶部：标题 + 级别标签
        top_layout = QHBoxLayout()
        
        # 标题和级别
        title_level_layout = QVBoxLayout()
        
        # 荣誉名称
        title = TitleLabel(award.competition_name)
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        title_level_layout.addWidget(title)
        
        # 级别等级
        level_text = f"{award.level} • {award.rank}"
        if award.certificate_code:
            level_text += f" • {award.certificate_code}"
        level_label = CaptionLabel(level_text)
        title_level_layout.addWidget(level_label)
        
        top_layout.addLayout(title_level_layout, 1)
        
        # 日期和人数 - 右上角
        date_people_layout = QVBoxLayout()
        date_text = BodyLabel(award.award_date.strftime("%Y-%m-%d"))
        people_count = BodyLabel(f"{len(award.members)} 人")
        date_people_layout.addWidget(date_text)
        date_people_layout.addWidget(people_count)
        top_layout.addLayout(date_people_layout)
        
        card_layout.addLayout(top_layout)
        
        # 中部：成员列表
        if award.members:
            members_text = ", ".join([m.name for m in award.members])
            members_label = BodyLabel(members_text)
            members_label.setWordWrap(True)
            members_label.setStyleSheet("font-size: 12px;")
            card_layout.addWidget(members_label)
        
        # 底部：备注和按钮
        if award.remarks:
            remarks_label = CaptionLabel(f"备注: {award.remarks}")
            remarks_label.setWordWrap(True)
            remarks_label.setStyleSheet("font-size: 11px;")
            card_layout.addWidget(remarks_label)
        
        # 操作按钮
        action_layout = QHBoxLayout()
        action_layout.addStretch()
        
        edit_btn = PrimaryPushButton("编辑")
        edit_btn.setFixedWidth(60)
        edit_btn.setFixedHeight(28)
        edit_btn.clicked.connect(lambda: self._edit_award(award))
        
        delete_btn = PushButton("删除")
        delete_btn.setFixedWidth(60)
        delete_btn.setFixedHeight(28)
        delete_btn.clicked.connect(lambda: self._delete_award(award))
        
        action_layout.addWidget(edit_btn)
        action_layout.addSpacing(6)
        action_layout.addWidget(delete_btn)
        
        card_layout.addLayout(action_layout)
        
        return card
    
    def _edit_award(self, award) -> None:
        """编辑荣誉"""
        try:
            dialog = AwardDetailDialog(self, award, self.theme_manager, self.ctx)
            if dialog.exec():
                self.refresh()  # 刷新列表
        except Exception as e:
            logger.exception(f"编辑失败: {e}")
            QMessageBox.warning(self, "错误", f"编辑失败: {str(e)}")
    
    def _delete_award(self, award) -> None:
        """删除荣誉"""
        reply = QMessageBox.question(
            self, 
            "确认删除", 
            f"确定要删除 '{award.competition_name}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.ctx.awards.delete_award(award.id)
                self.refresh()
                QMessageBox.information(self, "成功", "已删除")
            except Exception as e:
                logger.exception(f"删除失败: {e}")
                QMessageBox.warning(self, "错误", f"删除失败: {str(e)}")
    
    def closeEvent(self, event):
        """页面关闭时停止定时器"""
        if self.refresh_timer:
            self.refresh_timer.stop()
        super().closeEvent(event)
    
    def showEvent(self, event):
        """页面显示时启动定时器"""
        super().showEvent(event)
        if self.refresh_timer:
            self.refresh_timer.start()
    
    def _apply_theme(self) -> None:
        """应用主题到滚动区域"""
        is_dark = self.theme_manager.is_dark
        scroll_bg = "#2a2a3a" if is_dark else "#f5f5f5"
        
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
        self.scrollArea.setStyleSheet(scroll_stylesheet)
        # 确保内部容器也有正确的背景色
        scroll_widget = self.scrollArea.widget()
        if scroll_widget:
            scroll_widget.setObjectName("scrollContent")
            scroll_widget.setAutoFillBackground(True)
            palette = scroll_widget.palette()
            palette.setColor(palette.ColorRole.Window, 
                           {"#2a2a3a": QColor(42, 42, 58), "#f5f5f5": QColor(245, 245, 245)}[scroll_bg])
            scroll_widget.setPalette(palette)


class AwardDetailDialog(QDialog):
    """荣誉详情编辑对话框 - 和录入页相同的结构"""
    
    def __init__(self, parent, award, theme_manager: ThemeManager, ctx):
        super().__init__(parent)
        self.award = award
        self.theme_manager = theme_manager
        self.ctx = ctx
        self.members_data = []  # 存储成员卡片数据
        
        self.setWindowTitle(f"编辑荣誉 - {award.competition_name}")
        self.setMinimumWidth(700)
        self.setMinimumHeight(600)
        self._init_ui()
        self._apply_theme()
    
    def _init_ui(self):
        from ..theme import create_card, make_section_title
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # 内容容器
        content = QWidget()
        content.setObjectName("pageRoot")
        scroll.setWidget(content)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)
        
        # === 基本信息卡片 ===
        info_card, info_layout = create_card()
        
        # Row 1: 比赛名称 + 获奖日期
        row1 = QHBoxLayout()
        row1.setSpacing(16)
        name_col = QVBoxLayout()
        name_label = QLabel("比赛名称")
        name_label.setObjectName("formLabel")
        self.name_input = QLineEdit(self.award.competition_name)
        name_col.addWidget(name_label)
        name_col.addWidget(self.name_input)
        
        date_col = QVBoxLayout()
        date_label = QLabel("获奖日期")
        date_label.setObjectName("formLabel")
        date_row = QHBoxLayout()
        date_row.setSpacing(8)
        
        self.year_input = QSpinBox()
        self.year_input.setRange(1900, 2100)
        self.year_input.setValue(self.award.award_date.year)
        self.year_input.setMaximumWidth(80)
        
        self.month_input = QSpinBox()
        self.month_input.setRange(1, 12)
        self.month_input.setValue(self.award.award_date.month)
        self.month_input.setMaximumWidth(80)
        
        self.day_input = QSpinBox()
        self.day_input.setRange(1, 31)
        self.day_input.setValue(self.award.award_date.day)
        self.day_input.setMaximumWidth(80)
        
        date_row.addWidget(self.year_input)
        date_row.addWidget(QLabel("年"))
        date_row.addWidget(self.month_input)
        date_row.addWidget(QLabel("月"))
        date_row.addWidget(self.day_input)
        date_row.addWidget(QLabel("日"))
        date_row.addStretch()
        
        date_col.addWidget(date_label)
        date_col.addLayout(date_row)
        
        row1.addLayout(name_col, 2)
        row1.addLayout(date_col, 2)
        info_layout.addLayout(row1)
        
        # Row 2: 赛事级别 + 奖项等级
        row2 = QHBoxLayout()
        row2.setSpacing(16)
        level_col = QVBoxLayout()
        level_label = QLabel("赛事级别")
        level_label.setObjectName("formLabel")
        self.level_input = QComboBox()
        self.level_input.addItems(["国家级", "省级", "校级"])
        self.level_input.setCurrentText(self.award.level)
        level_col.addWidget(level_label)
        level_col.addWidget(self.level_input)
        
        rank_col = QVBoxLayout()
        rank_label = QLabel("奖项等级")
        rank_label.setObjectName("formLabel")
        self.rank_input = QComboBox()
        self.rank_input.addItems(["一等奖", "二等奖", "三等奖", "优秀奖"])
        self.rank_input.setCurrentText(self.award.rank)
        rank_col.addWidget(rank_label)
        rank_col.addWidget(self.rank_input)
        
        row2.addLayout(level_col, 1)
        row2.addLayout(rank_col, 1)
        info_layout.addLayout(row2)
        
        # Row 3: 证书编号
        cert_col = QVBoxLayout()
        cert_label = QLabel("证书编号")
        cert_label.setObjectName("formLabel")
        self.cert_input = QLineEdit(self.award.certificate_code or "")
        cert_col.addWidget(cert_label)
        cert_col.addWidget(self.cert_input)
        info_layout.addLayout(cert_col)
        
        # Row 4: 备注
        remark_col = QVBoxLayout()
        remark_label = QLabel("备注")
        remark_label.setObjectName("formLabel")
        self.remarks_input = QLineEdit(self.award.remarks or "")
        remark_col.addWidget(remark_label)
        remark_col.addWidget(self.remarks_input)
        info_layout.addLayout(remark_col)
        
        content_layout.addWidget(info_card)
        
        # === 成员卡片 ===
        members_card, members_layout = create_card()
        members_layout.addWidget(make_section_title("参与成员"))
        
        self.members_container = QWidget()
        self.members_container.setStyleSheet("QWidget { background-color: transparent; }")
        self.members_list_layout = QVBoxLayout(self.members_container)
        self.members_list_layout.setContentsMargins(0, 0, 0, 0)
        self.members_list_layout.setSpacing(12)
        self.members_list_layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinAndMaxSize)
        
        members_layout.addWidget(self.members_container)
        
        # 加载已有成员
        for member in self.award.members:
            self._add_member_card(member)
        
        # 添加成员按钮
        add_member_btn = PrimaryPushButton("添加成员")
        add_member_btn.clicked.connect(self._add_member_row)
        members_layout.addWidget(add_member_btn)
        
        content_layout.addWidget(members_card)
        content_layout.addStretch()
        
        layout.addWidget(scroll)
        
        # === 按钮 ===
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        save_btn = PrimaryPushButton("保存")
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)
        
        cancel_btn = PushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
    
    def _add_member_card(self, member=None):
        """添加成员卡片"""
        import logging
        logger = logging.getLogger(__name__)
        
        member_card = QWidget()
        is_dark = self.theme_manager.is_dark
        if is_dark:
            card_style = """
                QWidget {
                    background-color: #353751;
                    border-radius: 8px;
                    border: 1px solid #4a4a5e;
                }
            """
            label_style = "color: #a0a0a0; font-size: 12px;"
            input_style = """
                QLineEdit {
                    border: 1px solid #4a4a5e;
                    border-radius: 4px;
                    padding: 6px;
                    background-color: #2a2a3a;
                    color: #e0e0e0;
                }
                QLineEdit:focus {
                    border: 2px solid #4a90e2;
                }
            """
        else:
            card_style = """
                QWidget {
                    background-color: #f5f5f5;
                    border-radius: 8px;
                    border: 1px solid #e0e0e0;
                }
            """
            label_style = "color: #666; font-size: 12px;"
            input_style = """
                QLineEdit {
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    padding: 6px;
                    background-color: white;
                    color: #333;
                }
                QLineEdit:focus {
                    border: 2px solid #1890ff;
                }
            """
        
        member_card.setStyleSheet(card_style)
        member_layout = QVBoxLayout(member_card)
        member_layout.setContentsMargins(12, 12, 12, 12)
        member_layout.setSpacing(10)
        
        # 头部：成员编号和删除按钮
        header_layout = QHBoxLayout()
        member_index = len(self.members_data) + 1
        member_label = QLabel(f"成员 #{member_index}")
        member_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        header_layout.addWidget(member_label)
        header_layout.addStretch()
        
        delete_btn = PushButton("删除")
        delete_btn.setMaximumWidth(60)
        
        # 表单布局
        form_grid = QGridLayout()
        form_grid.setSpacing(12)
        form_grid.setColumnStretch(1, 1)
        form_grid.setColumnStretch(3, 1)
        
        field_names = ['name', 'gender', 'id_card', 'phone', 'student_id',
                       'email', 'major', 'class_name', 'college']
        field_labels = ['姓名', '性别', '身份证号', '手机号', '学号',
                        '邮箱', '专业', '班级', '学院']
        
        member_fields = {}
        for field_name, label in zip(field_names, field_labels):
            input_widget = QLineEdit()
            input_widget.setPlaceholderText(f"请输入{label}")
            input_widget.setStyleSheet(input_style)
            
            # 如果是编辑现有成员，填充数据
            if member:
                value = getattr(member, field_name, "")
                if value:
                    input_widget.setText(str(value))
            
            member_fields[field_name] = input_widget
        
        # 按2列布局
        for idx, (field_name, label) in enumerate(zip(field_names, field_labels)):
            col = (idx % 2) * 2
            row = idx // 2
            
            label_widget = QLabel(label)
            label_widget.setStyleSheet(label_style)
            label_widget.setMinimumWidth(50)
            label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            form_grid.addWidget(label_widget, row, col, alignment=Qt.AlignmentFlag.AlignCenter)
            form_grid.addWidget(member_fields[field_name], row, col + 1)
        
        # 组装
        member_layout.addLayout(header_layout)
        member_layout.addLayout(form_grid)
        
        delete_btn.clicked.connect(lambda: self._remove_member_card(member_card, member_fields))
        header_layout.addWidget(delete_btn)
        
        member_data = {
            'card': member_card,
            'fields': member_fields
        }
        self.members_data.append(member_data)
        self.members_list_layout.addWidget(member_card)
    
    def _add_member_row(self):
        """添加空白成员卡片"""
        self._add_member_card()
    
    def _remove_member_card(self, member_card, member_fields):
        """删除成员卡片"""
        for idx, data in enumerate(self.members_data):
            if data['card'] == member_card:
                self.members_data.pop(idx)
                break
        member_card.deleteLater()
    
    def _save(self):
        """保存编辑"""
        try:
            # 获取成员数据
            members = self._get_members_data()
            
            self.ctx.awards.update_award(
                self.award.id,
                competition_name=self.name_input.text(),
                award_date=QDate(self.year_input.value(), self.month_input.value(), self.day_input.value()).toPython(),
                level=self.level_input.currentText(),
                rank=self.rank_input.currentText(),
                certificate_code=self.cert_input.text() or None,
                remarks=self.remarks_input.text() or None,
                member_names=members
            )
            
            # 刷新管理页面，因为成员信息可能已更改
            # 向上查找 main_window，然后刷新 management_page
            parent = self.parent()
            while parent:
                management_page = getattr(parent, 'management_page', None)
                if management_page:
                    management_page.refresh()
                    break
                parent = parent.parent() if hasattr(parent, 'parent') else None
            
            self.accept()
        except Exception as e:
            logger.exception(f"保存奖项失败: {e}")
            QMessageBox.critical(self, "错误", f"保存失败: {str(e)}")
    
    def _get_members_data(self):
        """获取成员数据"""
        members = []
        field_names = ['name', 'gender', 'id_card', 'phone', 'student_id',
                       'email', 'major', 'class_name', 'college']
        
        for member_data in self.members_data:
            member_fields = member_data['fields']
            name_widget = member_fields.get('name')
            if isinstance(name_widget, QLineEdit):
                name = name_widget.text().strip()
                if name:
                    member_info = {'name': name}
                    for field_name in field_names[1:]:
                        widget = member_fields.get(field_name)
                        if isinstance(widget, QLineEdit):
                            value = widget.text().strip()
                            if value:
                                member_info[field_name] = value
                    members.append(member_info)
        return members
    
    def _apply_theme(self):
        """应用主题"""
        is_dark = self.theme_manager.is_dark
        if is_dark:
            bg_color = "#2a2a3a"
        else:
            bg_color = "#f5f5f5"
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
            }}
            QLineEdit {{
                border: 1px solid #4a4a5e;
                border-radius: 4px;
                padding: 6px;
                background-color: {"#1a1a2e" if is_dark else "#ffffff"};
                color: {"#e0e0e0" if is_dark else "#333333"};
            }}
            QComboBox {{
                border: 1px solid #4a4a5e;
                border-radius: 4px;
                padding: 6px;
                background-color: {"#1a1a2e" if is_dark else "#ffffff"};
                color: {"#e0e0e0" if is_dark else "#333333"};
            }}
            QSpinBox {{
                border: 1px solid #4a4a5e;
                border-radius: 4px;
                padding: 6px;
                background-color: {"#1a1a2e" if is_dark else "#ffffff"};
                color: {"#e0e0e0" if is_dark else "#333333"};
            }}
        """)
