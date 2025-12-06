from pathlib import Path
from typing import Any, ClassVar

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CheckBox,
    ComboBox,
    FluentIcon as FIF,
    IconWidget,
    InfoBar,
    LineEdit,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    StrongBodyLabel,
)

from src.services.major_importer import read_majors_from_excel

from ..styled_theme import ThemeManager
from ..theme import create_card, create_page_header, make_section_title
from .base_page import BasePage


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


class SettingsPage(BasePage):
    THEME_OPTIONS: ClassVar[dict[str, str]] = {
        "light": "浅色",
        "dark": "深色",
        "auto": "跟随系统",
    }

    FREQUENCY_OPTIONS: ClassVar[dict[str, str]] = {
        "manual": "手动",
        "startup": "启动时",
        "daily": "每天",
        "weekly": "每周",
    }

    MAJOR_STAT_FIELDS: ClassVar[list[tuple[str, str, FIF, str]]] = [
        ("library_total", "收录专业", FIF.FOLDER, "blue"),
        ("member_major_count", "成员使用专业", FIF.PEOPLE, "purple"),
        ("covered_major_count", "已匹配专业", FIF.ACCEPT, "green"),
        ("unmatched_major_count", "未匹配专业", FIF.QUESTION, "orange"),
        ("member_records_with_major", "成员记录（含专业）", FIF.ALIGNMENT, "cyan"),
        ("coverage_percent", "覆盖率", FIF.PIE_SINGLE, "gold"),
    ]

    def __init__(self, ctx, theme_manager: ThemeManager):
        super().__init__(ctx, theme_manager)
        self.attach_dir = QLabel()
        self.backup_dir = QLabel()
        self.frequency = ComboBox()
        self.frequency.addItems(list(self.FREQUENCY_OPTIONS.values()))
        self.include_attachments = CheckBox("包含附件")
        self.include_logs = CheckBox("包含日志")
        self.theme_mode = ComboBox()
        self.theme_mode.addItems(list(self.THEME_OPTIONS.values()))
        self.email_suffix = LineEdit()
        clean_input_text(self.email_suffix)
        self.email_suffix.setPlaceholderText("例如: @st.gsau.edu.cn")
        self.major_stat_labels: dict[str, QLabel] = {}

        # Top 5 Majors Container
        self.top_majors_layout = QVBoxLayout()
        self.top_majors_layout.setSpacing(12)
        self.top_majors_layout.setContentsMargins(0, 0, 0, 0)

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        title_widget = QWidget()
        title_widget.setObjectName("pageRoot")
        title_layout = QVBoxLayout(title_widget)
        title_layout.setContentsMargins(32, 24, 32, 0)
        title_layout.setSpacing(0)
        title_layout.addWidget(create_page_header("系统设置", "配置目录、主题与备份策略"))
        outer_layout.addWidget(title_widget)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer_layout.addWidget(scroll)
        self.content_widget = scroll

        container = QWidget()
        container.setObjectName("pageRoot")
        scroll.setWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 28, 32, 32)
        layout.setSpacing(28)

        settings_card, settings_layout = create_card()
        settings_layout.addWidget(make_section_title("目录与备份"))
        form = QFormLayout()
        form.setSpacing(12)

        attach_row = self._build_path_row(self.attach_dir, self._choose_attach_dir)
        form.addRow("附件目录", attach_row)
        backup_row = self._build_path_row(self.backup_dir, self._choose_backup_dir)
        form.addRow("备份目录", backup_row)
        form.addRow("自动备份频率", self.frequency)
        form.addRow(self.include_attachments)
        form.addRow(self.include_logs)
        form.addRow("主题模式", self.theme_mode)
        form.addRow("默认邮箱后缀", self.email_suffix)
        settings_layout.addLayout(form)

        action_row = QHBoxLayout()
        save_btn = PrimaryPushButton("保存设置")
        save_btn.clicked.connect(self._save)
        backup_btn = PushButton("立即备份")
        backup_btn.clicked.connect(self._backup_now)
        action_row.addWidget(save_btn)
        action_row.addWidget(backup_btn)
        action_row.addStretch()
        settings_layout.addLayout(action_row)
        layout.addWidget(settings_card)
        layout.addWidget(self._build_major_card())
        layout.addStretch()

    def _build_path_row(self, label: QLabel, chooser) -> QWidget:
        wrapper = QWidget()
        row = QHBoxLayout(wrapper)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(label)
        row.addStretch()
        button = PushButton("选择…")
        button.clicked.connect(chooser)
        row.addWidget(button)
        return wrapper

    def refresh(self) -> None:
        self.attach_dir.setText(self.ctx.attachments.root.as_posix())
        self.backup_dir.setText(self.ctx.backup.backup_root.as_posix())

        # Convert stored frequency value to display text
        stored_frequency = self.ctx.settings.get("backup_frequency", "manual")
        display_frequency = self.FREQUENCY_OPTIONS.get(stored_frequency, "手动")
        self.frequency.setCurrentText(display_frequency)

        self.include_attachments.setChecked(self.ctx.settings.get("include_attachments", "true") == "true")
        self.include_logs.setChecked(self.ctx.settings.get("include_logs", "true") == "true")
        # Convert stored theme value to display text
        stored_theme = self.ctx.settings.get("theme_mode", "light")
        display_text = self.THEME_OPTIONS.get(stored_theme, "浅色")
        self.theme_mode.setCurrentText(display_text)
        # Load email suffix
        email_suffix = self.ctx.settings.get("email_suffix", "@st.gsau.edu.cn")
        self.email_suffix.setText(email_suffix)
        self._refresh_major_stats()

    def _choose_attach_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择附件目录", self.attach_dir.text())
        if path:
            self.attach_dir.setText(path)

    def _choose_backup_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择备份目录", self.backup_dir.text())
        if path:
            self.backup_dir.setText(path)

    def _save(self) -> None:
        try:
            self.ctx.settings.set("attachment_root", self.attach_dir.text())
            self.ctx.settings.set("backup_root", self.backup_dir.text())

            # Convert display text back to frequency value
            display_frequency = self.frequency.currentText()
            frequency_value = next(
                (k for k, v in self.FREQUENCY_OPTIONS.items() if v == display_frequency),
                "manual",
            )
            self.ctx.settings.set("backup_frequency", frequency_value)

            self.ctx.settings.set("include_attachments", str(self.include_attachments.isChecked()).lower())
            self.ctx.settings.set("include_logs", str(self.include_logs.isChecked()).lower())

            # Save email suffix
            email_suffix = self.email_suffix.text().strip()
            if not email_suffix:
                email_suffix = "@st.gsau.edu.cn"  # 默认值
            self.ctx.settings.set("email_suffix", email_suffix)

            # Convert display text back to theme value
            display_text = self.theme_mode.currentText()
            theme_value = next((k for k, v in self.THEME_OPTIONS.items() if v == display_text), "light")
            self.ctx.settings.set("theme_mode", theme_value)

            # Apply theme changes
            theme_mode = self.theme_manager.get_theme_from_text(theme_value)
            self.theme_manager.set_theme(theme_mode)

            # Refresh entire window stylesheet
            main_window: Any = self.window()
            if hasattr(main_window, "apply_theme_stylesheet"):
                main_window.apply_theme_stylesheet()

            InfoBar.success("成功", "设置已保存", parent=self.window())
        except Exception as e:
            InfoBar.error("错误", f"保存设置失败: {e}", parent=self.window())

    def _backup_now(self) -> None:
        path = self.ctx.backup.perform_backup()
        InfoBar.success("备份完成", str(path), duration=2000, parent=self.window())

    def _build_major_card(self) -> QWidget:
        card, card_layout = create_card()
        card_layout.addWidget(make_section_title("专业库管理"))

        stats_grid = QGridLayout()
        stats_grid.setSpacing(16)
        for idx, (key, label, icon, accent) in enumerate(self.MAJOR_STAT_FIELDS):
            stats_grid.addWidget(self._create_major_stat_tile(key, label, icon, accent), idx // 3, idx % 3)
        card_layout.addLayout(stats_grid)

        desc_label = QLabel("使用 Excel 模板批量导入，或直接维护 tools/index.xlsx。")
        desc_label.setProperty("description", True)
        card_layout.addWidget(desc_label)

        list_title = QLabel("Top 5 专业使用情况（按成员出现次数）")
        list_title.setProperty("subtitle", True)
        card_layout.addWidget(list_title)

        # Top 5 Container
        top_majors_container = QWidget()
        top_majors_container.setLayout(self.top_majors_layout)
        card_layout.addWidget(top_majors_container)

        btn_row = QHBoxLayout()
        import_btn = PushButton("从 Excel 导入")
        import_btn.clicked.connect(self._import_majors)
        refresh_btn = PushButton("刷新统计")
        refresh_btn.clicked.connect(self._refresh_major_stats)
        template_btn = PushButton("打开模板")
        template_btn.clicked.connect(self._open_major_template)
        btn_row.addWidget(import_btn)
        btn_row.addWidget(refresh_btn)
        btn_row.addWidget(template_btn)
        btn_row.addStretch()
        card_layout.addLayout(btn_row)
        return card

    def _create_major_stat_tile(self, key: str, caption: str, icon: FIF, accent: str) -> QWidget:
        frame = QFrame()
        frame.setProperty("metricTile", True)
        frame.setProperty("accent", accent)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # Header with Icon
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        icon_widget = IconWidget(icon)
        icon_widget.setFixedSize(24, 24)
        header_layout.addWidget(icon_widget)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        value_label = QLabel("--")
        value_label.setProperty("metricValue", True)
        layout.addWidget(value_label)

        caption_label = QLabel(caption)
        caption_label.setProperty("metricCaption", True)
        layout.addWidget(caption_label)

        self.major_stat_labels[key] = value_label
        return frame

    def _get_major_excel_path(self) -> Path:
        return Path(__file__).resolve().parents[3] / "tools" / "index.xlsx"

    def _open_major_template(self) -> None:
        excel_path = self._get_major_excel_path()
        if not excel_path.exists():
            InfoBar.warning("未找到模板", f"请确认 {excel_path} 是否存在", parent=self.window())
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(excel_path)))

    def _refresh_major_stats(self) -> None:
        try:
            stats = self.ctx.majors.get_statistics()
        except Exception as error:
            InfoBar.error("刷新失败", f"无法获取专业统计：{error}", parent=self.window())
            return

        for key, label in self.major_stat_labels.items():
            value = stats.get(key, "--")
            if key == "coverage_percent" and isinstance(value, (int, float)):
                label.setText(f"{value:.1f}%")
            else:
                label.setText(str(value))

        # Update Top 5
        # Clear existing
        while self.top_majors_layout.count():
            item = self.top_majors_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        top_majors = stats.get("top_majors", [])
        if not isinstance(top_majors, list):
            top_majors = []

        if not top_majors:
            label = QLabel("暂无使用记录")
            label.setProperty("description", True)
            self.top_majors_layout.addWidget(label)
        else:
            # top_majors is list[tuple[str, int]] here
            max_count = top_majors[0][1] if top_majors else 1
            for idx, (name, count) in enumerate(top_majors, 1):
                self.top_majors_layout.addWidget(
                    self._create_top_major_item(idx, name, count, max_count)
                )

    def _create_top_major_item(self, idx: int, name: str, count: int, max_count: int) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(6)

        # Header: "1. Name" ... "Count"
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(12)

        # Rank Badge
        rank_label = StrongBodyLabel(str(idx))
        rank_label.setFixedWidth(24)
        rank_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Rank Styling
        if idx == 1:
            rank_label.setStyleSheet("color: #FFD700; font-size: 18px; font-weight: bold;")  # Gold
        elif idx == 2:
            rank_label.setStyleSheet("color: #C0C0C0; font-size: 16px; font-weight: bold;")  # Silver
        elif idx == 3:
            rank_label.setStyleSheet("color: #CD7F32; font-size: 16px; font-weight: bold;")  # Bronze
        else:
            rank_label.setStyleSheet("color: #808080; font-size: 14px;")  # Grey

        header.addWidget(rank_label)

        # Name
        name_label = BodyLabel(name)
        header.addWidget(name_label)

        header.addStretch()

        # Count
        count_label = CaptionLabel(f"{count} 人次")
        count_label.setStyleSheet("color: #909090;")
        header.addWidget(count_label)

        layout.addLayout(header)

        # Progress Bar
        bar = ProgressBar()
        bar.setRange(0, max_count)
        bar.setValue(count)
        bar.setFixedHeight(4)
        layout.addWidget(bar)

        return widget

    def _import_majors(self) -> None:
        default_excel = self._get_major_excel_path()
        start_dir = default_excel if default_excel.exists() else default_excel.parent
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择专业 Excel 文件",
            str(start_dir),
            "Excel 文件 (*.xlsx)",
        )
        if not file_path:
            return

        excel_path = Path(file_path)
        try:
            majors = read_majors_from_excel(excel_path)
        except ModuleNotFoundError as error:
            if error.name == "openpyxl":
                InfoBar.error("缺少依赖", "请先安装 openpyxl，再重试导入", parent=self.window())
                return
            InfoBar.error("导入失败", str(error), parent=self.window())
            return
        except Exception as error:
            InfoBar.error("读取失败", f"无法解析 Excel：{error}", parent=self.window())
            return

        if not majors:
            InfoBar.warning("无数据", "文件中未找到专业名称", parent=self.window())
            return

        try:
            count = self.ctx.majors.replace_all_majors(majors)
        except Exception as error:
            InfoBar.error("写入失败", f"导入数据库时出错：{error}", parent=self.window())
            return

        InfoBar.success("导入完成", f"成功导入 {count} 个专业", parent=self.window())
        self._refresh_major_stats()
