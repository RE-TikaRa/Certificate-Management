from __future__ import annotations

import logging
from datetime import datetime
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtWidgets import (
    QLabel, QVBoxLayout, QHBoxLayout, QScrollArea, QWidget, 
    QPushButton, QMessageBox, QHeaderView, QGridLayout, QFrame
)
from PySide6.QtGui import QFont, QColor
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
            # 切换到录入页并加载数据
            main_window = self.window()
            if hasattr(main_window, 'entry_page'):
                main_window.entry_page.load_award_for_editing(award)
                main_window.navigate("entry")
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
        """
        self.scrollArea.setStyleSheet(scroll_stylesheet)
