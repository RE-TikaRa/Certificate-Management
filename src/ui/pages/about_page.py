"""
关于页面
显示系统信息、版本信息和开发者信息
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QScrollArea, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, FluentIcon, HyperlinkButton, TitleLabel

from ...version import get_app_version
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
        version = BodyLabel(f"Version {get_app_version()}")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_font = QFont()
        version_font.setPointSize(12)
        version.setFont(version_font)
        header_layout.addWidget(version)

        # 标签条
        tags_layout = QHBoxLayout()
        tags_layout.setSpacing(8)
        tags_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for text in ("Desktop", "Offline-first", "Local MCP", "SQLite Local"):
            tag = BodyLabel(text)
            tag.setObjectName("tagChip")
            tag_font = QFont()
            tag_font.setPointSize(10)
            tag.setFont(tag_font)
            tag.setMargin(6)
            tags_layout.addWidget(tag)
        header_layout.addLayout(tags_layout)

        layout.addLayout(header_layout)
        layout.addSpacing(20)

        # ============ 信息卡片区域 ============
        info_card = self._create_info_card(
            "系统简介",
            "荣誉证书管理系统是一款基于 PySide6 + QFluentWidgets 的桌面端应用，"
            "用于管理竞赛/科研荣誉证书、成员信息与附件材料，完全离线运行。\n\n"
            "内置证书录入、全文检索（FTS5）、成员管理（支持快照）、回收站、自动备份与导入/导出等功能，"
            "并提供本地 MCP（stdio/SSE）服务与可选 Gradio Web 控制台，方便外部智能体安全接入，"
            "支持用户名/密码/令牌、写入开关与 PII 过滤，帮助学校/团队高效组织与查询荣誉数据。",
        )
        layout.addWidget(info_card)

        # ============ 技术栈卡片 ============
        tech_card = self._create_info_card(
            "技术栈",
            "• GUI: PySide6 + QFluentWidgets\n"
            "• 数据: SQLAlchemy 2.x + SQLite（本地）\n"
            "• 语言: Python 3.14+\n"
            "• MCP: OpenAI MCP stdio/SSE + 可选 Gradio Web 控制台\n"
            "• 定时/任务: APScheduler\n"
            "• 日志: loguru\n"
            "• 工具: uv / ruff / pyright\n"
            "• 表格: openpyxl（XLSX）\n"
            "• 文档: Windows Word COM（提取 .doc 文本）",
        )
        layout.addWidget(tech_card)

        # ============ 功能特性卡片 ============
        features_card = self._create_info_card(
            "核心功能",
            "• 荣誉录入：手动/批量导入（CSV、XLSX），字段校验与预检（dry-run 不写入数据库）\n"
            "• 全文检索：FTS5 + 筛选/排序，500ms 防抖\n"
            "• 成员管理：10 字段监控，学校/专业代码自动补全\n"
            "• 附件管理：MD5 校验去重，删除移入 attachments/.trash\n"
            "• 统计看板：8 张指标卡 + 饼/柱图 + 最近荣誉\n"
            "• 主题与样式：亮/暗主题即时切换\n"
            "• 备份与清理：自动/手动备份，日志与数据库一键清理\n"
            "• AI 接入：内置 MCP（stdio/SSE）与本地 Web 控制台，可配置用户名/密码/令牌、写入开关与 PII 去除",
        )
        layout.addWidget(features_card)

        # ============ 开发者信息卡片 ============
        dev_card = self._create_info_card(
            "开发者信息",
            "• 开发者: RE-TikaRa\n"
            "• 项目地址: https://github.com/RE-TikaRa/Certificate-Management\n"
            "• 最新构建: 2025-12\n"
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
            chip_bg = "#32364a"
            chip_text = "#e8e8f5"
        else:
            scroll_bg = "#f4f6fb"
            card_bg = "#ffffff"
            card_border = "#e0e0e0"
            text_color = "#333333"
            chip_bg = "#e8ecf7"
            chip_text = "#1f2540"

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
            QLabel#tagChip {{
                background-color: {chip_bg};
                color: {chip_text};
                border-radius: 12px;
                padding: 2px 10px;
            }}
            QLabel {{
                color: {text_color};
                background-color: transparent;
            }}
        """)
