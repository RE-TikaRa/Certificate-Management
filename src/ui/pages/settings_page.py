from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QLabel,
)
from qfluentwidgets import InfoBar

from .base_page import BasePage


class SettingsPage(BasePage):
    def __init__(self, ctx):
        super().__init__(ctx)
        self.attach_dir = QLabel()
        self.backup_dir = QLabel()
        self.frequency = QComboBox()
        self.frequency.addItems(["manual", "startup", "daily", "weekly"])
        self.include_attachments = QCheckBox("包含附件")
        self.include_logs = QCheckBox("包含日志")
        self.theme_mode = QComboBox()
        self.theme_mode.addItems(["light", "dark"])
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("附件目录", self.attach_dir)
        attach_btn = QPushButton("选择…")
        attach_btn.clicked.connect(self._choose_attach_dir)
        form.addRow("", attach_btn)
        form.addRow("备份目录", self.backup_dir)
        backup_btn = QPushButton("选择…")
        backup_btn.clicked.connect(self._choose_backup_dir)
        form.addRow("", backup_btn)
        form.addRow("自动备份频率", self.frequency)
        form.addRow(self.include_attachments)
        form.addRow(self.include_logs)
        form.addRow("主题模式", self.theme_mode)

        group = QGroupBox("系统设置")
        group.setLayout(form)
        layout.addWidget(group)

        save_btn = QPushButton("保存设置")
        save_btn.clicked.connect(self._save)
        backup_btn = QPushButton("立即备份")
        backup_btn.clicked.connect(self._backup_now)
        layout.addWidget(save_btn)
        layout.addWidget(backup_btn)
        layout.addStretch()

    def refresh(self) -> None:
        self.attach_dir.setText(self.ctx.attachments.root.as_posix())
        self.backup_dir.setText(self.ctx.backup.backup_root.as_posix())
        self.frequency.setCurrentText(self.ctx.settings.get("backup_frequency", "manual"))
        self.include_attachments.setChecked(self.ctx.settings.get("include_attachments", "true") == "true")
        self.include_logs.setChecked(self.ctx.settings.get("include_logs", "true") == "true")
        self.theme_mode.setCurrentText(self.ctx.settings.get("theme_mode", "light"))

    def _choose_attach_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择附件目录", self.attach_dir.text())
        if path:
            self.attach_dir.setText(path)

    def _choose_backup_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择备份目录", self.backup_dir.text())
        if path:
            self.backup_dir.setText(path)

    def _save(self) -> None:
        self.ctx.settings.bulk_update(
            {
                "attachment_root": self.attach_dir.text(),
                "backup_root": self.backup_dir.text(),
                "backup_frequency": self.frequency.currentText(),
                "include_attachments": str(self.include_attachments.isChecked()).lower(),
                "include_logs": str(self.include_logs.isChecked()).lower(),
                "theme_mode": self.theme_mode.currentText(),
            }
        )
        self.ctx.backup.schedule_jobs()
        InfoBar.success("设置已保存", "", duration=2000, parent=self)

    def _backup_now(self) -> None:
        path = self.ctx.backup.perform_backup()
        InfoBar.success("备份完成", str(path), duration=2000, parent=self)
