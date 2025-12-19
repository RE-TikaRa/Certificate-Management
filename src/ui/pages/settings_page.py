import logging
import shutil
import threading
from contextlib import suppress
from pathlib import Path
from queue import Empty, SimpleQueue
from typing import Any, ClassVar

from pypinyin import lazy_pinyin
from PySide6.QtCore import QProcess, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIntValidator
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QProgressBar,
    QProgressDialog,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CheckBox,
    ComboBox,
    EditableComboBox,
    InfoBar,
    LineEdit,
    MaskDialogBase,
    MessageBox,
    PrimaryPushButton,
    PushButton,
)

from src.config import BASE_DIR, LOG_DIR
from src.mcp.runtime import get_mcp_runtime
from src.services.import_export import ImportResult
from src.services.major_importer import read_major_catalog_from_csv, read_majors_from_excel
from src.services.school_importer import read_school_list

from ..styled_theme import ThemeManager
from ..theme import create_card, create_page_header, make_section_title
from ..utils.async_utils import run_in_thread_guarded
from .base_page import BasePage


def _split_api_keys(raw: str) -> list[str]:
    parts: list[str] = []
    for chunk in raw.replace("\n", ",").split(","):
        item = chunk.strip()
        if not item:
            continue
        if "|" in item:
            _name, value = item.split("|", 1)
            item = value.strip()
        if item:
            parts.append(item)
    return parts


