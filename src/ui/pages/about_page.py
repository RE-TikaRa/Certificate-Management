"""
关于页面
显示系统信息、版本信息和开发者信息
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QScrollArea, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, FluentIcon, HyperlinkButton, TitleLabel

from ..styled_theme import ThemeManager
from .base_page import BasePage


class AboutPage(BasePage):
    """关于页面"""

    def __init__(self, ctx, theme_manager: ThemeManager):
        super().__init__(ctx, theme_manager)
        self._build_ui()

    def _build_ui(self):
        """构建UI"""
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setObjectName("aboutScrollArea")
        outer_layout.addWidget(scroll_area)
        self.content_widget = scroll_area

        container = QWidget()
        container.setObjectName("pageRoot")
        scroll_area.setWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(60, 40, 60, 40)
        layout.setSpacing(40)

        # 应用主题
        self._apply_theme()
        self.theme_manager.themeChanged.connect(self._apply_theme)

        # ============ 标题区域 ============
        header_layout = QVBoxLayout()
        header_layout.setSpacing(16)

        # 系统名称
        title = TitleLabel("荣誉证书管理系统")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(28)
        title_font.setBold(True)
        title.setFont(title_font)
        header_layout.addWidget(title)

        # 英文名称
        subtitle = BodyLabel("Certificate Management System")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_font = QFont()
        subtitle_font.setPointSize(14)
        subtitle.setFont(subtitle_font)
        header_layout.addWidget(subtitle)

        # 版本信息
        version = BodyLabel("Version 1.0.0")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_font = QFont()
        version_font.setPointSize(12)
        version.setFont(version_font)
        header_layout.addWidget(version)

        layout.addLayout(header_layout)
        layout.addSpacing(20)

        # ============ 信息卡片区域 ============
        info_card = self._create_info_card(
            "系统简介",
            "荣誉证书管理系统是一款基于 PySide6 开发的桌面应用程序，"
            "个人向用途，用于管理各类竞赛荣誉证书、成员信息和附件文档。\n\n"
            "系统提供了证书录入、数据统计、成员管理、文档导入等功能，"
            "帮助用户高效地组织和查询荣誉信息。",
        )
        layout.addWidget(info_card)

        # ============ 技术栈卡片 ============
        tech_card = self._create_info_card(
            "技术栈",
            "• GUI 框架: PySide6 6.10.1 + QFluentWidgets 1.9.2\n"
            "• 数据库: SQLAlchemy 2.0.32 + SQLite\n"
            "• 编程语言: Python 3.9+\n"
            "• 文档处理: python-docx, openpyxl\n"
            "• 数据分析: pandas, matplotlib",
        )
        layout.addWidget(tech_card)

        # ============ 功能特性卡片 ============
        features_card = self._create_info_card(
            "核心功能",
            "• 荣誉录入: 支持手动录入、批量导入、文档提取\n"
            "• 数据统计: 多维度可视化数据分析与报表\n"
            "• 成员管理: 成员信息管理、历史记录查询\n"
            "• 智能搜索: 模糊搜索、专业名称自动补全\n"
            "• 附件管理: 文件上传、MD5校验、回收站\n"
            "• 主题切换: 深色/浅色主题无缝切换\n"
            "• 数据备份: 自动/手动备份、数据导出",
        )
        layout.addWidget(features_card)

        # ============ 开发者信息卡片 ============
        dev_card = self._create_info_card(
            "开发者信息",
            "• 开发者: RE-TikaRa\n"
            "• 项目地址: https://github.com/RE-TikaRa/Certificate-Management\n"
            "• 开发时间: 2025年12月\n"
            "• 许可证: MIT License",
        )
        layout.addWidget(dev_card)

        # ============ 链接按钮区域 ============
        links_layout = QHBoxLayout()
        links_layout.setSpacing(20)
        links_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        github_btn = HyperlinkButton("https://github.com/RE-TikaRa/Certificate-Management", "GitHub 仓库", self)
        github_btn.setIcon(FluentIcon.GITHUB)
        links_layout.addWidget(github_btn)

        issue_btn = HyperlinkButton(
            "https://github.com/RE-TikaRa/Certificate-Management/issues",
            "问题反馈",
            self,
        )
        issue_btn.setIcon(FluentIcon.FEEDBACK)
        links_layout.addWidget(issue_btn)

        layout.addLayout(links_layout)

        # ============ 版权信息 ============
        copyright_label = BodyLabel("© 2025 RE-TikaRa. All rights reserved.")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        copyright_font = QFont()
        copyright_font.setPointSize(10)
        copyright_label.setFont(copyright_font)
        layout.addWidget(copyright_label)

        layout.addStretch()

    def _create_info_card(self, title: str, content: str) -> QWidget:
        """创建信息卡片"""
        card = QWidget()
        card.setObjectName("infoCard")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(12)

        # 标题
        title_label = BodyLabel(title)
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        card_layout.addWidget(title_label)

        # 内容
        content_label = BodyLabel(content)
        content_label.setWordWrap(True)
        content_font = QFont()
        content_font.setPointSize(11)
        content_label.setFont(content_font)
        card_layout.addWidget(content_label)

        return card

    def _apply_theme(self):
        """应用主题样式"""
        is_dark = self.theme_manager.is_dark

        if is_dark:
            scroll_bg = "#232635"
            card_bg = "#2b2b3c"
            card_border = "#3a3a4a"
            text_color = "#e0e0e0"
        else:
            scroll_bg = "#f4f6fb"
            card_bg = "#ffffff"
            card_border = "#e0e0e0"
            text_color = "#333333"

        self.setStyleSheet(f"""
            QWidget#pageRoot {{
                background-color: {scroll_bg};
            }}
            QScrollArea#aboutScrollArea {{
                background-color: {scroll_bg};
                border: none;
            }}
            QWidget#infoCard {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 8px;
            }}
            QLabel {{
                color: {text_color};
                background-color: transparent;
            }}
        """)
