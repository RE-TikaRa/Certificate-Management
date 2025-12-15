import logging
import shutil
import threading
from contextlib import suppress
from pathlib import Path
from queue import Empty, SimpleQueue
from typing import Any, ClassVar

from pypinyin import lazy_pinyin
from PySide6.QtCore import QProcess, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QIntValidator
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QProgressBar,
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
    MaskDialogBase,
    MessageBox,
    PrimaryPushButton,
    PushButton,
)

from src.config import BASE_DIR, DB_PATH, LOG_DIR
from src.mcp_runtime import get_mcp_runtime
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


class UvSyncDialog(MaskDialogBase):
    def __init__(
        self,
        parent,
        *,
        title: str,
        workdir: str,
        program: str,
        args: list[str],
        log_path: Path,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.widget.setMinimumWidth(720)
        self.widget.setMaximumWidth(920)
        self._workdir = workdir
        self._program = program
        self._sync_args = args
        self._check_args = [*args, "--check"]
        self._log_path = log_path
        self._process = QProcess(self)
        self._process.setWorkingDirectory(workdir)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_output)
        self._process.finished.connect(self._on_finished)

        self._log_fp: Any = None
        self._running = False
        self._mode: str = "idle"  # idle|check|sync

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self.widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        header = create_page_header("安装/更新 Web 依赖", "先检查是否需要更新，再按需同步（实时输出）")
        layout.addWidget(header)

        card, card_layout = create_card()
        card_layout.setSpacing(10)

        self.status = BodyLabel("准备中…")
        self.status.setStyleSheet("color: #7a7a7a;")
        card_layout.addWidget(self.status)

        self.progress = QProgressBar(self.widget)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        card_layout.addWidget(self.progress)

        self.output = QPlainTextEdit(self.widget)
        self.output.setReadOnly(True)
        self.output.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.output.setMinimumHeight(260)
        card_layout.addWidget(self.output)

        layout.addWidget(card)

        btn_row = QHBoxLayout()
        self.open_log_btn = PushButton("打开日志文件")
        self.open_log_btn.clicked.connect(self._open_log)
        self.sync_btn = PrimaryPushButton("开始更新")
        self.sync_btn.setEnabled(False)
        self.sync_btn.clicked.connect(self._run_sync)
        self.force_btn = PushButton("强制同步")
        self.force_btn.setEnabled(False)
        self.force_btn.clicked.connect(lambda: self._run_sync(force=True))
        self.cancel_btn = PushButton("取消")
        self.cancel_btn.clicked.connect(self._cancel)
        self.close_btn = PrimaryPushButton("关闭")
        self.close_btn.setEnabled(False)
        self.close_btn.clicked.connect(self.close)
        btn_row.addWidget(self.open_log_btn)
        btn_row.addWidget(self.force_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.sync_btn)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.close_btn)
        layout.addLayout(btn_row)

    def start(self) -> None:
        self._run_check()

    def _run_check(self) -> None:
        if self._running:
            return
        self._mode = "check"
        self._running = True
        self._open_run()
        self.sync_btn.setEnabled(False)
        self.force_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.status.setText(f"检查中：{self._program} {' '.join(self._check_args)}")
        self._process.start(self._program, self._check_args)

    def _run_sync(self, force: bool = False) -> None:
        if self._running:
            return
        self._mode = "sync"
        self._running = True
        self._open_run(clear=not force)
        self.sync_btn.setEnabled(False)
        self.force_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.status.setText(f"更新中：{self._program} {' '.join(self._sync_args)}")
        self._process.start(self._program, self._sync_args)

    def _open_run(self, *, clear: bool = True) -> None:
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_fp = self._log_path.open("ab")
        if clear:
            self.output.clear()
        self.progress.setRange(0, 0)

    def _append(self, text: str) -> None:
        if not text:
            return
        self.output.appendPlainText(text.rstrip("\n"))
        cursor = self.output.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.output.setTextCursor(cursor)
        if self._log_fp:
            with suppress(Exception):
                self._log_fp.write(text.encode("utf-8", errors="replace"))
                self._log_fp.flush()

    def _on_output(self) -> None:
        raw = self._process.readAllStandardOutput().data()
        data = bytes(raw)
        if not data:
            return
        self._append(data.decode("utf-8", errors="replace"))

    def _on_finished(self, code: int, _status: QProcess.ExitStatus) -> None:
        mode = self._mode
        self._mode = "idle"
        self._running = False
        if self._log_fp:
            with suppress(Exception):
                self._log_fp.close()
        self._log_fp = None
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.cancel_btn.setEnabled(False)
        self.close_btn.setEnabled(True)

        if mode == "check":
            if code == 0:
                self.status.setText("已是最新：环境已同步，无需更新（基于 uv.lock）")
                self.force_btn.setEnabled(True)
                self.sync_btn.setEnabled(False)
            else:
                self.status.setText("检测到环境未同步：可点击“开始更新”进行同步")
                self.sync_btn.setEnabled(True)
                self.force_btn.setEnabled(True)
            return

        if code == 0:
            self.status.setText("完成：依赖已安装/更新")
        else:
            self.status.setText(f"失败：返回码 {code}（可打开日志查看详情）")

    def _cancel(self) -> None:
        if not self._running:
            return
        self.status.setText("正在取消…")
        self._process.terminate()
        QTimer.singleShot(1500, lambda: self._process.kill() if self._running else None)

    def _open_log(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._log_path)))

    def closeEvent(self, event) -> None:
        if self._running:
            self._cancel()
        super().closeEvent(event)


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
        self.flag_rows: list[dict] = []
        self.mcp_allow_write = CheckBox("允许写操作（需重启 MCP 进程，谨慎开启）")
        self.mcp_redact_pii = CheckBox("成员敏感信息脱敏（建议开启）")
        self.mcp_max_bytes = LineEdit()
        self.mcp_max_bytes.setPlaceholderText("默认 1048576（1MB，单位：字节）")
        self.mcp_max_bytes.setValidator(QIntValidator(1, 50_000_000, self))
        self.mcp_auto_start = CheckBox("启动软件时自动启动 MCP（仅本地）")
        self.mcp_port = LineEdit()
        self.mcp_port.setPlaceholderText("默认 8000")
        self.mcp_port.setValidator(QIntValidator(1, 65535, self))
        self.mcp_web_auto_start = CheckBox("启动软件时自动启动 MCP Web 控制台")
        self.mcp_web_host = LineEdit()
        self.mcp_web_host.setPlaceholderText("默认 127.0.0.1")
        self.mcp_web_port = LineEdit()
        self.mcp_web_port.setPlaceholderText("默认 7860")
        self.mcp_web_port.setValidator(QIntValidator(1, 65535, self))
        self.mcp_web_username = LineEdit()
        self.mcp_web_username.setPlaceholderText("例如：local 或 user-xxxx")
        self.mcp_web_token = LineEdit()
        self.mcp_web_token.setReadOnly(True)
        self._mcp_web_regen_user_btn = PushButton("随机用户名")
        self._mcp_web_regen_token_btn = PushButton("重新生成密码")
        self._mcp_web_install_btn = PushButton("安装/更新 Web 依赖（uv）")
        self._mcp_web_install_dialog: UvSyncDialog | None = None

        self._mcp_runtime = get_mcp_runtime(self.ctx)
        self._mcp_status = BodyLabel("MCP：未运行")
        self._mcp_web_status = BodyLabel("MCP Web：未运行")
        self._mcp_start_btn = PrimaryPushButton("启动 MCP")
        self._mcp_stop_btn = PushButton("停止 MCP")
        self._mcp_log_btn = PushButton("打开 MCP 日志")
        self._web_start_btn = PrimaryPushButton("启动 Web 控制台")
        self._web_stop_btn = PushButton("停止 Web 控制台")
        self._web_open_btn = PushButton("打开 Web 页面")
        self._web_log_btn = PushButton("打开 Web 日志")
        self._process_timer = QTimer(self)
        self._process_timer.setInterval(1000)
        self._process_timer.timeout.connect(self._refresh_process_status)
        self._mcp_refreshing = False

        self._build_ui()
        self.refresh()
        self._process_timer.start()
        self._refresh_process_status()
        self._connect_mcp_signals()

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
        layout.addWidget(self._build_mcp_card())
        layout.addWidget(self._build_cleanup_card())
        layout.addWidget(self._build_flags_card())
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
        # MCP
        self._mcp_refreshing = True
        try:
            allow_write = self.ctx.settings.get("mcp_allow_write", "false") == "true"
            self.mcp_allow_write.setChecked(allow_write)
            self.mcp_redact_pii.setChecked(self.ctx.settings.get("mcp_redact_pii", "true") == "true")
            self.mcp_max_bytes.setText(self.ctx.settings.get("mcp_max_bytes", "1048576"))
            self.mcp_auto_start.setChecked(self.ctx.settings.get("mcp_auto_start", "false") == "true")
            self.mcp_port.setText(self.ctx.settings.get("mcp_port", "8000"))
            self.mcp_web_auto_start.setChecked(self.ctx.settings.get("mcp_web_auto_start", "false") == "true")
            self.mcp_web_host.setText(self.ctx.settings.get("mcp_web_host", "127.0.0.1"))
            self.mcp_web_port.setText(self.ctx.settings.get("mcp_web_port", "7860"))
            self.mcp_web_username.setText(self.ctx.settings.get("mcp_web_username", self._mcp_runtime.web_username()))
            self.mcp_web_token.setText(self.ctx.settings.get("mcp_web_token", self._mcp_runtime.web_token()))
        finally:
            self._mcp_refreshing = False
        self._refresh_process_status()
        self._refresh_academic_stats()
        self._refresh_import_log()
        self._refresh_flags()

    def _connect_mcp_signals(self) -> None:
        for cb in (
            self.mcp_allow_write,
            self.mcp_redact_pii,
            self.mcp_auto_start,
            self.mcp_web_auto_start,
        ):
            cb.stateChanged.connect(lambda _=0: self._save_mcp_settings(silent=True))

        for le in (
            self.mcp_max_bytes,
            self.mcp_port,
            self.mcp_web_host,
            self.mcp_web_port,
            self.mcp_web_username,
        ):
            le.editingFinished.connect(lambda: self._save_mcp_settings(silent=True))

    def _save_mcp_settings(self, *, silent: bool = False) -> None:
        if self._mcp_refreshing:
            return
        try:
            self.ctx.settings.set("mcp_allow_write", str(self.mcp_allow_write.isChecked()).lower())
            self.ctx.settings.set("mcp_redact_pii", str(self.mcp_redact_pii.isChecked()).lower())

            max_bytes_text = self.mcp_max_bytes.text().strip() or "1048576"
            try:
                max_bytes_value = max(1024, int(max_bytes_text))
            except ValueError:
                max_bytes_value = 1_048_576
            self.ctx.settings.set("mcp_max_bytes", str(max_bytes_value))

            self.ctx.settings.set("mcp_auto_start", str(self.mcp_auto_start.isChecked()).lower())
            mcp_port_text = self.mcp_port.text().strip() or "8000"
            try:
                mcp_port_value = max(1, min(65535, int(mcp_port_text)))
            except ValueError:
                mcp_port_value = 8000
            self.ctx.settings.set("mcp_port", str(mcp_port_value))

            self.ctx.settings.set("mcp_web_auto_start", str(self.mcp_web_auto_start.isChecked()).lower())
            self.ctx.settings.set("mcp_web_host", self.mcp_web_host.text().strip() or "127.0.0.1")
            web_port_text = self.mcp_web_port.text().strip() or "7860"
            try:
                web_port_value = max(1, min(65535, int(web_port_text)))
            except ValueError:
                web_port_value = 7860
            self.ctx.settings.set("mcp_web_port", str(web_port_value))

            username = self.mcp_web_username.text().strip() or "local"
            self.ctx.settings.set("mcp_web_username", username)
            self._mcp_runtime.set_web_username(username)

            token = self.mcp_web_token.text().strip()
            if token:
                self.ctx.settings.set("mcp_web_token", token)

            if not silent:
                InfoBar.success("MCP", "MCP 设置已保存", parent=self.window())
        except Exception as exc:
            if not silent:
                InfoBar.error("MCP", f"MCP 设置保存失败：{exc}", parent=self.window())

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

            # MCP 设置（页面内已自动保存，这里兜底写一次）
            self._save_mcp_settings(silent=True)

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

    def _build_mcp_card(self) -> QWidget:
        card, card_layout = create_card()
        card_layout.addWidget(make_section_title("MCP 服务"))

        hint = BodyLabel(
            "本软件 MCP 仅供本地使用（localhost）。\n"
            "MCP 客户端可直接用 `uv run certificate-mcp`（stdio）启动；也可以在此页启动本地 SSE 服务（仅用于本机调试）。\n"
            "如需写操作或更大附件读取上限，在此勾选并重启 MCP 进程；也可通过环境变量临时覆盖。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #7a7a7a;")
        card_layout.addWidget(hint)

        form = QFormLayout()
        form.setSpacing(12)
        form.addRow(self.mcp_allow_write)
        form.addRow(self.mcp_redact_pii)
        form.addRow("附件读取上限（字节）", self.mcp_max_bytes)
        form.addRow(self.mcp_auto_start)
        form.addRow("MCP 端口（本地）", self.mcp_port)
        form.addRow(self.mcp_web_auto_start)
        form.addRow("Web Host", self.mcp_web_host)
        form.addRow("Web Port", self.mcp_web_port)
        user_row = QWidget()
        user_layout = QHBoxLayout(user_row)
        user_layout.setContentsMargins(0, 0, 0, 0)
        user_layout.addWidget(self.mcp_web_username, 1)
        user_layout.addWidget(self._mcp_web_regen_user_btn)
        form.addRow("Web 用户名", user_row)

        token_row = QWidget()
        token_layout = QHBoxLayout(token_row)
        token_layout.setContentsMargins(0, 0, 0, 0)
        token_layout.addWidget(self.mcp_web_token, 1)
        token_layout.addWidget(self._mcp_web_regen_token_btn)
        form.addRow("Web 密码", token_row)
        form.addRow(self._mcp_web_install_btn)
        card_layout.addLayout(form)

        status_layout = QVBoxLayout()
        self._mcp_status.setStyleSheet("color: #7a7a7a;")
        self._mcp_web_status.setStyleSheet("color: #7a7a7a;")
        status_layout.addWidget(self._mcp_status)
        status_layout.addWidget(self._mcp_web_status)
        card_layout.addLayout(status_layout)

        btn_row = QHBoxLayout()
        self._mcp_start_btn.clicked.connect(self._start_mcp)
        self._mcp_stop_btn.clicked.connect(self._stop_mcp)
        self._mcp_log_btn.clicked.connect(self._open_mcp_log)
        self._web_start_btn.clicked.connect(self._start_web)
        self._web_stop_btn.clicked.connect(self._stop_web)
        self._web_open_btn.clicked.connect(self._open_web)
        self._web_log_btn.clicked.connect(self._open_web_log)
        self._mcp_web_regen_user_btn.clicked.connect(self._regen_web_username)
        self._mcp_web_regen_token_btn.clicked.connect(self._regen_web_token)
        self._mcp_web_install_btn.clicked.connect(self._install_mcp_web_deps)
        btn_row.addWidget(self._mcp_start_btn)
        btn_row.addWidget(self._mcp_stop_btn)
        btn_row.addWidget(self._mcp_log_btn)
        btn_row.addSpacing(16)
        btn_row.addWidget(self._web_start_btn)
        btn_row.addWidget(self._web_stop_btn)
        btn_row.addWidget(self._web_open_btn)
        btn_row.addWidget(self._web_log_btn)
        btn_row.addStretch()
        card_layout.addLayout(btn_row)

        self._refresh_process_status()
        return card

    def _refresh_process_status(self) -> None:
        mcp = self._mcp_runtime.mcp_info()
        web = self._mcp_runtime.web_info()
        if mcp.running:
            self._mcp_status.setText(f"MCP：运行中（PID {mcp.pid}） {mcp.url or ''}".rstrip())
        else:
            self._mcp_status.setText("MCP：未运行")
        if web.running:
            self._mcp_web_status.setText(f"MCP Web：运行中（PID {web.pid}） {web.url or ''}".rstrip())
        else:
            self._mcp_web_status.setText("MCP Web：未运行")

        mcp_running = mcp.running
        web_running = web.running
        self._mcp_start_btn.setEnabled(not mcp_running)
        self._mcp_stop_btn.setEnabled(mcp_running)
        self._mcp_log_btn.setEnabled(True)
        self._web_start_btn.setEnabled(not web_running)
        self._web_stop_btn.setEnabled(web_running)
        self._web_open_btn.setEnabled(True)
        self._web_log_btn.setEnabled(True)

    def _start_mcp(self) -> None:
        try:
            port_text = self.mcp_port.text().strip() or "8000"
            port_value = max(1, min(65535, int(port_text)))
            max_bytes_text = self.mcp_max_bytes.text().strip() or "1048576"
            max_bytes_value = max(1024, int(max_bytes_text))
            self._mcp_runtime.start_mcp_sse(
                port=port_value,
                allow_write=self.mcp_allow_write.isChecked(),
                max_bytes=max_bytes_value,
            )
            InfoBar.success("MCP", f"已启动（本地）：{self._mcp_sse_url()}", parent=self.window())
        except Exception as exc:
            InfoBar.error("MCP", f"启动失败：{exc}", parent=self.window())
        finally:
            self._refresh_process_status()

    def _stop_mcp(self) -> None:
        try:
            self._mcp_runtime.stop_mcp()
            InfoBar.success("MCP", "已停止", parent=self.window())
        except Exception as exc:
            InfoBar.error("MCP", f"停止失败：{exc}", parent=self.window())
        finally:
            self._refresh_process_status()

    def _mcp_sse_url(self) -> str:
        port = self.mcp_port.text().strip() or "8000"
        return f"http://127.0.0.1:{port}/sse"

    def _start_web(self) -> None:
        try:
            import importlib.util

            if importlib.util.find_spec("gradio") is None:
                InfoBar.error("MCP Web", "未安装 gradio，请先执行：uv sync --group mcp-web", parent=self.window())
                return

            host = self.mcp_web_host.text().strip() or "127.0.0.1"
            port = self.mcp_web_port.text().strip() or "7860"
            self._mcp_runtime.start_web(host=host, port=int(port))
            InfoBar.success("MCP Web", "已启动", parent=self.window())
        except Exception as exc:
            InfoBar.error("MCP Web", f"启动失败：{exc}", parent=self.window())
        finally:
            self._refresh_process_status()

    def _stop_web(self) -> None:
        try:
            self._mcp_runtime.stop_web()
            InfoBar.success("MCP Web", "已停止", parent=self.window())
        except Exception as exc:
            InfoBar.error("MCP Web", f"停止失败：{exc}", parent=self.window())
        finally:
            self._refresh_process_status()

    def _regen_web_token(self) -> None:
        token = self._mcp_runtime.regenerate_web_token()
        self.mcp_web_token.setText(token)
        InfoBar.success("MCP Web", "密码已更新，重启 Web 控制台后生效", parent=self.window())

    def _regen_web_username(self) -> None:
        username = self._mcp_runtime.regenerate_web_username()
        self.mcp_web_username.setText(username)
        InfoBar.success("MCP Web", "用户名已更新，重启 Web 控制台后生效", parent=self.window())

    def _install_mcp_web_deps(self) -> None:
        if shutil.which("uv") is None:
            InfoBar.error("MCP Web", "未找到 uv，请先安装 uv", parent=self.window())
            return

        self._mcp_web_install_dialog = UvSyncDialog(
            self.window(),
            title="安装/更新 Web 依赖",
            workdir=str(BASE_DIR),
            program="uv",
            args=["-v", "sync", "--group", "mcp-web"],
            log_path=LOG_DIR / "mcp_web_install.log",
        )
        self._mcp_web_install_dialog.show()
        self._mcp_web_install_dialog.start()

    def _open_web(self) -> None:
        host = self.mcp_web_host.text().strip() or "127.0.0.1"
        port = self.mcp_web_port.text().strip() or "7860"
        QDesktopServices.openUrl(QUrl(f"http://{host}:{port}"))

    def _open_mcp_log(self) -> None:
        log_path = self._mcp_runtime.mcp_info().log_path
        if not log_path:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(log_path))

    def _open_web_log(self) -> None:
        log_path = self._mcp_runtime.web_info().log_path
        if not log_path:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(log_path))

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

    def _build_flags_card(self) -> QWidget:
        card, card_layout = create_card()
        card_layout.addWidget(make_section_title("自定义开关"))

        hint = BodyLabel("用于录入/导出/筛选的布尔开关，支持改名、启用、默认值、排序。")
        hint.setStyleSheet("color: #7a7a7a;")
        card_layout.addWidget(hint)

        # 标题行
        header = QHBoxLayout()
        add_btn = PrimaryPushButton("新增开关")
        add_btn.clicked.connect(self._add_flag_dialog)
        refresh_btn = PushButton("刷新")
        refresh_btn.clicked.connect(self._refresh_flags)
        header.addWidget(add_btn)
        header.addWidget(refresh_btn)
        header.addStretch()
        card_layout.addLayout(header)

        # 列头
        head_row = QHBoxLayout()
        head_row.setSpacing(8)
        head_row.addWidget(self._make_header_label("显示名", 180))
        head_row.addWidget(self._make_header_label("Key", 170))
        head_row.addWidget(self._make_header_label("默认勾选", 80))
        head_row.addWidget(self._make_header_label("启用", 60))
        head_row.addWidget(self._make_header_label("排序", 120))
        head_row.addWidget(self._make_header_label("操作", 120))
        card_layout.addLayout(head_row)

        self.flags_container = QWidget()
        self.flags_layout = QVBoxLayout(self.flags_container)
        self.flags_layout.setContentsMargins(0, 4, 0, 0)
        self.flags_layout.setSpacing(6)
        card_layout.addWidget(self.flags_container)

        return card

    def _make_header_label(self, text: str, width: int | None = None) -> QLabel:
        label = QLabel(text)
        if width:
            label.setMinimumWidth(width)
        label.setStyleSheet("color: #888; font-weight: 600;")
        return label

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

    # ---- 自定义开关 ----
    def _refresh_flags(self) -> None:
        # 清空布局
        while self.flags_layout.count():
            item = self.flags_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.flag_rows.clear()

        flags = self.ctx.flags.list_flags(enabled_only=False)
        for flag in flags:
            self._add_flag_row(flag)

        self.flags_layout.addStretch()

    def _add_flag_row(self, flag) -> None:
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        name_edit = LineEdit(parent=row_widget)
        name_edit.setText(flag.label)
        name_edit.setMinimumWidth(180)
        row_layout.addWidget(name_edit)

        key_label = QLabel(flag.key)
        key_label.setMinimumWidth(170)
        row_layout.addWidget(key_label)

        default_cb = CheckBox()
        default_cb.setChecked(bool(flag.default_value))
        row_layout.addWidget(default_cb)

        enabled_cb = CheckBox()
        enabled_cb.setChecked(bool(flag.enabled))
        row_layout.addWidget(enabled_cb)

        sort_row = QHBoxLayout()
        up_btn = PushButton("上移")
        down_btn = PushButton("下移")
        up_btn.setFixedWidth(50)
        down_btn.setFixedWidth(50)
        sort_row.addWidget(up_btn)
        sort_row.addWidget(down_btn)
        sort_row.addStretch()
        sort_wrap = QWidget()
        sort_wrap.setLayout(sort_row)
        sort_wrap.setMinimumWidth(120)
        row_layout.addWidget(sort_wrap)

        ops_row = QHBoxLayout()
        edit_btn = PushButton("编辑")
        edit_btn.setFixedWidth(50)
        del_btn = PushButton("删除")
        del_btn.setFixedWidth(50)
        ops_row.addWidget(edit_btn)
        ops_row.addWidget(del_btn)
        ops_row.addStretch()
        ops_wrap = QWidget()
        ops_wrap.setLayout(ops_row)
        ops_wrap.setMinimumWidth(120)
        row_layout.addWidget(ops_wrap)

        self.flags_layout.addWidget(row_widget)

        row_data = {
            "id": flag.id,
            "widget": row_widget,
            "name": name_edit,
            "default": default_cb,
            "enabled": enabled_cb,
            "key": flag.key,
        }
        self.flag_rows.append(row_data)

        up_btn.clicked.connect(lambda _=None, w=row_widget: self._move_flag_row(w, -1))
        down_btn.clicked.connect(lambda _=None, w=row_widget: self._move_flag_row(w, 1))
        del_btn.clicked.connect(lambda _=None, fid=flag.id, label=flag.label: self._delete_flag(fid, label))
        edit_btn.clicked.connect(lambda _=None, f=flag: self._edit_flag_dialog(f))

    def _move_flag_row(self, widget: QWidget, delta: int) -> None:
        idx = next((i for i, r in enumerate(self.flag_rows) if r["widget"] == widget), -1)
        if idx < 0:
            return
        new_idx = idx + delta
        if not 0 <= new_idx < len(self.flag_rows):
            return
        self.flag_rows[idx], self.flag_rows[new_idx] = self.flag_rows[new_idx], self.flag_rows[idx]

        self.flags_layout.removeWidget(widget)
        self.flags_layout.insertWidget(new_idx, widget)

    def _add_flag_dialog(self) -> None:
        dialog = FlagDialog(parent=self.window())
        if not dialog.exec():
            return
        try:
            self.ctx.flags.create_flag(
                key=dialog.key_value,
                label=dialog.label_value,
                default_value=dialog.default_checked,
                enabled=dialog.enabled_checked,
            )
            InfoBar.success("已添加", dialog.label_value, parent=self.window())
        except Exception as exc:
            InfoBar.error("添加失败", str(exc), parent=self.window())
        self._refresh_flags()

    def _edit_flag_dialog(self, flag) -> None:
        dialog = FlagDialog(
            parent=self.window(),
            key_value=flag.key,
            label_value=flag.label,
            default_checked=flag.default_value,
            enabled_checked=flag.enabled,
            editable_key=False,
        )
        if not dialog.exec():
            return
        try:
            self.ctx.flags.update_flag(
                flag.id,
                label=dialog.label_value,
                default_value=dialog.default_checked,
                enabled=dialog.enabled_checked,
            )
            InfoBar.success("已更新", dialog.label_value, parent=self.window())
        except Exception as exc:
            InfoBar.error("更新失败", str(exc), parent=self.window())
        self._refresh_flags()

    def _delete_flag(self, flag_id: int, label: str) -> None:
        first = MessageBox("确认删除", f"删除开关「{label}」将清理其所有历史值，确定继续？", self.window())
        if not first.exec():
            return
        second = MessageBox("再次确认", "此操作不可撤销，真的要删除吗？", self.window())
        if not second.exec():
            return
        try:
            self.ctx.flags.delete_flag(flag_id)
            InfoBar.success("已删除", label, parent=self.window())
        except Exception as exc:
            InfoBar.error("删除失败", str(exc), parent=self.window())
        self._refresh_flags()

    def _save_flags(self) -> None:
        try:
            for order, row in enumerate(self.flag_rows):
                self.ctx.flags.update_flag(
                    row["id"],
                    label=row["name"].text().strip() or row["key"],
                    default_value=row["default"].isChecked(),
                    enabled=row["enabled"].isChecked(),
                    sort_order=order,
                )
            InfoBar.success("已保存", "自定义开关已更新", parent=self.window())
        except Exception as exc:
            InfoBar.error("保存失败", str(exc), parent=self.window())
        self._refresh_flags()

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