def _parse_named_api_keys(raw: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for chunk in raw.replace("\n", ",").split(","):
        item = chunk.strip()
        if not item:
            continue
        name = ""
        value = item
        if "|" in item:
            name, value = item.split("|", 1)
            name = name.strip()
            value = value.strip()
        if value:
            out.append((name, value))
    return out


def _mask_key(key: str) -> str:
    k = key.strip()
    if len(k) <= 10:
        return k[:2] + "…" if len(k) > 2 else "…"
    return f"{k[:6]}…{k[-4:]}"


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


def replace_whitespace_with_underscore(line_edit: QLineEdit) -> None:
    import re

    def on_text_changed(text: str) -> None:
        replaced = re.sub(r"\s+", "_", text)
        if replaced != text:
            line_edit.textChanged.disconnect(on_text_changed)
            line_edit.setText(replaced)
            line_edit.setCursorPosition(len(replaced))
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


class AIKeyManagerDialog(MaskDialogBase):
    saved = Signal(str)  # comma-separated keys

    def __init__(self, parent, *, initial_keys: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("管理 API Key")
        self.widget.setMinimumWidth(720)
        self.widget.setMaximumWidth(920)
        self._initial_keys = initial_keys
        self._build_ui()
        self._load_initial()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self.widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        header = create_page_header("API Key 管理", "支持逗号分隔/换行分隔，保存后自动轮换")
        layout.addWidget(header)

        card, card_layout = create_card()
        card_layout.setSpacing(10)

        self.count_label = BodyLabel("Key 数量：0")
        self.count_label.setStyleSheet("color: #7a7a7a;")
        card_layout.addWidget(self.count_label)

        self.editor = QPlainTextEdit(self.widget)
        self.editor.setPlaceholderText("一行一个 Key，或用逗号分隔多个 Key")
        self.editor.setMinimumHeight(220)
        self.editor.textChanged.connect(self._refresh_count)
        card_layout.addWidget(self.editor)

        preview_title = BodyLabel("掩码预览（仅显示部分）")
        preview_title.setStyleSheet("color: #7a7a7a;")
        card_layout.addWidget(preview_title)

        self.preview = QListWidget(self.widget)
        self.preview.setMinimumHeight(140)
        card_layout.addWidget(self.preview)

        layout.addWidget(card)

        btn_row = QHBoxLayout()
        self.reset_btn = PushButton("还原")
        self.reset_btn.clicked.connect(self._load_initial)
        self.clear_btn = PushButton("清空")
        self.clear_btn.clicked.connect(lambda: self.editor.setPlainText(""))
        btn_row.addWidget(self.reset_btn)
        btn_row.addWidget(self.clear_btn)
        btn_row.addStretch()
        self.save_btn = PrimaryPushButton("保存")
        self.save_btn.clicked.connect(self._save)
        self.cancel_btn = PushButton("取消")
        self.cancel_btn.clicked.connect(self.close)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

    def _load_initial(self) -> None:
        keys = _split_api_keys(self._initial_keys)
        self.editor.blockSignals(True)
        try:
            self.editor.setPlainText("\n".join(keys))
        finally:
            self.editor.blockSignals(False)
        self._refresh_count()

    def _refresh_count(self) -> None:
        keys = _split_api_keys(self.editor.toPlainText())
        self.count_label.setText(f"Key 数量：{len(keys)}")
        self.preview.clear()
        for key in keys[:50]:
            self.preview.addItem(QListWidgetItem(_mask_key(key)))
        if len(keys) > 50:
            self.preview.addItem(QListWidgetItem(f"… 还有 {len(keys) - 50} 个未显示"))

    def _save(self) -> None:
        keys = _split_api_keys(self.editor.toPlainText())
        if not keys:
            InfoBar.warning("AI", "至少需要 1 个 Key", parent=self.window())
            return
        self.saved.emit(",".join(keys))
        self.close()


class AIProviderNameDialog(MaskDialogBase):
    saved = Signal(str)

    def __init__(self, parent, *, title: str, initial_name: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.widget.setMinimumWidth(520)
        self._initial_name = initial_name
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self.widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        header = create_page_header(self.windowTitle(), "仅用于区分不同提供商（本地保存）")
        layout.addWidget(header)

        form = QFormLayout()
        form.setSpacing(12)
        self.name = LineEdit()
        self.name.setPlaceholderText("例如：OpenAI / PackyAPI / 自建兼容")
        self.name.setText(self._initial_name)
        form.addRow("名称", self.name)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok_btn = PrimaryPushButton("保存")
        cancel_btn = PushButton("取消")
        ok_btn.clicked.connect(self._save)
        cancel_btn.clicked.connect(self.close)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _save(self) -> None:
        name = self.name.text().strip()
        if not name:
            InfoBar.warning("AI", "名称不能为空", parent=self.window())
            return
        self.saved.emit(name)
        self.close()


class AIKeyEditDialog(MaskDialogBase):
    saved = Signal(str, str)  # name, api_key

    def __init__(self, parent, *, title: str, initial_name: str = "", initial_key: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.widget.setMinimumWidth(640)
        self._initial_name = initial_name
        self._initial_key = initial_key
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self.widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        header = create_page_header(self.windowTitle(), "可配置多个 Key，软件会自动轮换（本地保存）")
        layout.addWidget(header)

        form = QFormLayout()
        form.setSpacing(12)

        self.name = LineEdit()
        self.name.setPlaceholderText("例如：主账号 / 备用账号（可留空）")
        self.name.setText(self._initial_name)
        form.addRow("名称", self.name)

        self.key = LineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("sk-... 或你的提供商 token（支持任意字符串）")
        self.key.setText(self._initial_key)
        form.addRow("API Key", self.key)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok_btn = PrimaryPushButton("保存")
        cancel_btn = PushButton("取消")
        ok_btn.clicked.connect(self._save)
        cancel_btn.clicked.connect(self.close)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _save(self) -> None:
        api_key = self.key.text().strip()
        if not api_key:
            InfoBar.warning("AI", "API Key 不能为空", parent=self.window())
            return
        self.saved.emit(self.name.text().strip(), api_key)
        self.close()


class AIModelPickerDialog(MaskDialogBase):
    selected = Signal(str)

    def __init__(self, parent, *, initial_models: list[str], current: str, fetch_models):
        super().__init__(parent)
        self.setWindowTitle("选择模型")
        self.widget.setMinimumWidth(720)
        self.widget.setMaximumWidth(920)
        self._fetch_models = fetch_models
        self._models: list[str] = list(initial_models)
        self._current = current
        self._busy = False
        self._build_ui()
        self._apply_models(self._models)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self.widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        header = create_page_header("模型选择", "可刷新获取模型列表，也可用搜索过滤")
        layout.addWidget(header)

        tool_row = QHBoxLayout()
        self.search = LineEdit()
        self.search.setPlaceholderText("搜索模型（支持子串）")
        self.search.textChanged.connect(self._filter)
        self.refresh_btn = PrimaryPushButton("刷新列表")
        self.refresh_btn.clicked.connect(self._refresh)
        tool_row.addWidget(self.search, 1)
        tool_row.addWidget(self.refresh_btn)
        layout.addLayout(tool_row)

        self.status = BodyLabel("模型：0")
        self.status.setStyleSheet("color: #7a7a7a;")
        layout.addWidget(self.status)

        self.list = QListWidget(self.widget)
        self.list.itemDoubleClicked.connect(lambda item: self._select(item.text()))
        self.list.setMinimumHeight(360)
        layout.addWidget(self.list)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.ok_btn = PrimaryPushButton("选择")
        self.ok_btn.clicked.connect(self._select_current)
        self.cancel_btn = PushButton("取消")
        self.cancel_btn.clicked.connect(self.close)
        btn_row.addWidget(self.ok_btn)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

    def _apply_models(self, models: list[str]) -> None:
        self._models = models
        self._filter()

    def _filter(self) -> None:
        keyword = self.search.text().strip().lower()
        self.list.clear()
        filtered = [m for m in self._models if keyword in m.lower()] if keyword else list(self._models)
        self.status.setText(f"模型：{len(filtered)} / {len(self._models)}")
        for model_id in filtered:
            self.list.addItem(QListWidgetItem(model_id))
        if self._current:
            matches = self.list.findItems(self._current, Qt.MatchFlag.MatchExactly)
            if matches:
                self.list.setCurrentItem(matches[0])

    def _refresh(self) -> None:
        if self._busy:
            return
        self._busy = True
        self.refresh_btn.setEnabled(False)
        self.status.setText("模型：刷新中…")

        def on_done(result: list[str] | Exception) -> None:
            self._busy = False
            self.refresh_btn.setEnabled(True)
            if isinstance(result, Exception):
                InfoBar.error("AI", str(result), parent=self.window())
                self._filter()
                return
            self._apply_models(result)

        run_in_thread_guarded(self._fetch_models, on_done, guard=self)

    def _select_current(self) -> None:
        item = self.list.currentItem()
        if item is None:
            InfoBar.warning("AI", "请选择一个模型", parent=self.window())
            return
        self._select(item.text())

    def _select(self, model_id: str) -> None:
        model = model_id.strip()
        if not model:
            return
        self.selected.emit(model)
        self.close()


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
        self.ai_enabled = CheckBox("启用 AI 证书识别（将把证书图片发送到你配置的 API）")
        self.ai_provider = ComboBox()
        self.ai_provider_add_btn = PushButton("新增提供商")
        self.ai_provider_rename_btn = PushButton("重命名")
        self.ai_provider_delete_btn = PushButton("删除")
        self.ai_api_base = LineEdit()
        self.ai_api_base.setPlaceholderText("例如：https://api.openai.com 或你的 OpenAI 兼容地址")
        self.ai_model = EditableComboBox()
        self.ai_model.setPlaceholderText("例如：gpt-4.1-mini（按你的 API 提供方填写）")
        self.ai_refresh_models_btn = PushButton("刷新模型")
        self.ai_test_btn = PrimaryPushButton("测试联通")
        self.ai_pick_model_btn = PushButton("选择…")
        self._ai_model_dialog: AIModelPickerDialog | None = None
        self.ai_pdf_pages = LineEdit()
        self.ai_pdf_pages.setPlaceholderText("默认 1（建议 1-3）")
        self.ai_pdf_pages.setValidator(QIntValidator(1, 10, self))
        self.ai_max_bytes = LineEdit()
        self.ai_max_bytes.setPlaceholderText("默认 20971520（20MB，单位：字节）")
        self.ai_max_bytes.setValidator(QIntValidator(1, 200_000_000, self))
        self.ai_status = BodyLabel("AI：未测试")
        self.ai_status.setStyleSheet("color: #7a7a7a;")
        self.ai_keys_table = QTableWidget(0, 2)
        self.ai_keys_table.setHorizontalHeaderLabels(["名称", "API Key"])
        self.ai_keys_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.ai_keys_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.ai_keys_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ai_keys_table.verticalHeader().setVisible(False)
        header = self.ai_keys_table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.ai_keys_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.ai_keys_table.setMinimumHeight(180)
        self.ai_key_add_btn = PushButton("新增 Key")
        self.ai_key_edit_btn = PushButton("编辑")
        self.ai_key_delete_btn = PushButton("删除")
        self.ai_key_meta = BodyLabel("API Key：0 个")
        self.ai_key_meta.setStyleSheet("color: #7a7a7a;")
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
        self._ai_refreshing = False
        self._ai_busy = False
        self._ai_current_provider_id: int | None = None

        self._build_ui()
        self.refresh()
        self._refresh_process_status()
        self._connect_mcp_signals()
        self._connect_ai_signals()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh_process_status()
        self._process_timer.start()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._process_timer.stop()

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
        layout.addWidget(self._build_ai_card())
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
        # AI
        self._ai_refreshing = True
        try:
            self.ai_enabled.setChecked(self.ctx.settings.get("ai_enabled", "false") == "true")
            self.ai_max_bytes.setText(self.ctx.settings.get("ai_max_bytes", "20971520"))
            self._refresh_ai_provider_ui()
        finally:
            self._ai_refreshing = False
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
        ):
            le.editingFinished.connect(lambda: self._save_mcp_settings(silent=True))

    def _connect_ai_signals(self) -> None:
        self.ai_enabled.stateChanged.connect(lambda _=0: self._save_ai_settings(silent=True))
        self.ai_provider.currentIndexChanged.connect(lambda _=0: self._on_ai_provider_changed())
        self.ai_provider_add_btn.clicked.connect(self._add_ai_provider)
        self.ai_provider_rename_btn.clicked.connect(self._rename_ai_provider)
        self.ai_provider_delete_btn.clicked.connect(self._delete_ai_provider)
        for le in (self.ai_api_base, self.ai_pdf_pages, self.ai_max_bytes):
            le.editingFinished.connect(lambda: self._save_ai_settings(silent=True))
        self.ai_model.currentIndexChanged.connect(lambda _=0: self._save_ai_settings(silent=True))
        self.ai_model.editingFinished.connect(lambda: self._save_ai_settings(silent=True))
        self.ai_pick_model_btn.clicked.connect(self._open_ai_model_dialog)

        self.ai_refresh_models_btn.clicked.connect(self._refresh_ai_models)
        self.ai_test_btn.clicked.connect(self._test_ai_connection)
        self.ai_key_add_btn.clicked.connect(self._add_ai_key)
        self.ai_key_edit_btn.clicked.connect(self._edit_ai_key)
        self.ai_key_delete_btn.clicked.connect(self._delete_ai_key)

    def _ai_selected_provider_id(self) -> int | None:
        raw = self.ai_provider.currentData()
        if isinstance(raw, int):
            return raw
        if raw is None:
            return None
        try:
            return int(str(raw))
        except Exception:
            return None

    def _refresh_ai_provider_ui(self) -> None:
        providers = self.ctx.ai_providers.list_providers()
        if not providers:
            self.ctx.ai_providers.ensure_legacy_migration()
            providers = self.ctx.ai_providers.list_providers()

        active_id = self.ctx.ai_providers.get_active_provider_id()
        if active_id is None and providers:
            active_id = providers[0].id
            self.ctx.ai_providers.set_active_provider_id(active_id)

        self.ai_provider.blockSignals(True)
        try:
            self.ai_provider.clear()
            for p in providers:
                self.ai_provider.addItem(p.name)
                self.ai_provider.setItemData(self.ai_provider.count() - 1, p.id)
            index = 0
            for i, p in enumerate(providers):
                if p.id == active_id:
                    index = i
                    break
            if providers:
                self.ai_provider.setCurrentIndex(index)
        finally:
            self.ai_provider.blockSignals(False)

        self._ai_current_provider_id = active_id if providers else None
        enabled = bool(providers)
        for w in (
            self.ai_provider,
            self.ai_provider_rename_btn,
            self.ai_provider_delete_btn,
            self.ai_api_base,
            self.ai_model,
            self.ai_pick_model_btn,
            self.ai_refresh_models_btn,
            self.ai_test_btn,
            self.ai_pdf_pages,
            self.ai_keys_table,
            self.ai_key_add_btn,
            self.ai_key_edit_btn,
            self.ai_key_delete_btn,
        ):
            w.setEnabled(enabled)

        if not providers:
            self.ai_api_base.setText("")
            self.ai_model.setText("")
            self.ai_pdf_pages.setText("1")
            self.ai_keys_table.setRowCount(0)
            self.ai_key_meta.setText("API Key：0 个")
            return

        provider = self.ctx.ai_providers.get_active_provider()
        self._load_ai_provider(provider)

    def _load_ai_provider(self, provider) -> None:
        self.ai_api_base.setText(provider.api_base)
        self.ai_model.setText(provider.model)
        self.ai_pdf_pages.setText(str(provider.pdf_pages))
        self._refresh_ai_keys_table(provider.api_keys)
        self._refresh_ai_key_meta()

    def _on_ai_provider_changed(self) -> None:
        if self._ai_refreshing:
            return
        prev_id = self._ai_current_provider_id
        next_id = self._ai_selected_provider_id()
        if next_id is None:
            return
        if prev_id is not None:
            self._save_ai_provider_fields(prev_id, silent=True)
        self.ctx.ai_providers.set_active_provider_id(next_id)
        self._ai_current_provider_id = next_id
        provider = self.ctx.ai_providers.get_active_provider()
        self._ai_refreshing = True
        try:
            self._load_ai_provider(provider)
            self.ai_status.setText("AI：未测试")
        finally:
            self._ai_refreshing = False

    def _add_ai_provider(self) -> None:
        dialog = AIProviderNameDialog(self.window(), title="新增 AI 提供商")

        def on_saved(name: str) -> None:
            base = self.ai_api_base.text().strip().rstrip("/")
            model = self.ai_model.text().strip()
            try:
                pdf_pages = int(self.ai_pdf_pages.text().strip() or "1")
            except ValueError:
                pdf_pages = 1
            provider = self.ctx.ai_providers.create_provider(
                name=name,
                api_base=base,
                api_keys="",
                model=model,
                pdf_pages=max(1, min(10, pdf_pages)),
            )
            self.ctx.ai_providers.set_active_provider_id(provider.id)
            self.refresh()
            InfoBar.success("AI", f"已新增提供商：{name}", parent=self.window())

        dialog.saved.connect(on_saved)
        dialog.show()

    def _rename_ai_provider(self) -> None:
        provider_id = self._ai_current_provider_id
        if provider_id is None:
            return
        provider = self.ctx.ai_providers.get_active_provider()
        dialog = AIProviderNameDialog(self.window(), title="重命名 AI 提供商", initial_name=provider.name)

        def on_saved(name: str) -> None:
            self.ctx.ai_providers.update_provider(provider_id, name=name)
            self._refresh_ai_provider_ui()
            InfoBar.success("AI", f"已重命名为：{name}", parent=self.window())

        dialog.saved.connect(on_saved)
        dialog.show()

    def _delete_ai_provider(self) -> None:
        provider_id = self._ai_current_provider_id
        if provider_id is None:
            return
        provider = self.ctx.ai_providers.get_active_provider()
        box = MessageBox("删除提供商", f"确定删除“{provider.name}”吗？", parent=self.window())
        if not box.exec():
            return
        self.ctx.ai_providers.delete_provider(provider_id)
        self.refresh()
        InfoBar.success("AI", "已删除提供商", parent=self.window())

    def _refresh_ai_keys_table(self, raw_keys: str) -> None:
        entries = _parse_named_api_keys(raw_keys)
        self.ai_keys_table.setRowCount(len(entries))
        for row, (name, api_key) in enumerate(entries):
            name_item = QTableWidgetItem(name)
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            key_item = QTableWidgetItem(_mask_key(api_key))
            key_item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            key_item.setData(Qt.ItemDataRole.UserRole, api_key)
            self.ai_keys_table.setItem(row, 0, name_item)
            self.ai_keys_table.setItem(row, 1, key_item)
        self.ai_keys_table.resizeColumnToContents(0)

    def _refresh_ai_key_meta(self) -> None:
        try:
            provider = self.ctx.ai_providers.get_active_provider()
        except Exception:
            self.ai_key_meta.setText("API Key：0 个")
            return
        count = len(_split_api_keys(provider.api_keys))
        self.ai_key_meta.setText(f"API Key：{count} 个（轮换索引 {provider.last_key_index}）")

    def _persist_ai_keys(self) -> None:
        provider_id = self._ai_current_provider_id
        if provider_id is None:
            return
        entries: list[tuple[str, str]] = []
        for row in range(self.ai_keys_table.rowCount()):
            name_item = self.ai_keys_table.item(row, 0)
            key_item = self.ai_keys_table.item(row, 1)
            if key_item is None:
                continue
            raw = key_item.data(Qt.ItemDataRole.UserRole)
            if not isinstance(raw, str):
                continue
            api_key = raw.strip()
            if not api_key:
                continue
            name = name_item.text().strip() if name_item is not None else ""
            entries.append((name, api_key))
        lines = [f"{n}|{k}" if n else k for n, k in entries]
        self.ctx.ai_providers.update_provider(provider_id, api_keys="\n".join(lines), reset_rotation=True)
        self._refresh_ai_key_meta()

    def _selected_ai_key_row(self) -> int | None:
        row = self.ai_keys_table.currentRow()
        return None if row < 0 else row

    def _add_ai_key(self) -> None:
        dialog = AIKeyEditDialog(self.window(), title="新增 API Key")

        def on_saved(name: str, api_key: str) -> None:
            row = self.ai_keys_table.rowCount()
            self.ai_keys_table.insertRow(row)
            name_item = QTableWidgetItem(name)
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            self.ai_keys_table.setItem(row, 0, name_item)
            key_item = QTableWidgetItem(_mask_key(api_key))
            key_item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            key_item.setData(Qt.ItemDataRole.UserRole, api_key)
            self.ai_keys_table.setItem(row, 1, key_item)
            self._persist_ai_keys()
            InfoBar.success("AI", "API Key 已保存", parent=self.window())

        dialog.saved.connect(on_saved)
        dialog.show()

    def _edit_ai_key(self) -> None:
        row = self._selected_ai_key_row()
        if row is None:
            InfoBar.warning("AI", "请选择要编辑的 Key", parent=self.window())
            return
        name_item = self.ai_keys_table.item(row, 0)
        key_item = self.ai_keys_table.item(row, 1)
        if key_item is None:
            return
        raw = key_item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(raw, str):
            return
        dialog = AIKeyEditDialog(
            self.window(),
            title="编辑 API Key",
            initial_name=name_item.text() if name_item is not None else "",
            initial_key=raw,
        )

        def on_saved(name: str, api_key: str) -> None:
            name_item = QTableWidgetItem(name)
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            self.ai_keys_table.setItem(row, 0, name_item)
            new_item = QTableWidgetItem(_mask_key(api_key))
            new_item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            new_item.setData(Qt.ItemDataRole.UserRole, api_key)
            self.ai_keys_table.setItem(row, 1, new_item)
            self._persist_ai_keys()
            InfoBar.success("AI", "API Key 已更新", parent=self.window())

        dialog.saved.connect(on_saved)
        dialog.show()

    def _delete_ai_key(self) -> None:
        row = self._selected_ai_key_row()
        if row is None:
            InfoBar.warning("AI", "请选择要删除的 Key", parent=self.window())
            return
        box = MessageBox("删除 API Key", "确定删除选中的 Key 吗？", parent=self.window())
        if not box.exec():
            return
        self.ai_keys_table.removeRow(row)
        self._persist_ai_keys()
        InfoBar.success("AI", "API Key 已删除", parent=self.window())

    def _save_ai_settings(self, *, silent: bool = False) -> None:
        if self._ai_refreshing:
            return
        try:
            self.ctx.settings.set("ai_enabled", str(self.ai_enabled.isChecked()).lower())
            max_bytes_raw = self.ai_max_bytes.text().strip() or "20971520"
            try:
                max_bytes = int(max_bytes_raw)
            except ValueError:
                max_bytes = 20971520
            max_bytes = max(1, min(200_000_000, max_bytes))
            self.ai_max_bytes.setText(str(max_bytes))
            self.ctx.settings.set("ai_max_bytes", str(max_bytes))
            provider_id = self._ai_current_provider_id
            if provider_id is not None:
                self._save_ai_provider_fields(provider_id, silent=True)
                self._refresh_ai_key_meta()
            if not silent:
                InfoBar.success("AI", "AI 设置已保存", parent=self.window())
        except Exception as exc:
            if not silent:
                InfoBar.error("AI", f"AI 设置保存失败：{exc}", parent=self.window())

    def _save_ai_provider_fields(self, provider_id: int, *, silent: bool) -> None:
        base = self.ai_api_base.text().strip().rstrip("/")
        self.ai_api_base.setText(base)
        model = self.ai_model.text().strip()
        try:
            pdf_pages = int(self.ai_pdf_pages.text().strip() or "1")
        except ValueError:
            pdf_pages = 1
        self.ctx.ai_providers.update_provider(
            provider_id,
            api_base=base,
            model=model,
            pdf_pages=max(1, min(10, pdf_pages)),
        )
        if not silent:
            InfoBar.success("AI", "提供商设置已保存", parent=self.window())

    def _refresh_ai_models(self) -> None:
        if self._ai_busy:
            return
        self._save_ai_settings(silent=True)
        self._ai_busy = True
        self.ai_refresh_models_btn.setEnabled(False)
        self.ai_test_btn.setEnabled(False)
        self.ai_pick_model_btn.setEnabled(False)
        self.ai_status.setText("AI：正在获取模型列表…")

        def task() -> list[str]:
            return self.ctx.ai.list_models()

        def on_done(result: list[str] | Exception) -> None:
            self._ai_busy = False
            self.ai_refresh_models_btn.setEnabled(True)
            self.ai_test_btn.setEnabled(True)
            self.ai_pick_model_btn.setEnabled(True)
            if isinstance(result, Exception):
                self.ai_status.setText("AI：获取模型失败")
                InfoBar.error("AI", str(result), parent=self.window())
                return

            current = self.ai_model.text().strip()
            self.ai_model.blockSignals(True)
            try:
                self.ai_model.clear()
                self.ai_model.addItems(result)
                if current:
                    self.ai_model.setText(current)
            finally:
                self.ai_model.blockSignals(False)
            self.ai_status.setText(f"AI：已获取 {len(result)} 个模型")
            InfoBar.success("AI", f"已获取 {len(result)} 个模型", parent=self.window())

        run_in_thread_guarded(task, on_done, guard=self)

    def _open_ai_model_dialog(self) -> None:
        if self._ai_model_dialog is not None:
            self._ai_model_dialog.close()

        existing = [self.ai_model.itemText(i) for i in range(self.ai_model.count())]

        def fetch() -> list[str]:
            return self.ctx.ai.list_models()

        self._ai_model_dialog = AIModelPickerDialog(
            self.window(),
            initial_models=existing,
            current=self.ai_model.text().strip(),
            fetch_models=fetch,
        )

        def on_selected(model_id: str) -> None:
            self.ai_model.setText(model_id)
            self._save_ai_settings(silent=True)
            InfoBar.success("AI", f"已选择模型：{model_id}", parent=self.window())

        self._ai_model_dialog.selected.connect(on_selected)
        self._ai_model_dialog.show()

    def _test_ai_connection(self) -> None:
        if self._ai_busy:
            return
        self._save_ai_settings(silent=True)
        self._ai_busy = True
        self.ai_refresh_models_btn.setEnabled(False)
        self.ai_test_btn.setEnabled(False)
        self.ai_pick_model_btn.setEnabled(False)
        self.ai_key_add_btn.setEnabled(False)
        self.ai_key_edit_btn.setEnabled(False)
        self.ai_key_delete_btn.setEnabled(False)
        self.ai_status.setText("AI：测试中…")

        def task() -> tuple[int, str]:
            try:
                models = self.ctx.ai.list_models()
            except Exception:
                latency = self.ctx.ai.check_latency()
                return 0, f"连通正常（/v1/models 不支持，latency={latency}ms）"
            provider = self.ctx.ai_providers.get_active_provider()
            selected = provider.model.strip()
            if selected and selected not in set(models):
                return len(models), f"连通正常，但当前模型不在列表中：{selected}"
            latency = self.ctx.ai.check_latency()
            return len(models), f"连通正常（latency={latency}ms）"

        def on_done(result: tuple[int, str] | Exception) -> None:
            self._ai_busy = False
            self.ai_refresh_models_btn.setEnabled(True)
            self.ai_test_btn.setEnabled(True)
            self.ai_pick_model_btn.setEnabled(True)
            self.ai_key_add_btn.setEnabled(True)
            self.ai_key_edit_btn.setEnabled(True)
            self.ai_key_delete_btn.setEnabled(True)
            if isinstance(result, Exception):
                self.ai_status.setText("AI：测试失败")
                InfoBar.error("AI", str(result), parent=self.window())
                return
            count, msg = result
            base = self.ai_api_base.text().strip()
            model = self.ai_model.text().strip()
            self.ai_status.setText(f"AI：{msg}（models={count}）")
            InfoBar.success("AI", f"{self.ai_status.text()}\n{base}\n{model}".strip(), parent=self.window())

        run_in_thread_guarded(task, on_done, guard=self)

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
            # AI 设置（页面内已自动保存，这里兜底写一次）
            self._save_ai_settings(silent=True)

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

    def _build_ai_card(self) -> QWidget:
        card, card_layout = create_card()
        card_layout.addWidget(make_section_title("AI 证书识别"))

        hint = BodyLabel(
            "用于“荣誉录入”页面的一键识别：从证书图片自动抽取比赛名称、日期、级别、奖项、证书编号与成员姓名。\n"
            "注意：启用后会把证书图片发送到你填写的 API（仅本地保存配置，请勿对外暴露服务）。\n"
            "           只有填写好APIKey之后才能够刷新模型列表与选择模型"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #7a7a7a;")
        card_layout.addWidget(hint)

        top_form = QFormLayout()
        top_form.setSpacing(12)
        top_form.addRow(self.ai_enabled)
        provider_row = QWidget()
        provider_layout = QHBoxLayout(provider_row)
        provider_layout.setContentsMargins(0, 0, 0, 0)
        provider_layout.addWidget(self.ai_provider, 1)
        provider_layout.addWidget(self.ai_provider_add_btn)
        provider_layout.addWidget(self.ai_provider_rename_btn)
        provider_layout.addWidget(self.ai_provider_delete_btn)
        top_form.addRow("提供商", provider_row)
        top_form.addRow("API Url", self.ai_api_base)
        card_layout.addLayout(top_form)

        keys_title = QLabel("API Key（支持多 Key 轮换）")
        card_layout.addWidget(keys_title)
        card_layout.addWidget(self.ai_keys_table)

        key_action = QHBoxLayout()
        key_action.addWidget(self.ai_key_add_btn)
        key_action.addWidget(self.ai_key_edit_btn)
        key_action.addWidget(self.ai_key_delete_btn)
        key_action.addStretch()
        card_layout.addLayout(key_action)

        card_layout.addWidget(self.ai_key_meta)

        bottom_form = QFormLayout()
        bottom_form.setSpacing(12)
        model_row = QWidget()
        model_layout = QHBoxLayout(model_row)
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_layout.addWidget(self.ai_model, 1)
        model_layout.addWidget(self.ai_pick_model_btn)
        model_layout.addWidget(self.ai_refresh_models_btn)
        model_layout.addWidget(self.ai_test_btn)
        bottom_form.addRow("模型", model_row)
        bottom_form.addRow("PDF 页数（最多 10）", self.ai_pdf_pages)
        bottom_form.addRow("单文件大小上限（字节）", self.ai_max_bytes)
        card_layout.addLayout(bottom_form)

        card_layout.addWidget(self.ai_status)

        action = QHBoxLayout()
        save_btn = PrimaryPushButton("保存 AI 设置")
        save_btn.clicked.connect(lambda: self._save_ai_settings(silent=False))
        action.addWidget(save_btn)
        action.addStretch()
        card_layout.addLayout(action)

        return card

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
            host = self.ctx.settings.get("mcp_host", "127.0.0.1")
            self._mcp_runtime.start_mcp_sse(
                host=host,
                port=port_value,
                allow_write=self.mcp_allow_write.isChecked(),
                max_bytes=max_bytes_value,
            )
        except Exception as exc:
            InfoBar.error("MCP", f"启动失败：{exc}", parent=self.window())
            return
        finally:
            self._refresh_process_status()

        mcp = self._mcp_runtime.mcp_info()
        if mcp.running:
            InfoBar.success("MCP", f"已启动（本地）：{self._mcp_sse_url()}", parent=self.window())
            return
        InfoBar.error(
            "MCP",
            f"启动失败：进程未保持运行，请查看日志：{mcp.log_path}",
            parent=self.window(),
        )

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
        host = (self.ctx.settings.get("mcp_host", "127.0.0.1") or "").strip()
        if host.startswith("[") and host.endswith("]"):
            host = host[1:-1].strip()
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        return f"http://{host}:{port}/sse"

    def _start_web(self) -> None:
        try:
            host = self.mcp_web_host.text().strip() or "127.0.0.1"
            port = self.mcp_web_port.text().strip() or "7860"
            self._mcp_runtime.start_web(host=host, port=int(port))
        except Exception as exc:
            InfoBar.error("MCP Web", f"启动失败：{exc}", parent=self.window())
            return
        finally:
            self._refresh_process_status()

        web = self._mcp_runtime.web_info()
        if web.running:
            InfoBar.success("MCP Web", "已启动", parent=self.window())
            return
        InfoBar.error(
            "MCP Web",
            f"启动失败：进程未保持运行，请查看日志：{web.log_path}",
            parent=self.window(),
        )

    def _stop_web(self) -> None:
        try:
            self._mcp_runtime.stop_web()
            InfoBar.success("MCP Web", "已停止", parent=self.window())
        except Exception as exc:
            InfoBar.error("MCP Web", f"停止失败：{exc}", parent=self.window())
        finally:
            self._refresh_process_status()

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
        self.award_template_btn = PushButton("下载导入模板 (XLSX)")
        self.award_template_btn.clicked.connect(self._download_awards_template_xlsx)
        btn_row.addWidget(self.award_import_btn)
        btn_row.addWidget(self.award_export_btn)
        btn_row.addWidget(self.award_template_btn)

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

        hint = BodyLabel("用于录入/导出/筛选的布尔开关，支持改名、启用、默认值、排序（修改后点“保存”生效）。")
        hint.setStyleSheet("color: #7a7a7a;")
        card_layout.addWidget(hint)

        # 标题行
        header = QHBoxLayout()
        add_btn = PrimaryPushButton("新增开关")
        add_btn.clicked.connect(self._add_flag_dialog)
        save_btn = PushButton("保存")
        save_btn.clicked.connect(self._save_flags)
        refresh_btn = PushButton("刷新")
        refresh_btn.clicked.connect(self._refresh_flags)
        header.addWidget(add_btn)
        header.addWidget(save_btn)
        header.addWidget(refresh_btn)
        header.addStretch()
        card_layout.addLayout(header)

        self.flags_container = QWidget()
        # 表格区域过宽会导致列间空隙过大，这里限制最大宽度并居中展示
        self.flags_container.setMaximumWidth(1140)
        self.flags_layout = QGridLayout(self.flags_container)
        self.flags_layout.setContentsMargins(0, 8, 0, 0)
        self.flags_layout.setHorizontalSpacing(12)
        self.flags_layout.setVerticalSpacing(10)

        name_h = self._make_header_label("显示名")
        name_h.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        key_h = self._make_header_label("Key")
        key_h.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        default_h = self._make_header_label("默认勾选")
        default_h.setAlignment(Qt.AlignmentFlag.AlignCenter)
        enabled_h = self._make_header_label("启用")
        enabled_h.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sort_h = self._make_header_label("排序")
        sort_h.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ops_h = self._make_header_label("操作")
        ops_h.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.flags_layout.addWidget(name_h, 0, 0)
        self.flags_layout.addWidget(key_h, 0, 1)
        self.flags_layout.addWidget(default_h, 0, 2)
        self.flags_layout.addWidget(enabled_h, 0, 3)
        self.flags_layout.addWidget(sort_h, 0, 4)
        self.flags_layout.addWidget(ops_h, 0, 5)

        self.flags_layout.setColumnMinimumWidth(0, 220)
        self.flags_layout.setColumnMinimumWidth(1, 180)
        self.flags_layout.setColumnMinimumWidth(2, 90)
        self.flags_layout.setColumnMinimumWidth(3, 70)
        self.flags_layout.setColumnMinimumWidth(4, 140)
        self.flags_layout.setColumnMinimumWidth(5, 140)

        # 让“显示名/Key”随容器宽度扩展，其他列保持紧凑，整体随窗口自适应
        self.flags_layout.setColumnStretch(0, 5)
        self.flags_layout.setColumnStretch(1, 3)
        self.flags_layout.setColumnStretch(2, 0)
        self.flags_layout.setColumnStretch(3, 0)
        self.flags_layout.setColumnStretch(4, 0)
        self.flags_layout.setColumnStretch(5, 0)
        table_wrap = QWidget()
        table_row = QHBoxLayout(table_wrap)
        table_row.setContentsMargins(0, 0, 0, 0)
        table_row.addStretch()
        table_row.addWidget(self.flags_container)
        table_row.addStretch()
        card_layout.addWidget(table_wrap)

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
        for row in self.flag_rows:
            for widget in row.get("cells", []):
                self.flags_layout.removeWidget(widget)
                widget.deleteLater()
        self.flag_rows.clear()

        flags = self.ctx.flags.list_flags(enabled_only=False)
        for flag in flags:
            self._add_flag_row(flag)

        self._render_flag_rows()

    def _add_flag_row(self, flag) -> None:
        name_edit = LineEdit(parent=self.flags_container)
        name_edit.setText(flag.label)
        name_edit.setMinimumWidth(180)
        name_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        key_label = QLabel(flag.key, parent=self.flags_container)
        key_label.setMinimumWidth(170)
        key_label.setStyleSheet("color: #bdbdbd;" if self.theme_manager.is_dark else "color: #666;")
        key_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        default_cb = CheckBox(parent=self.flags_container)
        default_cb.setChecked(bool(flag.default_value))
        default_cb.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        enabled_cb = CheckBox(parent=self.flags_container)
        enabled_cb.setChecked(bool(flag.enabled))
        enabled_cb.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        sort_wrap = QWidget(parent=self.flags_container)
        sort_row = QHBoxLayout(sort_wrap)
        sort_row.setContentsMargins(0, 0, 0, 0)
        sort_row.setSpacing(8)
        up_btn = PushButton("上移", parent=sort_wrap)
        down_btn = PushButton("下移", parent=sort_wrap)
        up_btn.setFixedWidth(56)
        down_btn.setFixedWidth(56)
        sort_row.addWidget(up_btn)
        sort_row.addWidget(down_btn)
        sort_wrap.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        ops_wrap = QWidget(parent=self.flags_container)
        ops_row = QHBoxLayout(ops_wrap)
        ops_row.setContentsMargins(0, 0, 0, 0)
        ops_row.setSpacing(8)
        edit_btn = PushButton("编辑", parent=ops_wrap)
        del_btn = PushButton("删除", parent=ops_wrap)
        edit_btn.setFixedWidth(56)
        del_btn.setFixedWidth(56)
        ops_row.addWidget(edit_btn)
        ops_row.addWidget(del_btn)
        ops_wrap.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        row_data = {
            "id": flag.id,
            "name": name_edit,
            "default": default_cb,
            "enabled": enabled_cb,
            "key": flag.key,
            "cells": [name_edit, key_label, default_cb, enabled_cb, sort_wrap, ops_wrap],
            "key_label": key_label,
            "sort_wrap": sort_wrap,
            "ops_wrap": ops_wrap,
        }
        self.flag_rows.append(row_data)

        up_btn.clicked.connect(lambda _=None, fid=flag.id: self._move_flag_row(fid, -1))
        down_btn.clicked.connect(lambda _=None, fid=flag.id: self._move_flag_row(fid, 1))
        del_btn.clicked.connect(
            lambda _=None, fid=flag.id, name=name_edit: self._delete_flag(fid, name.text().strip() or flag.key)
        )
        edit_btn.clicked.connect(lambda _=None, fid=flag.id: self._edit_flag_dialog(fid))

    def _render_flag_rows(self) -> None:
        self.flags_container.setUpdatesEnabled(False)
        try:
            for row in self.flag_rows:
                for widget in row.get("cells", []):
                    self.flags_layout.removeWidget(widget)

            for i, row in enumerate(self.flag_rows, start=1):
                self.flags_layout.addWidget(row["name"], i, 0)
                self.flags_layout.addWidget(row["key_label"], i, 1)
                self.flags_layout.addWidget(row["default"], i, 2, alignment=Qt.AlignmentFlag.AlignCenter)
                self.flags_layout.addWidget(row["enabled"], i, 3, alignment=Qt.AlignmentFlag.AlignCenter)
                self.flags_layout.addWidget(row["sort_wrap"], i, 4, alignment=Qt.AlignmentFlag.AlignCenter)
                self.flags_layout.addWidget(
                    row["ops_wrap"], i, 5, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
            self.flags_layout.setRowStretch(len(self.flag_rows) + 1, 1)
        finally:
            self.flags_container.setUpdatesEnabled(True)

    def _move_flag_row(self, flag_id: int, delta: int) -> None:
        idx = next((i for i, r in enumerate(self.flag_rows) if r["id"] == flag_id), -1)
        if idx < 0:
            return
        new_idx = idx + delta
        if not 0 <= new_idx < len(self.flag_rows):
            return
        self.flag_rows[idx], self.flag_rows[new_idx] = self.flag_rows[new_idx], self.flag_rows[idx]
        self._render_flag_rows()

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

    def _edit_flag_dialog(self, flag_id: int) -> None:
        row = next((r for r in self.flag_rows if r.get("id") == flag_id), None)
        if not row:
            return

        dialog = FlagDialog(
            parent=self.window(),
            key_value=row["key"],
            label_value=row["name"].text().strip() or row["key"],
            default_checked=row["default"].isChecked(),
            enabled_checked=row["enabled"].isChecked(),
            editable_key=False,
        )
        if not dialog.exec():
            return
        try:
            self.ctx.flags.update_flag(
                flag_id,
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

    def _download_awards_template_xlsx(self) -> None:
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存导入模板 (XLSX)",
            str(Path("exports/awards_template.xlsx").resolve()),
            "Excel 文件 (*.xlsx)",
        )
        if not save_path:
            return
        path = Path(save_path)
        if path.suffix.lower() != ".xlsx":
            path = path.with_suffix(".xlsx")
        try:
            template = self.ctx.importer.get_awards_template_path("xlsx")
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(template, path)
            InfoBar.success("已保存", path.name, parent=self.window())
        except Exception as exc:
            self.logger.exception("Save awards template failed: %s", exc)
            InfoBar.error("保存失败", str(exc), parent=self.window())

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
                "将清空 awards.db 并重建空库（不依赖删除文件），数据将全部丢失。<br><br>"
                "<span style='color:#d32f2f; font-weight:700; font-size: 20px;'>"
                "本操作会删除：<br>所有荣誉/成员、附件记录、设置项、备份记录、学校与专业及映射、导入记录等。<br><br>请谨慎操作！"
                "</span>"
            ),
        ):
            return
        self._do_clear_database()

    def _do_clear_database(self) -> None:
        try:
            with suppress(Exception):
                self._mcp_runtime.shutdown()
            self.ctx.db.reset()
            self.ctx.settings.reload()
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
        replace_whitespace_with_underscore(self.key_edit)
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
