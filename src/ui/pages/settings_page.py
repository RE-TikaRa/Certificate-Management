from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QVBoxLayout,
    QWidget,
    QLabel,
    QHBoxLayout,
    QApplication,
)
from qfluentwidgets import CheckBox, InfoBar, PrimaryPushButton, PushButton, ComboBox

from ..theme import create_card, create_page_header, make_section_title
from ..styled_theme import ThemeManager, ThemeMode

from .base_page import BasePage


class SettingsPage(BasePage):
    THEME_OPTIONS = {
        "light": "浅色",
        "dark": "深色", 
        "auto": "跟随系统",
    }
    
    def __init__(self, ctx, theme_manager: ThemeManager):
        super().__init__(ctx, theme_manager)
        self.attach_dir = QLabel()
        self.backup_dir = QLabel()
        self.frequency = ComboBox()
        self.frequency.addItems(["manual", "startup", "daily", "weekly"])
        self.include_attachments = CheckBox("包含附件")
        self.include_logs = CheckBox("包含日志")
        self.theme_mode = ComboBox()
        self.theme_mode.addItems(list(self.THEME_OPTIONS.values()))
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(18)
        layout.addWidget(create_page_header("系统设置", "配置目录、主题与备份策略"))

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
        self.frequency.setCurrentText(self.ctx.settings.get("backup_frequency", "manual"))
        self.include_attachments.setChecked(self.ctx.settings.get("include_attachments", "true") == "true")
        self.include_logs.setChecked(self.ctx.settings.get("include_logs", "true") == "true")
        # Convert stored theme value to display text
        stored_theme = self.ctx.settings.get("theme_mode", "light")
        display_text = self.THEME_OPTIONS.get(stored_theme, "浅色")
        self.theme_mode.setCurrentText(display_text)

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
            self.ctx.settings.set("backup_frequency", self.frequency.currentText())
            self.ctx.settings.set("include_attachments", str(self.include_attachments.isChecked()).lower())
            self.ctx.settings.set("include_logs", str(self.include_logs.isChecked()).lower())
            
            # Convert display text back to theme value
            display_text = self.theme_mode.currentText()
            theme_value = next(
                (k for k, v in self.THEME_OPTIONS.items() if v == display_text),
                "light"
            )
            self.ctx.settings.set("theme_mode", theme_value)
            
            # Apply theme changes
            theme_mode = self.theme_manager.get_theme_from_text(theme_value)
            self.theme_manager.set_theme(theme_mode)
            
            # Refresh entire window stylesheet
            main_window = self.window()
            if hasattr(main_window, 'apply_theme_stylesheet'):
                main_window.apply_theme_stylesheet()
            
            InfoBar.success("成功", "设置已保存", parent=self.window())
        except Exception as e:
            InfoBar.error("错误", f"保存设置失败: {e}", parent=self.window())

    def _backup_now(self) -> None:
        path = self.ctx.backup.perform_backup()
        InfoBar.success("备份完成", str(path), duration=2000, parent=self)
