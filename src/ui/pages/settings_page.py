import logging
import shutil
import threading
from contextlib import suppress
from pathlib import Path
from queue import Empty, SimpleQueue
from typing import Any, ClassVar

from pypinyin import lazy_pinyin
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressDialog,
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
    MessageBox,
    PrimaryPushButton,
    PushButton,
)

from src.config import DB_PATH, LOG_DIR
from src.services.import_export import ImportResult
from src.services.major_importer import read_major_catalog_from_csv, read_majors_from_excel
from src.services.school_importer import read_school_list

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

    MAX_MAJOR_DISPLAY: ClassVar[int] = 200

    def __init__(self, ctx, theme_manager: ThemeManager):
        super().__init__(ctx, theme_manager)
        self.logger = logging.getLogger(__name__)
        self.attach_dir = QLabel()
        self.backup_dir = QLabel()
        self.backup_list = QListWidget()
        self.restore_btn = PrimaryPushButton("恢复选中")
        self.verify_btn = PushButton("验证选中")
        self.frequency = ComboBox()
        self.frequency.addItems(list(self.FREQUENCY_OPTIONS.values()))
        self.include_attachments = CheckBox("包含附件")
        self.include_logs = CheckBox("包含日志")
        self.theme_mode = ComboBox()
        self.theme_mode.addItems(list(self.THEME_OPTIONS.values()))
        self.email_suffix = LineEdit()
        clean_input_text(self.email_suffix)
        self.email_suffix.setPlaceholderText("例如: @st.gsau.edu.cn")
        self.school_total_value = QLabel("--")
        self.school_with_code_value = QLabel("--")
        self.major_total_value = QLabel("--")
        self.mapping_total_value = QLabel("--")
        self.college_total_value = QLabel("--")
        self.region_selector = ComboBox()
        self.region_selector.currentIndexChanged.connect(self._on_region_changed)
        self.school_selector = ComboBox()
        self.school_selector.currentIndexChanged.connect(self._load_school_major_list)
        self.school_major_list = QListWidget()
        self.school_major_list.setMinimumHeight(200)
        self._school_options: list[tuple[str | None, str | None]] = []
        self._region_options: list[str | None] = [None]
        self.school_import_btn: PrimaryPushButton | None = None
        self.major_import_btn: PushButton | None = None
        self.mapping_import_btn: PushButton | None = None
        self.award_import_btn: PrimaryPushButton | None = None
        self.award_export_btn: PushButton | None = None
        self.award_dry_run: CheckBox | None = None
        self.import_log_list = QListWidget()
        self.rebuild_fts_btn: PrimaryPushButton | None = None
        self._import_busy = False
        self._progress_dialog: QProgressDialog | None = None

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
        layout.addWidget(self._build_cleanup_card())
        layout.addWidget(self._build_award_import_card())
        layout.addWidget(self._build_backup_card())
        layout.addWidget(self._build_index_card())
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
        self._refresh_backup_list()

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
        self._refresh_academic_stats()
        self._refresh_import_log()

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
        card_layout.addWidget(make_section_title("学校与专业数据"))

        stats_layout = QGridLayout()
        stats_layout.setSpacing(16)
        stats_layout.addWidget(self._create_stat_block("学校总数", self.school_total_value), 0, 0)
        stats_layout.addWidget(self._create_stat_block("含标识码", self.school_with_code_value), 0, 1)
        stats_layout.addWidget(self._create_stat_block("专业目录", self.major_total_value), 0, 2)
        stats_layout.addWidget(self._create_stat_block("映射条目", self.mapping_total_value), 0, 3)
        stats_layout.addWidget(self._create_stat_block("学院数量", self.college_total_value), 0, 4)
        card_layout.addLayout(stats_layout)

        btn_row = QHBoxLayout()
        self.school_import_btn = PrimaryPushButton("导入学校列表")
        self.school_import_btn.clicked.connect(self._import_school_list)
        self.major_import_btn = PushButton("导入专业目录 (CSV)")
        self.major_import_btn.clicked.connect(self._import_major_catalog)
        self.mapping_import_btn = PushButton("导入学校-专业映射 (Excel)")
        self.mapping_import_btn.clicked.connect(self._import_school_major_mapping)
        btn_row.addWidget(self.school_import_btn)
        btn_row.addWidget(self.major_import_btn)
        btn_row.addWidget(self.mapping_import_btn)
        btn_row.addStretch()
        card_layout.addLayout(btn_row)

        selector_row = QHBoxLayout()
        selector_row.addWidget(QLabel("地区"))
        self.region_selector.setMinimumWidth(150)
        selector_row.addWidget(self.region_selector)
        selector_row.addWidget(QLabel("学校"))
        self.school_selector.setMinimumWidth(220)
        selector_row.addWidget(self.school_selector, 1)
        refresh_btn = PushButton("刷新列表")
        refresh_btn.clicked.connect(self._refresh_school_selector)
        selector_row.addWidget(refresh_btn)
        selector_row.addStretch()
        card_layout.addLayout(selector_row)

        hint = BodyLabel("以下显示所选学校的专业-学院映射，如未显示可先导入 Excel。")
        hint.setStyleSheet("color: #7a7a7a;")
        card_layout.addWidget(hint)
        card_layout.addWidget(self.school_major_list)

        return card

    def _build_backup_card(self) -> QWidget:
        card, card_layout = create_card()
        card_layout.addWidget(make_section_title("备份管理"))

        btn_row = QHBoxLayout()
        refresh_btn = PushButton("刷新列表")
        refresh_btn.clicked.connect(self._refresh_backup_list)
        self.verify_btn.clicked.connect(self._verify_selected_backup)
        self.restore_btn.clicked.connect(self._restore_selected_backup)
        self.restore_btn.setEnabled(False)
        self.verify_btn.setEnabled(False)
        btn_row.addWidget(refresh_btn)
        btn_row.addWidget(self.verify_btn)
        btn_row.addWidget(self.restore_btn)
        btn_row.addStretch()
        card_layout.addLayout(btn_row)

        self.backup_list.setMinimumHeight(200)
        self.backup_list.itemSelectionChanged.connect(self._on_backup_selected)
        card_layout.addWidget(self.backup_list)
        return card

    def _build_award_import_card(self) -> QWidget:
        card, card_layout = create_card()
        card_layout.addWidget(make_section_title("数据导入 / 导出"))

        btn_row = QHBoxLayout()
        self.award_import_btn = PrimaryPushButton("导入荣誉 (CSV/XLSX)")
        self.award_import_btn.clicked.connect(self._import_awards)
        self.award_export_btn = PushButton("导出全部荣誉 (CSV)")
        self.award_export_btn.clicked.connect(self._export_awards)
        btn_row.addWidget(self.award_import_btn)
        btn_row.addWidget(self.award_export_btn)

        self.award_dry_run = CheckBox("仅预检（不写入数据库）")
        self.award_dry_run.setChecked(False)
        btn_row.addWidget(self.award_dry_run)
        btn_row.addStretch()
        card_layout.addLayout(btn_row)

        log_header = QHBoxLayout()
        log_header.addWidget(BodyLabel("最近导入记录（含预检）"))
        refresh = PushButton("刷新")
        refresh.clicked.connect(self._refresh_import_log)
        log_header.addStretch()
        log_header.addWidget(refresh)
        card_layout.addLayout(log_header)

        self.import_log_list.setMinimumHeight(160)
        card_layout.addWidget(self.import_log_list)
        return card

    def _build_index_card(self) -> QWidget:
        card, card_layout = create_card()
        card_layout.addWidget(make_section_title("索引维护"))

        hint = BodyLabel("若搜索结果异常，可重建全文索引（荣誉/成员）。")
        hint.setStyleSheet("color: #7a7a7a;")
        card_layout.addWidget(hint)

        row = QHBoxLayout()
        self.rebuild_fts_btn = PrimaryPushButton("重建全文索引")
        self.rebuild_fts_btn.clicked.connect(self._rebuild_fts)
        row.addWidget(self.rebuild_fts_btn)
        row.addStretch()
        card_layout.addLayout(row)
        return card

    def _build_cleanup_card(self) -> QWidget:
        card, card_layout = create_card()
        card_layout.addWidget(make_section_title("清理工具"))

        hint = BodyLabel("危险操作，执行前请确认已手动备份。")
        hint.setStyleSheet("color: #d32f2f;")
        card_layout.addWidget(hint)

        btn_row = QHBoxLayout()
        clear_log_btn = PushButton("清空日志缓存")
        clear_log_btn.clicked.connect(self._clear_logs)
        clear_backup_btn = PushButton("清空备份目录")
        clear_backup_btn.clicked.connect(self._clear_backups)
        clear_db_btn = PushButton("清空数据库")
        clear_db_btn.clicked.connect(self._clear_database)
        clear_all_btn = PrimaryPushButton("一键清空 (日志+备份+数据库)")
        clear_all_btn.clicked.connect(self._clear_all)
        btn_row.addWidget(clear_log_btn)
        btn_row.addWidget(clear_backup_btn)
        btn_row.addWidget(clear_db_btn)
        btn_row.addWidget(clear_all_btn)
        btn_row.addStretch()
        card_layout.addLayout(btn_row)
        return card

    def _format_size(self, size: int) -> str:
        size_f = float(size)
        for unit in ("B", "KB", "MB", "GB"):
            if size_f < 1024:
                return f"{size_f:.1f} {unit}"
            size_f /= 1024
        return f"{size_f:.1f} TB"

    def _refresh_backup_list(self) -> None:
        self.backup_list.clear()
        backups = self.ctx.backup.list_backups()
        if not backups:
            self.backup_list.addItem("暂无备份，请点击“立即备份”。")
            self.restore_btn.setEnabled(False)
            self.verify_btn.setEnabled(False)
            return

        for info in backups:
            status = "✓有效" if info.is_valid else "✕损坏"
            time_str = info.created_time.strftime("%Y-%m-%d %H:%M")
            text = f"{info.path.name} | {time_str} | {self._format_size(info.size)} | {status}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, info)
            if not info.is_valid:
                item.setForeground(Qt.GlobalColor.red)
            self.backup_list.addItem(item)
        self._on_backup_selected()

    def _on_backup_selected(self) -> None:
        has_selection = bool(self.backup_list.selectedItems())
        self.restore_btn.setEnabled(has_selection)
        self.verify_btn.setEnabled(has_selection)

    def _refresh_import_log(self) -> None:
        self.import_log_list.clear()
        jobs = self.ctx.importer.list_jobs(limit=30)
        if not jobs:
            self.import_log_list.addItem("暂无导入记录。")
            return
        for job in jobs:
            status = job.status or "unknown"
            title = f"{job.filename} | {status}"
            if job.created_at:
                title += f" | {job.created_at.strftime('%Y-%m-%d %H:%M')}"
            if job.message:
                title += f" | {job.message.splitlines()[0][:60]}"
            item = QListWidgetItem(title)
            if status != "success":
                item.setForeground(Qt.GlobalColor.darkYellow)
            self.import_log_list.addItem(item)

    def _verify_selected_backup(self) -> None:
        item = self.backup_list.currentItem()
        if not item:
            InfoBar.info("提示", "请先选择一个备份", parent=self.window())
            return
        info = item.data(Qt.ItemDataRole.UserRole)
        ok, message = self.ctx.backup.verify_backup(info.path)
        if ok:
            InfoBar.success("验证通过", f"{info.path.name} 完整有效", parent=self.window())
        else:
            InfoBar.error("验证失败", message or "备份文件损坏", parent=self.window())
        self._refresh_backup_list()

    def _restore_selected_backup(self) -> None:
        item = self.backup_list.currentItem()
        if not item:
            InfoBar.info("提示", "请先选择一个备份", parent=self.window())
            return
        info = item.data(Qt.ItemDataRole.UserRole)
        box = MessageBox(
            "确认恢复",
            f"将从备份 {info.path.name} 覆盖当前数据库和附件/日志。\n此操作不可撤销，建议先备份当前数据。是否继续？",
            self.window(),
        )
        auto_backup = CheckBox("恢复前自动备份当前数据")
        auto_backup.setChecked(True)
        layout = box.layout()
        if layout is not None:
            layout.addWidget(auto_backup)
        if not box.exec():
            return

        try:
            if auto_backup.isChecked():
                new_backup = self.ctx.backup.perform_backup()
                InfoBar.success("已备份当前数据", str(new_backup), duration=2000, parent=self.window())
            self.ctx.backup.restore_backup(info.path)
            InfoBar.success("已恢复", f"已从 {info.path.name} 恢复数据", parent=self.window())
        except Exception as exc:
            self.logger.exception("Restore backup failed: %s", exc)
            InfoBar.error("恢复失败", str(exc), parent=self.window())

    def _clear_logs(self) -> None:
        box = MessageBox(
            "清空日志",
            "将删除 logs 目录下的所有文件，操作不可恢复。是否继续？",
            self.window(),
        )
        if not box.exec():
            return
        self._do_clear_logs()

    def _do_clear_logs(self) -> None:
        try:
            logging.shutdown()  # 释放文件句柄
            if LOG_DIR.exists():
                for path in sorted(LOG_DIR.rglob("*"), key=lambda p: len(p.parts), reverse=True):
                    if path.is_file():
                        try:
                            path.unlink()
                        except PermissionError:
                            with suppress(Exception):
                                path.write_text("", encoding="utf-8")
                    elif path.is_dir():
                        with suppress(Exception):
                            path.rmdir()
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            InfoBar.success("完成", "日志缓存已清空", parent=self.window())
        except Exception as exc:
            self.logger.exception("Clear logs failed: %s", exc)
            InfoBar.error("清理失败", str(exc), parent=self.window())

    def _double_confirm(self, title: str, text: str) -> bool:
        first = MessageBox(title, text, self.window())
        if not first.exec():
            return False
        second = MessageBox("请再次确认", "此操作不可撤销，确定继续吗？", self.window())
        return bool(second.exec())

    def _clear_backups(self) -> None:
        if not self._double_confirm("清空备份", "将删除备份目录下所有文件。"):
            return
        self._do_clear_backups()

    def _do_clear_backups(self) -> None:
        try:
            root = self.ctx.backup.backup_root
            if root.exists():
                for path in sorted(root.iterdir(), key=lambda p: len(p.parts), reverse=True):
                    if path.is_file():
                        with suppress(Exception):
                            path.unlink()
                    elif path.is_dir():
                        with suppress(Exception):
                            shutil.rmtree(path)
            InfoBar.success("完成", "备份文件已清空", parent=self.window())
            self._refresh_backup_list()
        except Exception as exc:
            self.logger.exception("Clear backups failed: %s", exc)
            InfoBar.error("清理失败", str(exc), parent=self.window())

    def _clear_database(self) -> None:
        if not self._double_confirm(
            "清空数据库",
            (
                "将删除 awards.db 并重建空库，数据将全部丢失。<br><br>"
                "<span style='color:#d32f2f; font-weight:700; font-size: 20px;'>"
                "本操作会删除：<br>所有荣誉/成员、附件记录、设置项、备份记录、学校与专业及映射、导入记录等。<br><br>请谨慎操作！"
                "</span>"
            ),
        ):
            return
        self._do_clear_database()

    def _do_clear_database(self) -> None:
        try:
            self.ctx.db.engine.dispose()
            with suppress(FileNotFoundError):
                DB_PATH.unlink()
            self.ctx.db.initialize()
            InfoBar.success("完成", "数据库已清空并重建", parent=self.window())
        except Exception as exc:
            self.logger.exception("Clear database failed: %s", exc)
            InfoBar.error("清理失败", str(exc), parent=self.window())

    def _clear_all(self) -> None:
        if not self._double_confirm(
            "一键清空",
            (
                "将依次清空日志、备份目录并重建空数据库，所有数据都会被删除。<br><br>"
                "<span style='color:#d32f2f; font-weight:700;font-size: 20px'>此操作不可撤销，请确保已另行备份，使用此功能请不要依赖软件备份。</span>"
            ),
        ):
            return
        errors: list[str] = []
        try:
            self._do_clear_logs()
        except Exception as exc:  # pragma: no cover - UI path
            errors.append(f"日志：{exc}")
        try:
            self._do_clear_backups()
        except Exception as exc:
            errors.append(f"备份：{exc}")
        try:
            self._do_clear_database()
        except Exception as exc:
            errors.append(f"数据库：{exc}")

        if errors:
            InfoBar.warning("部分失败", "；".join(errors), parent=self.window())
        else:
            InfoBar.success("完成", "已清空日志、备份并重建数据库", parent=self.window())

    def _rebuild_fts(self) -> None:
        btn = self.rebuild_fts_btn
        if btn:
            btn.setDisabled(True)
        try:
            awards, members = self.ctx.db.rebuild_fts()
            InfoBar.success(
                "索引已重建",
                f"荣誉 {awards} 条，成员 {members} 条",
                parent=self.window(),
            )
        except Exception as exc:
            self.logger.exception("Rebuild FTS failed: %s", exc)
            InfoBar.error("重建失败", str(exc), parent=self.window())
        finally:
            if btn:
                btn.setDisabled(False)

    def _import_awards(self) -> None:
        start_dir = Path(self.ctx.settings.get("last_import_dir", "data")).resolve()
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择荣誉数据文件 (CSV/XLSX)",
            str(start_dir),
            "数据文件 (*.csv *.xlsx)",
        )
        if not file_path:
            return
        path = Path(file_path)
        self.ctx.settings.set("last_import_dir", str(path.parent))
        dry_run = bool(self.award_dry_run and self.award_dry_run.isChecked())

        if self._import_busy:
            InfoBar.info("正在导入", "请等待当前导入完成", parent=self.window())
            return

        progress_queue: SimpleQueue[int | tuple[str, object] | tuple[int, int, float]] = SimpleQueue()
        progress = {"processed": 0, "total": 0, "eta": 0.0}
        progress_timer = QTimer(self)
        progress_timer.setInterval(200)
        finished = {"done": False}
        done_token = "__done__"

        def poll_queue() -> None:
            if self._progress_dialog is None:
                return
            updated = False
            while True:
                try:
                    value = progress_queue.get_nowait()
                except Empty:
                    break
                if isinstance(value, tuple) and value and value[0] == done_token:
                    finalize(value[1])
                    return
                if isinstance(value, tuple) and len(value) == 3 and all(isinstance(v, (int, float)) for v in value):
                    progress["processed"], progress["total"], progress["eta"] = (
                        int(value[0]),
                        int(value[1]),
                        float(value[2]),
                    )
                    updated = True
                elif isinstance(value, int):
                    progress["processed"] = value
                    updated = True
            if updated:
                eta_text = ""
                if progress["eta"] > 0:
                    eta_text = f"；预计剩余 {progress['eta']:.1f} 秒"
                base = f"已处理 {progress['processed']} 条"
                if progress["total"]:
                    base += f" / {progress['total']} 条"
                self._progress_dialog.setLabelText(f"正在导入… {base}{eta_text}")

        def finalize(result: object) -> None:
            if finished["done"]:
                return
            finished["done"] = True
            progress_timer.stop()
            self._set_import_busy(False)
            if isinstance(result, Exception):
                self.logger.error("荣誉导入失败：%s", result)
                InfoBar.error("导入失败", str(result), parent=self.window())
                return
            if not isinstance(result, ImportResult):
                InfoBar.error("导入失败", "未知错误，请查看日志。", parent=self.window())
                return
            if result.failed == 0:
                InfoBar.success("导入完成", f"成功 {result.success} 条", parent=self.window())
            else:
                msg = f"成功 {result.success} 条，失败 {result.failed} 条"
                if result.error_file:
                    msg += f"（错误行已导出到 {result.error_file.name}）"
                InfoBar.warning("导入部分成功", msg, parent=self.window())
            self._refresh_import_log()

        def worker():
            def progress_cb(processed: int, total: int, eta: float) -> None:
                progress_queue.put((processed, total, eta))

            try:
                result = self.ctx.importer.import_from_file(path, progress_callback=progress_cb, dry_run=dry_run)
                progress_queue.put((done_token, result))
            except Exception as exc:
                progress_queue.put((done_token, exc))

        self._set_import_busy(True, "正在导入…")
        progress_timer.timeout.connect(poll_queue)
        progress_timer.start()
        threading.Thread(target=worker, daemon=True).start()

    def _export_awards(self) -> None:
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出全部荣誉",
            str(Path("exports/awards.csv").resolve()),
            "CSV 文件 (*.csv);;Excel 文件 (*.xlsx)",
        )
        if not save_path:
            return
        path = Path(save_path)
        try:
            awards = self.ctx.awards.list_awards()
            exported = self.ctx.importer.export_awards(path, awards)
            InfoBar.success("已导出", exported.name, parent=self.window())
        except Exception as exc:
            self.logger.exception("Export awards failed: %s", exc)
            InfoBar.error("导出失败", str(exc), parent=self.window())

    def _create_stat_block(self, title: str, value_label: QLabel) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        value_label.setStyleSheet("font-size: 22px; font-weight: 600;")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        caption = QLabel(title)
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        caption.setStyleSheet("color: #6c6c6c; font-size: 12px;")
        layout.addWidget(value_label)
        layout.addWidget(caption)
        return wrapper

    def _set_import_busy(self, busy: bool, message: str | None = None) -> None:
        self._import_busy = busy
        for btn in (
            self.school_import_btn,
            self.major_import_btn,
            self.mapping_import_btn,
            self.award_import_btn,
            self.award_export_btn,
        ):
            if btn is not None:
                btn.setDisabled(busy)
        if self.award_dry_run is not None:
            self.award_dry_run.setDisabled(busy)
        if busy:
            if self._progress_dialog is None:
                self._progress_dialog = QProgressDialog("正在导入数据…", "", 0, 0, self)
                self._progress_dialog.setWindowTitle("处理中")
                self._progress_dialog.setCancelButton(None)
                self._progress_dialog.setMinimumWidth(360)
                self._progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            if message:
                self._progress_dialog.setLabelText(message)
            self._progress_dialog.show()
        else:
            if self._progress_dialog is not None:
                self._progress_dialog.hide()
                self._progress_dialog.deleteLater()
                self._progress_dialog = None

    def _run_import_task(self, worker_factory, description: str) -> None:
        if self._import_busy:
            InfoBar.info("正在导入", "请等待当前导入完成", parent=self.window())
            return

        progress_queue: SimpleQueue[int | tuple[str, object]] = SimpleQueue()
        latest_progress = {"value": 0}
        progress_timer = QTimer(self)
        progress_timer.setInterval(200)
        finished = {"done": False}

        def finalize(result: object) -> None:
            if finished["done"]:
                return
            finished["done"] = True
            if self._progress_dialog is None:
                self.logger.warning("进度对话框已不存在：%s", description)
            progress_timer.stop()
            self._set_import_busy(False)
            if isinstance(result, Exception):
                self.logger.error("导入任务失败：%s", result)
                InfoBar.error("导入失败", str(result), parent=self.window())
                return
            if not result or not isinstance(result, tuple) or len(result) != 4:
                self.logger.error("导入任务返回异常：%s", result)
                InfoBar.error("导入失败", "执行出现异常，请查看日志。", parent=self.window())
                return
            status, title, message, refresh = result
            bar = {
                "success": InfoBar.success,
                "warning": InfoBar.warning,
                "error": InfoBar.error,
                "info": InfoBar.info,
            }.get(status, InfoBar.info)
            bar(title, message, parent=self.window())
            if refresh:
                self._refresh_academic_stats()
            self.logger.info("导入任务清理完成：%s", description)

        done_token = "__done__"

        def poll_queue() -> None:
            if self._progress_dialog is None:
                return
            updated = False
            while True:
                try:
                    value = progress_queue.get_nowait()
                except Empty:
                    break
                if isinstance(value, tuple) and value and value[0] == done_token:
                    self.logger.info("收到导入完成信号：%s", description)
                    finalize(value[1])
                    return
                if isinstance(value, int):
                    latest_progress["value"] = value
                    updated = True
            if updated:
                base_text = description or "正在导入…"
                extra = f"\n已处理 {latest_progress['value']} 条…" if latest_progress["value"] else ""
                self._progress_dialog.setLabelText(base_text + extra)

        progress_timer.timeout.connect(poll_queue)

        def worker():
            def progress_report(value: int) -> None:
                progress_queue.put(value)
                self.logger.debug("%s progress -> %d", description, value)

            self.logger.info("导入线程启动：%s (thread_id=%s)", description, threading.get_ident())
            try:
                result = worker_factory(progress_report)
                self.logger.info("导入线程完成：%s -> %s", description, type(result).__name__)
                progress_queue.put((done_token, result))
            except Exception as exc:
                self.logger.error("导入线程异常：%s", exc)
                progress_queue.put((done_token, exc))

        self.logger.info("开始导入任务：%s", description)
        self._set_import_busy(True, description)
        InfoBar.info("处理中", description, parent=self.window())
        progress_timer.start()
        threading.Thread(target=worker, daemon=True).start()

    def _import_school_list(self) -> None:
        default_csv = self._get_docs_path("china_universities_2025.csv")
        start_dir = default_csv if default_csv.exists() else default_csv.parent
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择学校 CSV 文件",
            str(start_dir),
            "CSV 文件 (*.csv)",
        )
        if not file_path:
            return

        csv_path = Path(file_path)

        def task(progress_callback):
            try:
                records = read_school_list(csv_path)
            except Exception as error:
                return ("error", "读取失败", f"无法解析 CSV：{error}", False)

            if not records:
                return ("warning", "无数据", "文件中未找到学校记录", False)

            try:
                self.logger.info("导入学校列表：%s，共 %d 条", csv_path.name, len(records))
                count = self.ctx.schools.replace_all(records, progress_callback=progress_callback)
            except Exception as error:
                return ("error", "写入失败", f"导入学校失败：{error}", False)

            progress_callback(count)
            self.logger.info("学校导入完成：%s，成功 %d 条", csv_path.name, count)
            return ("success", "导入完成", f"成功导入 {count} 所学校", True)

        self._run_import_task(task, "正在导入学校列表…")

    def _import_major_catalog(self) -> None:
        default_csv = self._get_docs_path("china_bachelor_majors_2025.csv")
        start_dir = default_csv if default_csv.exists() else default_csv.parent
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择专业目录 CSV",
            str(start_dir),
            "CSV 文件 (*.csv)",
        )
        if not file_path:
            return

        csv_path = Path(file_path)

        def task(progress_callback):
            try:
                records = read_major_catalog_from_csv(csv_path)
            except Exception as error:
                return ("error", "读取失败", f"无法解析 CSV：{error}", False)

            if not records:
                return ("warning", "无数据", "文件未包含任何专业记录", False)

            try:
                self.logger.info("导入专业目录：%s，共 %d 条", csv_path.name, len(records))
                count = self.ctx.majors.replace_all_majors(records, progress_callback=progress_callback)
            except Exception as error:
                return ("error", "写入失败", f"导入专业目录失败：{error}", False)

            self.logger.info("专业目录导入完成：%s，成功 %d 条", csv_path.name, count)
            return ("success", "导入完成", f"成功导入 {count} 个专业", True)

        self._run_import_task(task, "正在导入专业目录…")

    def _import_school_major_mapping(self) -> None:
        default_excel = self._get_docs_path("GSAU_majors.xlsx")
        start_dir = default_excel if default_excel.exists() else default_excel.parent
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择学校-专业映射 Excel",
            str(start_dir),
            "Excel 文件 (*.xlsx)",
        )
        if not file_path:
            return

        excel_path = Path(file_path)

        def task(progress_callback):
            try:
                mappings = read_majors_from_excel(excel_path)
            except ModuleNotFoundError as error:
                if error.name == "openpyxl":
                    return ("error", "缺少依赖", "请先安装 openpyxl，再重试导入", False)
                return ("error", "导入失败", str(error), False)
            except Exception as error:
                return ("error", "读取失败", f"无法解析 Excel：{error}", False)

            if not mappings:
                return ("warning", "无数据", "文件未包含学校-专业映射", False)

            try:
                total_rows = len(mappings)
                self.logger.info("导入学校-专业映射：%s，共 %d 条", excel_path.name, total_rows)
                inserted, updated = self.ctx.majors.upsert_school_major_mappings(
                    mappings,
                    progress_callback=progress_callback,
                )
            except Exception as error:
                return ("error", "写入失败", f"导入映射失败：{error}", False)

            message = f"新增 {inserted} 条，更新 {updated} 条专业映射"
            progress_callback(inserted + updated)
            self.logger.info(
                "学校-专业映射导入完成：%s，新增 %d 条，更新 %d 条",
                excel_path.name,
                inserted,
                updated,
            )
            return ("success", "导入完成", message, True)

        self._run_import_task(task, "正在导入学校-专业映射…")

    def _get_docs_path(self, filename: str) -> Path:
        return Path(__file__).resolve().parents[3] / "docs" / filename

    def _refresh_academic_stats(self) -> None:
        school_stats = self.ctx.schools.get_statistics()
        major_stats = self.ctx.majors.get_statistics()

        self.school_total_value.setText(str(school_stats.get("total", 0)))
        self.school_with_code_value.setText(str(school_stats.get("with_code", 0)))
        self.major_total_value.setText(str(major_stats.get("library_total", 0)))
        self.mapping_total_value.setText(str(major_stats.get("school_mapping_total", 0)))
        self.college_total_value.setText(str(major_stats.get("college_count", 0)))
        self._refresh_region_selector()
        self._refresh_school_selector()

    def _refresh_region_selector(self) -> None:
        current_index = self.region_selector.currentIndex()
        current_region = None
        if 0 <= current_index < len(self._region_options):
            current_region = self._region_options[current_index]

        regions = self._sort_regions(self.ctx.schools.get_regions())
        self.region_selector.blockSignals(True)
        self.region_selector.clear()
        self._region_options = [None]
        self.region_selector.addItem("全部地区")
        for region in regions:
            self.region_selector.addItem(region)
            self._region_options.append(region)
        target_index = 0
        if current_region in self._region_options:
            target_index = self._region_options.index(current_region)
        self.region_selector.setCurrentIndex(target_index)
        self.region_selector.blockSignals(False)

    def _refresh_school_selector(self) -> None:
        current_index = self.school_selector.currentIndex()
        current_selection: tuple[str | None, str | None] | None = None
        if 0 <= current_index < len(self._school_options):
            current_selection = self._school_options[current_index]

        region_index = self.region_selector.currentIndex()
        region_value = None
        if 0 <= region_index < len(self._region_options):
            region_value = self._region_options[region_index]

        schools = self.ctx.schools.list_by_region(region_value) if region_value else self.ctx.schools.get_all()
        self.school_selector.blockSignals(True)
        self.school_selector.clear()
        self._school_options = [(None, None)]
        self.school_selector.addItem("全部学校")
        for school in schools:
            label = f"{school.name}（{school.code}）" if school.code else school.name
            self.school_selector.addItem(label)
            self._school_options.append((school.name, school.code))
        target_index = 0
        if current_selection and current_selection in self._school_options:
            target_index = self._school_options.index(current_selection)
        self.school_selector.setCurrentIndex(target_index)
        self.school_selector.blockSignals(False)
        self._load_school_major_list()

    def _sort_regions(self, regions: list[str]) -> list[str]:
        return sorted(regions, key=lambda name: "".join(lazy_pinyin(name or "")).lower())

    def _on_region_changed(self) -> None:
        self._refresh_school_selector()

    def _load_school_major_list(self) -> None:
        self.school_major_list.clear()
        index = self.school_selector.currentIndex()
        if index <= 0 or index >= len(self._school_options):
            self.school_major_list.addItem("请选择具体学校以查看专业-学院映射。")
            return

        school_name, school_code = self._school_options[index]
        records = self.ctx.majors.get_school_major_list(school_code=school_code, school_name=school_name)
        if not records:
            self.school_major_list.addItem("该学校尚未导入映射，可点击上方按钮导入 Excel。")
            return

        truncated = False
        total_count = len(records)
        if total_count > self.MAX_MAJOR_DISPLAY:
            records = records[: self.MAX_MAJOR_DISPLAY]
            truncated = True

        for mapping in records:
            code = mapping.major_code or "未提供代码"
            college = mapping.college_name or "未设置学院"
            category = f" · {mapping.category}" if mapping.category else ""
            text = f"{mapping.major_name}（{code}） - {college}{category}"
            self.school_major_list.addItem(text)
        if truncated:
            self.school_major_list.addItem(f"…… 仅显示前 {self.MAX_MAJOR_DISPLAY} 条，共 {total_count} 条")