class FlagDialog(MaskDialogBase):
    """新增/编辑自定义开关对话框"""

    def __init__(
        self,
        parent=None,
        *,
        key_value: str | None = None,
        label_value: str | None = None,
        default_checked: bool = False,
        enabled_checked: bool = True,
        editable_key: bool = True,
    ):
        super().__init__(parent)
        self.setWindowTitle("开关设置")
        self.widget.setMinimumWidth(520)
        self.widget.setMaximumWidth(640)
        self.key_value = key_value or ""
        self.label_value = label_value or ""
        self.default_checked = default_checked
        self.enabled_checked = enabled_checked
        self.editable_key = editable_key
        self._build_ui()

    def _build_ui(self) -> None:
        from qfluentwidgets import PrimaryPushButton, PushButton

        layout = QVBoxLayout(self.widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        header = create_page_header(
            "新增开关" if self.editable_key else "编辑开关",
            "自定义布尔开关，可用于表单录入和导出筛选",
        )
        layout.addWidget(header)

        card, card_layout = create_card()
        card_layout.setSpacing(12)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form_layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form_layout.setHorizontalSpacing(12)
        form_layout.setVerticalSpacing(12)

        key_label = QLabel("Key")
        key_label.setObjectName("formLabel")
        self.key_edit = LineEdit(parent=self.widget)
        self.key_edit.setText(self.key_value)
        self.key_edit.setPlaceholderText("key（小写英文字母+数字+_，不可更改）")
        self.key_edit.setDisabled(not self.editable_key)
        form_layout.addRow(key_label, self.key_edit)

        hint = BodyLabel("只允许小写字母、数字、下划线，创建后不可修改。")
        hint.setStyleSheet("color: #6b7280;")
        form_layout.addRow(QLabel(), hint)

        label_label = QLabel("显示名")
        label_label.setObjectName("formLabel")
        self.label_edit = LineEdit(parent=self.widget)
        self.label_edit.setText(self.label_value)
        self.label_edit.setPlaceholderText("显示名，例如：是否申报综测")
        form_layout.addRow(label_label, self.label_edit)

        options_row = QHBoxLayout()
        options_row.setSpacing(16)
        self.default_cb = CheckBox("默认勾选")
        self.default_cb.setChecked(self.default_checked)
        self.enabled_cb = CheckBox("启用")
        self.enabled_cb.setChecked(self.enabled_checked)
        options_row.addWidget(self.default_cb)
        options_row.addWidget(self.enabled_cb)
        options_row.addStretch()
        form_layout.addRow(QLabel("选项"), options_row)

        card_layout.addLayout(form_layout)
        layout.addWidget(card)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()
        ok_btn = PrimaryPushButton("OK")
        cancel_btn = PushButton("Cancel")
        ok_btn.clicked.connect(self._on_ok)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _on_ok(self) -> None:
        self.key_value = self.key_edit.text().strip()
        self.label_value = self.label_edit.text().strip() or self.key_value
        self.default_checked = self.default_cb.isChecked()
        self.enabled_checked = self.enabled_cb.isChecked()
        if not self.key_value:
            InfoBar.warning("提示", "Key 不能为空", parent=self)
            return
        self.accept()
