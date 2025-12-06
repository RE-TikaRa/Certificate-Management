from pathlib import Path
from typing import Any, ClassVar

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CheckBox,
    ComboBox,
    InfoBar,
    LineEdit,
    PrimaryPushButton,
    PushButton,
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

        # Description
        desc = (
            "本系统支持通过 Excel 文件批量导入专业数据，用于在录入成员信息时提供自动补全功能。\n\n"
            "使用步骤：\n"
            "1. 点击“打开模板”按钮，查看或编辑 Excel 模板文件（docs/index.xlsx）。\n"
            "2. 在模板中维护专业列表，请保留表头，每行填写一个专业名称。\n"
            "3. 保存 Excel 文件后，点击“从 Excel 导入”按钮，选择该文件进行更新。\n"
            "4. 导入成功后，新专业将立即生效。"
        )
        desc_label = BodyLabel(desc)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #606060;")
        card_layout.addWidget(desc_label)

        card_layout.addSpacing(16)

        btn_row = QHBoxLayout()
        import_btn = PrimaryPushButton("从 Excel 导入")
        import_btn.clicked.connect(self._import_majors)

        template_btn = PushButton("打开模板")
        template_btn.clicked.connect(self._open_major_template)

        btn_row.addWidget(import_btn)
        btn_row.addWidget(template_btn)
        btn_row.addStretch()
        card_layout.addLayout(btn_row)
        return card

    def _get_major_excel_path(self) -> Path:
        return Path(__file__).resolve().parents[3] / "docs" / "index.xlsx"

    def _open_major_template(self) -> None:
        excel_path = self._get_major_excel_path()
        if not excel_path.exists():
            InfoBar.warning("未找到模板", f"请确认 {excel_path} 是否存在", parent=self.window())
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(excel_path)))

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
