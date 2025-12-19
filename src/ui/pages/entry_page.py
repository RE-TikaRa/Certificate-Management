import hashlib
import logging
from collections.abc import Iterable
from contextlib import suppress
from datetime import date
from functools import partial
from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import QDate, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QLineEdit,
    QPlainTextEdit,
    QProgressDialog,
    QScrollArea,
    QTableView,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    CheckBox,
    ComboBox,
    FluentIcon,
    InfoBar,
    LineEdit,
    MaskDialogBase,
    PrimaryPushButton,
    PushButton,
    SpinBox,
    TransparentToolButton,
)

from ...services.ai_certificate_service import CertificateExtractedInfo
from ...services.doc_extractor import extract_member_info_from_doc
from ...services.validators import FormValidator
from ..styled_theme import ThemeManager
from ..table_models import AttachmentTableModel
from ..theme import create_card, create_page_header, make_section_title
from ..utils.async_utils import run_in_thread_guarded
from ..widgets.attachment_table_view import AttachmentTableView
from ..widgets.major_search import MajorSearchWidget
from ..widgets.school_search import SchoolSearchWidget
from .base_page import BasePage

logger = logging.getLogger(__name__)


class AICertificatePreviewDialog(MaskDialogBase):
    applied = Signal(object)  # CertificateExtractedInfo

    def __init__(self, parent, *, info: CertificateExtractedInfo) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI 识别预览")
        self.widget.setMinimumWidth(760)
        self.widget.setMaximumWidth(960)
        self._info = info
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self.widget)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        header = create_page_header("AI 识别预览", "确认无误后再填充到表单（可手动修改）")
        layout.addWidget(header)

        card, card_layout = create_card()
        form = QFormLayout()
        form.setSpacing(12)

        self.competition_name = LineEdit()
        self.competition_name.setPlaceholderText("比赛/竞赛名称")
        form.addRow("比赛名称", self.competition_name)

        self.award_date = LineEdit()
        self.award_date.setPlaceholderText("YYYY-MM-DD（可留空）")
        form.addRow("获奖日期", self.award_date)

        self.level = ComboBox()
        self.level.addItems(["（不填）", "国家级", "省级", "校级"])
        form.addRow("赛事级别", self.level)

        self.rank = ComboBox()
        self.rank.addItems(["（不填）", "一等奖", "二等奖", "三等奖", "优秀奖"])
        form.addRow("奖项等级", self.rank)

        self.certificate_code = LineEdit()
        self.certificate_code.setPlaceholderText("证书编号（可留空）")
        form.addRow("证书编号", self.certificate_code)

        self.member_names = QPlainTextEdit(self.widget)
        self.member_names.setPlaceholderText("一行一个成员姓名")
        self.member_names.setMinimumHeight(140)
        form.addRow("成员姓名", self.member_names)

        card_layout.addLayout(form)
        layout.addWidget(card)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        apply_btn = PrimaryPushButton("填充到表单")
        cancel_btn = PushButton("取消")
        apply_btn.clicked.connect(self._apply)
        cancel_btn.clicked.connect(self.close)
        btn_row.addWidget(apply_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _load(self) -> None:
        self.competition_name.setText(self._info.competition_name or "")
        self.award_date.setText(self._info.award_date.isoformat() if self._info.award_date else "")
        self.certificate_code.setText(self._info.certificate_code or "")

        self.level.setCurrentText(self._info.level if self._info.level else "（不填）")
        self.rank.setCurrentText(self._info.rank if self._info.rank else "（不填）")
        self.member_names.setPlainText("\n".join(self._info.member_names))

    def _apply(self) -> None:
        data = {
            "competition_name": self.competition_name.text().strip() or None,
            "award_date": self.award_date.text().strip() or None,
            "level": None if self.level.currentText() == "（不填）" else self.level.currentText(),
            "rank": None if self.rank.currentText() == "（不填）" else self.rank.currentText(),
            "certificate_code": self.certificate_code.text().strip() or None,
            "member_names": [line.strip() for line in self.member_names.toPlainText().splitlines() if line.strip()],
        }
        try:
            info = CertificateExtractedInfo.model_validate(data)
        except Exception as exc:
            InfoBar.error("AI", f"预览内容不合法：{exc}", parent=self.window())
            return
        self.applied.emit(info)
        self.close()


def clean_input_text(line_edit: QLineEdit) -> None:
    """为输入框添加自动清理空白字符功能"""
    import re

    def on_text_changed(text: str):
        # 移除所有空白字符（空格、制表符、换行等）
        cleaned = re.sub(r"\s+", "", text)
        if cleaned != text:
            # 暂时断开信号避免递归
            line_edit.textChanged.disconnect(on_text_changed)
            line_edit.setText(cleaned)
            # 恢复光标位置到末尾
            line_edit.setCursorPosition(len(cleaned))
            # 重新连接信号
            line_edit.textChanged.connect(on_text_changed)

    line_edit.textChanged.connect(on_text_changed)


class EntryPage(BasePage):
    def __init__(self, ctx, theme_manager: ThemeManager):
        super().__init__(ctx, theme_manager)
        self.selected_files: list[Path] = []
        self._selected_file_keys: set[str] = set()
        self._attachments_loaded_for_edit = False
        self.editing_award = None  # 当前正在编辑的荣誉
        self.flag_checkboxes: dict[str, CheckBox] = {}
        self.flag_defs: list = []
        self._ai_busy = False
        self._ai_progress: QProgressDialog | None = None

        # 连接主题变化信号
        self.theme_manager.themeChanged.connect(self._on_theme_changed)

        self._build_ui()

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        title_widget = QWidget()
        title_widget.setObjectName("pageRoot")
        title_layout = QHBoxLayout(title_widget)
        title_layout.setContentsMargins(32, 24, 32, 0)
        title_layout.setSpacing(0)
        title_layout.addWidget(create_page_header("荣誉录入", "集中采集证书信息并同步团队"))
        title_layout.addStretch()
        from qfluentwidgets import FluentIcon, TransparentToolButton

        self.ai_cert_btn = PushButton("AI 识别证书")
        self.ai_cert_btn.clicked.connect(self._ai_recognize_certificate)
        title_layout.addWidget(self.ai_cert_btn)

        refresh_btn = TransparentToolButton(FluentIcon.ERASE_TOOL)
        refresh_btn.setToolTip("清空表单")
        refresh_btn.clicked.connect(self._clear_form)
        title_layout.addWidget(refresh_btn)
        outer_layout.addWidget(title_widget)

        self.scrollArea = QScrollArea()
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer_layout.addWidget(self.scrollArea)
        self.content_widget = self.scrollArea

        container = QWidget()
        container.setObjectName("pageRoot")
        self.scrollArea.setWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 28, 32, 32)
        layout.setSpacing(28)

        # === Basic Info Card ===
        info_card, info_layout = create_card()

        # Row 1: 比赛名称 + 获奖日期
        row1 = QHBoxLayout()
        row1.setSpacing(16)
        name_col = QVBoxLayout()
        name_label = QLabel("比赛名称")
        name_label.setObjectName("formLabel")
        self.name_input = LineEdit()
        name_col.addWidget(name_label)
        name_col.addWidget(self.name_input)

        date_col = QVBoxLayout()
        date_label = QLabel("获奖日期")
        date_label.setObjectName("formLabel")
        date_row = QHBoxLayout()
        date_row.setSpacing(8)

        # Year input
        year_label = QLabel("年")
        year_label.setObjectName("formLabel")
        year_label.setMaximumWidth(20)
        self.year_input = SpinBox()
        self.year_input.setRange(1900, 2100)
        today = QDate.currentDate()
        self.year_input.setValue(today.year())
        self.year_input.setMinimumWidth(100)

        # Month input
        month_label = QLabel("月")
        month_label.setObjectName("formLabel")
        month_label.setMaximumWidth(20)
        self.month_input = SpinBox()
        self.month_input.setRange(1, 12)
        self.month_input.setValue(today.month())
        self.month_input.setMinimumWidth(80)

        # Day input
        day_label = QLabel("日")
        day_label.setObjectName("formLabel")
        day_label.setMaximumWidth(20)
        self.day_input = SpinBox()
        self.day_input.setRange(1, 31)
        self.day_input.setValue(today.day())
        self.day_input.setMinimumWidth(80)

        date_row.addWidget(self.year_input)
        date_row.addWidget(year_label)
        date_row.addWidget(self.month_input)
        date_row.addWidget(month_label)
        date_row.addWidget(self.day_input)
        date_row.addWidget(day_label)
        date_row.addStretch()

        date_col.addWidget(date_label)
        date_col.addLayout(date_row)

        row1.addLayout(name_col, 2)
        row1.addLayout(date_col, 2)
        info_layout.addLayout(row1)

        # Row 2: 赛事级别 + 奖项等级
        row2 = QHBoxLayout()
        row2.setSpacing(16)
        level_col = QVBoxLayout()
        level_label = QLabel("赛事级别")
        level_label.setObjectName("formLabel")
        self.level_input = ComboBox()
        self.level_input.addItems(["国家级", "省级", "校级"])
        level_col.addWidget(level_label)
        level_col.addWidget(self.level_input)

        rank_col = QVBoxLayout()
        rank_label = QLabel("奖项等级")
        rank_label.setObjectName("formLabel")
        self.rank_input = ComboBox()
        self.rank_input.addItems(["一等奖", "二等奖", "三等奖", "优秀奖"])
        rank_col.addWidget(rank_label)
        rank_col.addWidget(self.rank_input)

        row2.addLayout(level_col, 1)
        row2.addLayout(rank_col, 1)
        info_layout.addLayout(row2)

        # Row 3: 证书编号
        cert_col = QVBoxLayout()
        cert_label = QLabel("证书编号")
        cert_label.setObjectName("formLabel")
        self.certificate_input = LineEdit()
        clean_input_text(self.certificate_input)
        cert_col.addWidget(cert_label)
        cert_col.addWidget(self.certificate_input)
        info_layout.addLayout(cert_col)

        # Row 4: 备注
        remark_col = QVBoxLayout()
        remark_label = QLabel("备注")
        remark_label.setObjectName("formLabel")
        self.remarks_input = LineEdit()
        remark_col.addWidget(remark_label)
        remark_col.addWidget(self.remarks_input)
        info_layout.addLayout(remark_col)

        # 自定义开关
        self.flags_container = QVBoxLayout()
        self.flags_container.setSpacing(8)
        info_layout.addLayout(self.flags_container)
        self._refresh_flag_section()

        layout.addWidget(info_card)

        # 成员输入卡片
        members_card, members_layout = create_card()
        members_layout.addWidget(make_section_title("参与成员"))

        # 成员列表容器 - 直接使用 QWidget，会自动扩展
        self.members_container = QWidget()
        self.members_container.setStyleSheet("QWidget { background-color: transparent; }")
        self.members_list_layout = QVBoxLayout(self.members_container)
        self.members_list_layout.setContentsMargins(0, 0, 0, 0)
        self.members_list_layout.setSpacing(12)
        self.members_list_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)  # 自动调整大小

        # 成员卡片会自动扩展父容器的高度
        members_layout.addWidget(self.members_container)

        # 存储成员数据的列表（用于保存和提取）
        self.members_data = []

        # 添加成员按钮
        add_member_btn = PrimaryPushButton("添加成员")
        add_member_btn.clicked.connect(self._add_member_row)
        members_layout.addWidget(add_member_btn)

        layout.addWidget(members_card)

        # === 附件表格卡片 ===
        attachment_card, attachment_layout = create_card()

        # 标题和添加按钮
        attach_header = QHBoxLayout()
        attach_header.addWidget(make_section_title("附件"))
        attach_header.addStretch()
        attach_btn = PrimaryPushButton("添加文件")
        attach_btn.clicked.connect(self._pick_files)
        attach_header.addWidget(attach_btn)
        attachment_layout.addLayout(attach_header)

        # 附件表格
        self.attach_model = AttachmentTableModel(self)
        self.attach_table = AttachmentTableView()
        self.attach_table.setModel(self.attach_model)
        header = self.attach_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # 序号
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # 附件名
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # MD5
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # 大小
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # 操作
        self.attach_table.verticalHeader().setVisible(False)
        self.attach_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.attach_table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        from ..theme import apply_table_style

        apply_table_style(self.attach_table)
        self.attach_table.fileDropped.connect(self._on_files_dropped)
        attachment_layout.addWidget(self.attach_table)
        layout.addWidget(attachment_card)
        self._resize_attachment_table(0)

        action_row = QHBoxLayout()
        action_row.addStretch()
        self.clear_btn = PushButton("清空表单")
        self.clear_btn.clicked.connect(self._on_clear_clicked)
        self.submit_btn = PrimaryPushButton("保存荣誉")
        self.submit_btn.clicked.connect(self._submit)
        action_row.addWidget(self.clear_btn)
        action_row.addWidget(self.submit_btn)
        layout.addLayout(action_row)
        layout.addStretch()

        self._apply_theme()
        self.refresh()

    def _ai_recognize_certificate(self) -> None:
        if self.editing_award is not None:
            InfoBar.warning("提示", "编辑模式下暂不支持 AI 识别，请先取消编辑或清空表单", parent=self.window())
            return
        if self._ai_busy:
            return

        if self.ctx.settings.get("ai_enabled", "false") != "true":
            InfoBar.warning("AI", "请先在“系统设置 → AI 证书识别”启用并填写配置", parent=self.window())
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择证书图片",
            "",
            "证书文件 (*.pdf *.png *.jpg *.jpeg *.webp);;所有文件 (*.*)",
        )
        if not file_path:
            return

        path = Path(file_path)
        self._add_attachment_files([path])

        self._ai_busy = True
        self.ai_cert_btn.setEnabled(False)
        self._ai_progress = QProgressDialog("正在识别证书…", "取消", 0, 0, self)
        self._ai_progress.setCancelButton(None)
        self._ai_progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._ai_progress.setAutoClose(True)
        self._ai_progress.setMinimumDuration(0)
        self._ai_progress.show()

        def task() -> CertificateExtractedInfo:
            return self.ctx.ai.extract_from_image(path)

        def on_done(result: CertificateExtractedInfo | Exception) -> None:
            self._ai_busy = False
            self.ai_cert_btn.setEnabled(True)
            if self._ai_progress is not None:
                self._ai_progress.close()
                self._ai_progress = None

            if isinstance(result, Exception):
                InfoBar.error("AI 识别失败", str(result), parent=self.window())
                return

            dialog = AICertificatePreviewDialog(self.window(), info=result)

            def on_applied(info: CertificateExtractedInfo) -> None:
                self._apply_ai_certificate_result(info)
                InfoBar.success("AI", "识别完成：已填充表单", parent=self.window())

            dialog.applied.connect(on_applied)
            dialog.show()

        run_in_thread_guarded(task, on_done, guard=self)

    def _apply_ai_certificate_result(self, info: CertificateExtractedInfo) -> None:
        if info.competition_name:
            self.name_input.setText(info.competition_name)
        if info.award_date:
            self.year_input.setValue(info.award_date.year)
            self.month_input.setValue(info.award_date.month)
            self.day_input.setValue(info.award_date.day)
        if info.level and info.level in {"国家级", "省级", "校级"}:
            self.level_input.setCurrentText(info.level)
        if info.rank and info.rank in {"一等奖", "二等奖", "三等奖", "优秀奖"}:
            self.rank_input.setCurrentText(info.rank)
        if info.certificate_code is not None:
            self.certificate_input.setText(info.certificate_code or "")

        if info.member_names:
            for member_data in self.members_data:
                card = member_data.get("card")
                if card is not None:
                    self.members_list_layout.removeWidget(card)
                    card.setParent(None)
                    card.deleteLater()
            self.members_data.clear()
            for name in info.member_names:
                self._add_member_row()
                member_fields = self.members_data[-1]["fields"]
                name_widget = member_fields.get("name")
                if name_widget is not None and hasattr(name_widget, "setText"):
                    name_widget.setText(name)

    def _add_member_row(self) -> None:
        """添加新的成员卡片（表单列表风格）"""
        import logging

        logger = logging.getLogger(__name__)

        # 创建成员卡片 - 使用 QFrame 并设置 card 属性以使用 QSS 定义的样式
        member_card = QFrame()
        member_card.setProperty("card", True)

        # 获取当前样式用于标签
        is_dark = self.theme_manager.is_dark
        label_style = "color: #a6aabb; font-size: 12px;" if is_dark else "color: #666; font-size: 12px;"
        member_layout = QVBoxLayout(member_card)
        member_layout.setContentsMargins(16, 16, 16, 16)
        member_layout.setSpacing(12)

        # 成员编号和删除按钮
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)  # 增加按钮间距
        member_index = len(self.members_data) + 1
        member_label = QLabel(f"成员 #{member_index}")
        member_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        header_layout.addWidget(member_label)

        join_checkbox = CheckBox("加入成员库")
        join_checkbox.setChecked(False)
        header_layout.addWidget(join_checkbox)
        header_layout.addStretch()

        # 上移按钮
        up_btn = TransparentToolButton(FluentIcon.UP)
        up_btn.setToolTip("上移")
        up_btn.setFixedSize(28, 28)
        header_layout.addWidget(up_btn)

        # 下移按钮
        down_btn = TransparentToolButton(FluentIcon.DOWN)
        down_btn.setToolTip("下移")
        down_btn.setFixedSize(28, 28)
        header_layout.addWidget(down_btn)

        # 导入文档按钮
        import_btn = PushButton("导入文档")
        import_btn.setMinimumWidth(85)
        import_btn.setFixedHeight(28)
        header_layout.addWidget(import_btn)

        # 从历史成员选择按钮
        history_btn = PushButton("从历史选择")
        history_btn.setMinimumWidth(95)  # 使用最小宽度而非最大宽度
        history_btn.setFixedHeight(28)  # 固定高度
        header_layout.addWidget(history_btn)

        # 删除按钮
        delete_btn = PushButton("删除")
        delete_btn.setFixedWidth(60)
        delete_btn.setFixedHeight(28)
        header_layout.addWidget(delete_btn)

        member_layout.addLayout(header_layout)

        # 创建3列的表单布局
        form_grid = QGridLayout()
        form_grid.setSpacing(12)
        form_grid.setColumnStretch(1, 1)
        form_grid.setColumnStretch(3, 1)

        # 字段配置：标签、输入框（按2列布局）
        field_names = [
            "name",
            "gender",
            "id_card",
            "phone",
            "student_id",
            "email",
            "school",
            "school_code",
            "major",
            "major_code",
            "class_name",
            "college",
        ]
        field_labels = [
            "姓名",
            "性别",
            "身份证号",
            "手机号",
            "学号",
            "邮箱",
            "学校",
            "学校代码",
            "专业",
            "专业代码",
            "班级",
            "学院",
        ]

        # 存储该成员的所有字段输入框
        member_fields = {}
        label_widgets: dict[str, QLabel] = {}

        # 首先创建所有输入框
        for field_name, label in zip(field_names, field_labels, strict=False):
            # 专业字段使用特殊的搜索组件
            if field_name == "major":
                input_widget = MajorSearchWidget(self.ctx.majors, self.theme_manager, parent=member_card)
            elif field_name == "school":
                input_widget = SchoolSearchWidget(self.ctx.schools, self.theme_manager, parent=member_card)
            else:
                input_widget = LineEdit()
                clean_input_text(input_widget)
                input_widget.setPlaceholderText(f"请输入{label}")
            member_fields[field_name] = input_widget

        # 然后按2列布局添加到表单
        for idx, (field_name, label) in enumerate(zip(field_names, field_labels, strict=False)):
            col = (idx % 2) * 2
            row = idx // 2

            label_widget = QLabel(label)
            label_widget.setStyleSheet(label_style)
            label_widget.setMinimumWidth(50)
            label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 标签居中

            form_grid.addWidget(label_widget, row, col, alignment=Qt.AlignmentFlag.AlignCenter)
            form_grid.addWidget(member_fields[field_name], row, col + 1)
            label_widgets[field_name] = label_widget

        def _apply_join_state(checked: bool) -> None:
            for field_name in field_names:
                if field_name == "name":
                    continue
                widget = member_fields.get(field_name)
                label_widget = label_widgets.get(field_name)
                if widget is not None:
                    widget.setVisible(checked)
                if label_widget is not None:
                    label_widget.setVisible(checked)

        join_checkbox.toggled.connect(_apply_join_state)
        _apply_join_state(join_checkbox.isChecked())

        member_layout.addLayout(form_grid)
        self._connect_member_field_signals(member_fields)

        # 导入文档按钮连接
        import_btn.clicked.connect(lambda: self._import_from_doc(member_fields))

        # 从历史成员选择按钮连接
        history_btn.clicked.connect(lambda: self._select_from_history(member_fields, join_checkbox))

        # 移动按钮连接
        up_btn.clicked.connect(lambda: self._move_member_up(member_card))
        down_btn.clicked.connect(lambda: self._move_member_down(member_card))

        # 删除按钮连接
        delete_btn.clicked.connect(lambda: self._remove_member_card(member_card, member_fields))

        # 保存成员数据
        member_data = {
            "card": member_card,
            "fields": member_fields,
            "label": member_label,
            "join_checkbox": join_checkbox,
        }
        self.members_data.append(member_data)

        # 添加到列表
        self.members_list_layout.addWidget(member_card)

        logger.debug(f"成员 #{member_index} 已添加，总成员数：{len(self.members_data)}")

    def _move_member_up(self, member_card: QWidget) -> None:
        """上移成员卡片"""
        idx = -1
        for i, data in enumerate(self.members_data):
            if data["card"] == member_card:
                idx = i
                break

        if idx <= 0:
            return

        # 交换数据
        self.members_data[idx], self.members_data[idx - 1] = self.members_data[idx - 1], self.members_data[idx]

        # 交换UI位置
        self.members_list_layout.removeWidget(member_card)
        self.members_list_layout.insertWidget(idx - 1, member_card)

        # 更新编号
        self._update_member_indices()

    def _move_member_down(self, member_card: QWidget) -> None:
        """下移成员卡片"""
        idx = -1
        for i, data in enumerate(self.members_data):
            if data["card"] == member_card:
                idx = i
                break

        if idx == -1 or idx >= len(self.members_data) - 1:
            return

        # 交换数据
        self.members_data[idx], self.members_data[idx + 1] = self.members_data[idx + 1], self.members_data[idx]

        # 交换UI位置
        self.members_list_layout.removeWidget(member_card)
        self.members_list_layout.insertWidget(idx + 1, member_card)

        # 更新编号
        self._update_member_indices()

    def _update_member_indices(self) -> None:
        """更新所有成员卡片的编号"""
        for i, data in enumerate(self.members_data):
            if "label" in data:
                data["label"].setText(f"成员 #{i + 1}")

    def _remove_member_card(self, member_card: QWidget, member_fields: dict) -> None:
        """删除一个成员卡片"""
        # 从列表中移除
        for idx, data in enumerate(self.members_data):
            if data["card"] == member_card:
                self.members_data.pop(idx)
                break

        # 从UI中移除
        member_card.deleteLater()

        # 更新编号
        # 使用 QTimer.singleShot 确保在 deleteLater 处理完后更新，或者直接更新
        # 这里直接更新即可，因为 deleteLater 只是标记删除，但 data 已经 pop 了
        self._update_member_indices()

    def _connect_member_field_signals(self, member_fields: dict) -> None:
        school_widget = member_fields.get("school")
        school_code_widget = member_fields.get("school_code")
        major_widget = member_fields.get("major")

        if isinstance(school_widget, SchoolSearchWidget):
            school_widget.schoolSelected.connect(partial(self._on_school_selected, member_fields))

        if isinstance(school_code_widget, QLineEdit):
            school_code_widget.textChanged.connect(partial(self._on_school_code_changed, member_fields))

        if isinstance(major_widget, MajorSearchWidget):
            major_widget.majorSelected.connect(partial(self._on_major_selected, member_fields))

    def _on_school_selected(self, member_fields: dict, name: str, code: str | None) -> None:
        school_code_widget = member_fields.get("school_code")
        major_widget = member_fields.get("major")
        major_code_widget = member_fields.get("major_code")
        college_widget = member_fields.get("college")

        if isinstance(school_code_widget, QLineEdit):
            school_code_widget.blockSignals(True)
            school_code_widget.setText(code or "")
            school_code_widget.blockSignals(False)

        if isinstance(major_widget, MajorSearchWidget):
            major_widget.set_school_filter(name=name, code=code or None)
            major_widget.clear()

        if isinstance(major_code_widget, QLineEdit):
            major_code_widget.clear()
        if isinstance(college_widget, QLineEdit):
            college_widget.clear()

    def _on_school_code_changed(self, member_fields: dict, code: str) -> None:
        major_widget = member_fields.get("major")
        school_widget = member_fields.get("school")
        school_name = school_widget.text() if isinstance(school_widget, SchoolSearchWidget) else None
        if isinstance(major_widget, MajorSearchWidget):
            major_widget.set_school_filter(name=school_name, code=code.strip() or None)

    def _on_major_selected(self, member_fields: dict, name: str, code: str, college: str) -> None:
        major_code_widget = member_fields.get("major_code")
        college_widget = member_fields.get("college")
        if isinstance(major_code_widget, QLineEdit):
            major_code_widget.setText(code or "")
        if isinstance(college_widget, QLineEdit) and college:
            college_widget.setText(college)

    def _select_from_history(self, member_fields: dict, join_checkbox: CheckBox) -> None:
        """从历史成员中选择"""
        # 获取所有历史成员
        from ...services.member_service import MemberService
        from ..widgets.major_search import MajorSearchWidget

        service = MemberService(self.ctx.db)
        members = service.list_members()

        if not members:
            InfoBar.warning("提示", "暂无历史成员记录", parent=self.window())
            return

        # 创建成员选择对话框
        dialog = HistoryMemberDialog(members, self.theme_manager, self.window())
        if dialog.exec():
            selected_member = dialog.selected_member
            if selected_member:
                # 填充成员信息到表单
                join_checkbox.setChecked(True)
                member_fields["name"].setText(selected_member.name)
                member_fields["gender"].setText(selected_member.gender or "")
                member_fields["id_card"].setText(selected_member.id_card or "")
                member_fields["phone"].setText(selected_member.phone or "")
                member_fields["student_id"].setText(selected_member.student_id or "")
                member_fields["email"].setText(selected_member.email or "")
                # 学校及专业字段特殊处理
                school_widget = member_fields.get("school")
                if isinstance(school_widget, SchoolSearchWidget):
                    school_widget.set_school(selected_member.school or "", selected_member.school_code)
                else:
                    widget = member_fields.get("school")
                    if isinstance(widget, QLineEdit):
                        widget.setText(selected_member.school or "")

                school_code_widget = member_fields.get("school_code")
                if isinstance(school_code_widget, QLineEdit):
                    school_code_widget.setText(selected_member.school_code or "")

                major_widget = member_fields["major"]
                if isinstance(major_widget, MajorSearchWidget):
                    major_widget.set_text(selected_member.major or "")
                else:
                    major_widget.setText(selected_member.major or "")

                major_code_widget = member_fields.get("major_code")
                if isinstance(major_code_widget, QLineEdit):
                    major_code_widget.setText(selected_member.major_code or "")

                member_fields["class_name"].setText(selected_member.class_name)
                member_fields["college"].setText(selected_member.college or "")
                InfoBar.success("成功", f"已选择成员: {selected_member.name}", parent=self.window())

    def _import_from_doc(self, member_fields: dict) -> None:
        """从 .doc 文档导入成员信息"""
        import logging

        logger = logging.getLogger(__name__)

        # 打开文件选择对话框
        file_path, _ = QFileDialog.getOpenFileName(self, "选择成员信息文档", "", "Word 文档 (*.doc);;所有文件 (*.*)")

        if not file_path:
            return

        # 创建美化的进度对话框（适配主题）
        progress = QProgressDialog(self.window())
        progress.setWindowTitle("📄 导入成员信息")

        # 根据主题设置文本颜色
        is_dark = self.theme_manager.is_dark
        if is_dark:
            text_color = "#e0e0e0"
            desc_color = "#a0a0a0"
            hint_color = "#808080"
        else:
            text_color = "#333"
            desc_color = "#666"
            hint_color = "#999"

        progress.setLabelText(
            f"<div style='padding: 10px;'>"
            f"<p style='font-size: 14px; margin-bottom: 8px; color: {text_color};'><b>🔄 正在处理文档...</b></p>"
            f"<p style='font-size: 12px; color: {desc_color};'>正在打开 Word 文档并提取成员信息</p>"
            f"<p style='font-size: 12px; color: {hint_color};'>这可能需要几秒钟，请耐心等待 ☕</p>"
            "</div>"
        )
        progress.setRange(0, 0)  # 不确定进度，显示滚动条
        progress.setMinimumWidth(400)
        progress.setMinimumHeight(150)
        progress.setCancelButton(None)  # 不可取消
        progress.setWindowModality(Qt.WindowModality.WindowModal)

        # 根据主题应用美化样式
        if is_dark:
            progress.setStyleSheet("""
                QProgressDialog {
                    background-color: #2b2b2b;
                    border-radius: 8px;
                }
                QLabel {
                    color: #e0e0e0;
                    padding: 15px;
                }
                QProgressBar {
                    border: 2px solid #3a3a3a;
                    border-radius: 5px;
                    text-align: center;
                    background-color: #1e1e1e;
                    color: #e0e0e0;
                    height: 20px;
                }
                QProgressBar::chunk {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #4a90e2, stop:0.5 #5fa3ef, stop:1 #4a90e2);
                    border-radius: 3px;
                }
            """)
        else:
            progress.setStyleSheet("""
                QProgressDialog {
                    background-color: white;
                    border-radius: 8px;
                }
                QLabel {
                    color: #333;
                    padding: 15px;
                }
                QProgressBar {
                    border: 2px solid #e0e0e0;
                    border-radius: 5px;
                    text-align: center;
                    background-color: #f5f5f5;
                    height: 20px;
                }
                QProgressBar::chunk {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #4a90e2, stop:0.5 #5fa3ef, stop:1 #4a90e2);
                    border-radius: 3px;
                }
            """)

        progress.show()
        QApplication.processEvents()  # 强制显示对话框

        try:
            # 提取文档信息（传入邮箱后缀）
            email_suffix = self.ctx.settings.get("email_suffix", "@st.gsau.edu.cn")
            member_info = extract_member_info_from_doc(file_path, email_suffix)

            # 关闭进度对话框
            progress.close()

            # 统计成功提取的字段数量
            extracted_count = sum(1 for v in member_info.values() if v is not None)

            if extracted_count == 0:
                InfoBar.warning("提取失败", "未能从文档中提取到任何信息", parent=self.window())
                logger.warning(f"未从文档中提取到信息: {file_path}")
                return

            # 填充字段（不包括姓名，姓名需要用户手动输入）
            field_mapping = {
                "gender": "gender",
                "id_card": "id_card",
                "phone": "phone",
                "student_id": "student_id",
                "email": "email",
                "school": "school",
                "school_code": "school_code",
                "major": "major",
                "major_code": "major_code",
                "class_name": "class_name",
                "college": "college",
            }

            filled_fields = []
            for field_key, dict_key in field_mapping.items():
                value = member_info.get(dict_key)
                if value and field_key in member_fields:
                    widget = member_fields[field_key]
                    if isinstance(widget, MajorSearchWidget):
                        widget.set_text(value)
                    elif isinstance(widget, SchoolSearchWidget):
                        widget.set_school(value, member_info.get("school_code"))
                    else:
                        widget.setText(value)
                    filled_fields.append(field_key)

            # 显示成功消息
            if filled_fields:
                InfoBar.success(
                    "导入成功",
                    f"已自动填充 {len(filled_fields)} 个字段，请手动输入姓名",
                    parent=self.window(),
                )
                logger.info(f"成功导入 {len(filled_fields)} 个字段: {', '.join(filled_fields)}")

                # 聚焦到姓名输入框
                if "name" in member_fields:
                    member_fields["name"].setFocus()
            else:
                InfoBar.warning("提取失败", "未能从文档中提取到有效信息", parent=self.window())

        except FileNotFoundError as e:
            progress.close()
            InfoBar.error("文件错误", str(e), parent=self.window())
            logger.error(f"文件不存在: {file_path}")
        except Exception as e:
            progress.close()
            InfoBar.error("导入失败", f"提取文档信息时出错: {e!s}", parent=self.window())
            logger.error(f"导入文档失败: {e}", exc_info=True)

    def _get_members_data(self) -> list[dict]:
        """获取成员卡片中的成员数据"""
        from ..widgets.major_search import MajorSearchWidget

        members = []
        field_names = [
            "name",
            "gender",
            "id_card",
            "phone",
            "student_id",
            "email",
            "school",
            "school_code",
            "major",
            "major_code",
            "class_name",
            "college",
        ]

        for member_data in self.members_data:
            member_fields = member_data["fields"]
            join_checkbox = member_data.get("join_checkbox")
            join_member_library = bool(join_checkbox.isChecked()) if isinstance(join_checkbox, CheckBox) else True

            # 获取姓名，如果有则表示成员有效
            name_widget = member_fields.get("name")
            if isinstance(name_widget, QLineEdit):
                name = name_widget.text().strip()
                if name:  # 只记录有姓名的成员
                    member_info = {"name": name, "join_member_library": join_member_library}

                    if join_member_library:
                        # 收集其他字段
                        for field_name in field_names[1:]:
                            widget = member_fields.get(field_name)
                            if isinstance(widget, (MajorSearchWidget, SchoolSearchWidget, QLineEdit)):
                                value = widget.text().strip()
                            else:
                                value = ""

                            if value:
                                member_info[field_name] = value

                    members.append(member_info)
        return members

    def _get_flag_values(self) -> dict[str, bool]:
        return {key: cb.isChecked() for key, cb in self.flag_checkboxes.items()}

    def _pick_files(self) -> None:
        """选择附件文件并添加到表格"""
        files, _ = QFileDialog.getOpenFileNames(self, "选择附件")
        if not files:
            return

        added = self._add_attachment_files(Path(file_path) for file_path in files)
        if added:
            InfoBar.success("成功", f"已添加 {added} 个附件", parent=self.window())
        else:
            InfoBar.info("无新增", "文件已存在或不可用", parent=self.window())

    def _update_attachment_table(self) -> None:
        """更新附件表格显示（异步计算 MD5/大小）"""

        def build_rows():
            rows = []
            display_idx = 1
            for file_path in self.selected_files:
                if not file_path.exists():
                    continue
                md5_hash = self._calculate_md5(file_path)
                try:
                    size_value = file_path.stat().st_size
                except OSError:
                    size_str = "未知"
                else:
                    size_str = self._format_file_size(size_value)
                rows.append(
                    {
                        "index": display_idx,
                        "name": file_path.name,
                        "md5": md5_hash[:16] + "...",
                        "size": size_str,
                        "path": file_path,
                    }
                )
                display_idx += 1
            return rows

        run_in_thread_guarded(build_rows, self._on_attachments_ready, guard=self)

    def _on_attachments_ready(self, rows: list[dict]) -> None:
        if isinstance(rows, Exception):
            logger.exception("附件分析失败: %s", rows)
            InfoBar.error("附件加载失败", str(rows), parent=self.window())
            return
        self.attach_model.set_objects(rows)
        self._resize_attachment_table(len(rows))
        # 设置操作按钮
        for row_idx, _row in enumerate(rows):
            delete_btn = TransparentToolButton(FluentIcon.DELETE)
            delete_btn.setToolTip("删除")
            delete_btn.clicked.connect(lambda checked, r=row_idx: self._remove_attachment(r))
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(4, 0, 4, 0)
            btn_layout.addWidget(delete_btn)
            btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            index = self.attach_model.index(row_idx, 4)
            self.attach_table.setIndexWidget(index, btn_widget)

    def _calculate_md5(self, file_path: Path) -> str:
        """计算文件MD5值"""
        try:
            md5_hash = hashlib.md5()
            with file_path.open("rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    md5_hash.update(chunk)
            return md5_hash.hexdigest()
        except Exception:
            return "无法计算"

    def _format_file_size(self, size: int | float) -> str:
        """格式化文件大小"""
        size_float = float(size)
        for unit in ["B", "KB", "MB", "GB"]:
            if size_float < 1024.0:
                return f"{size_float:.1f} {unit}"
            size_float /= 1024.0
        return f"{size_float:.1f} TB"

    def _remove_attachment(self, row: int) -> None:
        """删除指定行的附件"""
        if 0 <= row < len(self.selected_files):
            removed = self.selected_files.pop(row)
            self._selected_file_keys.discard(self._to_file_key(removed))
            self._update_attachment_table()

    def load_award_for_editing(self, award) -> None:
        """加载荣誉信息用于编辑"""
        self._refresh_flag_section()
        self.editing_award = award
        self.submit_btn.setText("更新荣誉")
        self.clear_btn.setText("取消编辑")
        self._attachments_loaded_for_edit = False

        # 填充基本信息
        self.name_input.setText(award.competition_name)
        self.year_input.setValue(award.award_date.year)
        self.month_input.setValue(award.award_date.month)
        self.day_input.setValue(award.award_date.day)
        self.level_input.setCurrentText(award.level)
        self.rank_input.setCurrentText(award.rank)
        self.certificate_input.setText(award.certificate_code or "")
        self.remarks_input.setText(award.remarks or "")

        # 清空并填充成员信息（使用新的表单卡片风格）
        for member_data in self.members_data:
            member_data["card"].deleteLater()
        self.members_data.clear()

        for assoc in award.award_members:
            # 添加新的成员卡片
            self._add_member_row()

            # 填充最后添加的成员卡片的数据
            member_data = self.members_data[-1]
            member_fields = member_data["fields"]
            join_checkbox = member_data.get("join_checkbox")

            member = getattr(assoc, "member", None)
            member_id = getattr(assoc, "member_id", None)
            linked = member is not None and member_id is not None
            if isinstance(join_checkbox, CheckBox):
                join_checkbox.setChecked(bool(linked))

            field_mapping = {"name": assoc.member_name or ""}
            if member is not None and member_id is not None:
                field_mapping.update(
                    {
                        "gender": member.gender or "",
                        "id_card": member.id_card or "",
                        "phone": member.phone or "",
                        "student_id": member.student_id or "",
                        "email": member.email or "",
                        "school": member.school or "",
                        "school_code": member.school_code or "",
                        "major": member.major or "",
                        "major_code": member.major_code or "",
                        "class_name": member.class_name or "",
                        "college": member.college or "",
                    }
                )

            for field_name, value in field_mapping.items():
                widget = member_fields.get(field_name)
                if widget is None:
                    continue
                if field_name == "school" and isinstance(widget, SchoolSearchWidget):
                    widget.set_school(
                        value or "", member.school_code if member is not None and member_id is not None else None
                    )
                elif isinstance(widget, MajorSearchWidget):
                    widget.set_text(value)
                else:
                    widget.setText(value)

        # 自定义开关
        if self.flag_defs:
            try:
                flag_values = self.ctx.flags.get_award_flags(award.id)
            except Exception:
                flag_values = {}
            for key, cb in self.flag_checkboxes.items():
                cb.setChecked(bool(flag_values.get(key, cb.isChecked())))

        self._load_existing_attachments(award.id)

    def refresh(self) -> None:
        self._refresh_flag_section()

    def _load_existing_attachments(self, award_id: int) -> None:
        try:
            from sqlalchemy.orm import joinedload

            from ...data.models import Award

            self.selected_files = []
            self._selected_file_keys.clear()
            with self.ctx.db.session_scope() as session:
                award = session.query(Award).options(joinedload(Award.attachments)).filter(Award.id == award_id).first()
                if not award:
                    return
                root = Path(self.ctx.settings.get("attachment_root", "attachments"))
                for attachment in award.attachments:
                    if getattr(attachment, "deleted", False):
                        continue
                    file_path = (root / attachment.relative_path).resolve()
                    if not file_path.exists():
                        continue
                    key = self._to_file_key(file_path)
                    if key in self._selected_file_keys:
                        continue
                    self.selected_files.append(file_path)
                    self._selected_file_keys.add(key)
            self._attachments_loaded_for_edit = True
            self._update_attachment_table()
        except Exception as exc:
            logger.warning("加载附件失败: %s", exc, exc_info=True)
            self._attachments_loaded_for_edit = False

    def _submit(self) -> None:
        issues = self._validate_form()
        if issues:
            InfoBar.warning("表单不合法", issues[0], parent=self.window())
            return

        members_data = self._get_members_data()

        award_date = cast(
            date,
            QDate(
                self.year_input.value(),
                self.month_input.value(),
                self.day_input.value(),
            ).toPython(),
        )

        should_back_to_overview = bool(self.editing_award)
        if self.editing_award:
            award = self.ctx.awards.update_award(
                self.editing_award.id,
                competition_name=self.name_input.text().strip(),
                award_date=award_date,
                level=self.level_input.currentText(),
                rank=self.rank_input.currentText(),
                certificate_code=self.certificate_input.text().strip() or None,
                remarks=self.remarks_input.text().strip() or None,
                member_names=members_data,
                attachment_files=self.selected_files if self._attachments_loaded_for_edit else None,
                flag_values=self._get_flag_values(),
            )
            InfoBar.success("成功", f"已更新：{award.competition_name}", parent=self.window())
        else:
            # 创建模式：创建新荣誉
            award = self.ctx.awards.create_award(
                competition_name=self.name_input.text().strip(),
                award_date=award_date,
                level=self.level_input.currentText(),
                rank=self.rank_input.currentText(),
                certificate_code=self.certificate_input.text().strip() or None,
                remarks=self.remarks_input.text().strip() or None,
                member_names=members_data,
                attachment_files=self.selected_files,
                flag_values=self._get_flag_values(),
            )
            InfoBar.success("成功", f"已保存：{award.competition_name}", parent=self.window())

        self._clear_form(silent=True)
        if should_back_to_overview:
            main_window = self.window()
            if (
                main_window is None
                or not hasattr(main_window, "navigate_to")
                or not hasattr(main_window, "overview_page")
            ):
                return

            def _go_back() -> None:
                mw = cast(Any, main_window)
                with suppress(Exception):
                    mw.switchTo(mw.overview_page)
                mw.navigate_to("overview")

            QTimer.singleShot(0, _go_back)

    def _validate_form(self) -> list[str]:
        """验证荣誉表单，返回错误信息列表，空列表表示验证通过"""
        issues: list[str] = []

        # 验证比赛名称
        name = self.name_input.text().strip()
        valid, msg = FormValidator.validate_competition_name(name)
        if not valid:
            issues.append(msg)
            self._highlight_field_error(self.name_input)
            return issues

        # 验证获奖日期
        try:
            award_date = QDate(
                self.year_input.value(),
                self.month_input.value(),
                self.day_input.value(),
            )
            if not award_date.isValid():
                issues.append("获奖日期不合法。")
                return issues
            elif award_date > QDate.currentDate():
                issues.append("获奖日期不能晚于今天。")
                return issues
        except Exception:
            issues.append("获奖日期不合法。")
            return issues

        # 验证证书号和备注
        code = self.certificate_input.text().strip()
        valid, msg = FormValidator.validate_certificate_code(code)
        if not valid:
            issues.append(msg)
            self._highlight_field_error(self.certificate_input)
            return issues

        remarks = self.remarks_input.text().strip()
        valid, msg = FormValidator.validate_remarks(remarks)
        if not valid:
            issues.append(msg)
            self._highlight_field_error(self.remarks_input)
            return issues

        # 验证成员
        members_data = self._get_members_data()
        if not members_data:
            issues.append("请至少添加一名成员。")
            return issues

        for i, member in enumerate(members_data, 1):
            member_errors = FormValidator.validate_member_info(member)
            if member_errors:
                issues.append(f"成员 {i} - {member_errors[0]}")
                if i - 1 < len(self.members_data):
                    self._highlight_member_error(i - 1)
                return issues

        return issues

    def _highlight_field_error(self, field_widget: QLineEdit) -> None:
        """高亮出错的字段"""
        field_widget.setStyleSheet("""
            QLineEdit {
                border: 2px solid #ff6b6b;
                border-radius: 4px;
                padding: 4px;
                background-color: rgba(255, 107, 107, 0.1);
            }
        """)
        # 3 秒后移除高亮
        from PySide6.QtCore import QTimer

        QTimer.singleShot(3000, lambda: field_widget.setStyleSheet(""))

    def _highlight_member_error(self, member_index: int) -> None:
        """高亮出错的成员卡片"""
        if 0 <= member_index < len(self.members_data):
            member_card = self.members_data[member_index]["card"]
            member_card.setStyleSheet("""
                QFrame {
                    border: 2px solid #ff6b6b;
                    border-radius: 8px;
                }
            """)
            # 3 秒后移除高亮
            from PySide6.QtCore import QTimer

            QTimer.singleShot(3000, lambda: member_card.setStyleSheet(""))

    def _on_clear_clicked(self) -> None:
        was_editing = self.editing_award is not None
        self._clear_form(silent=False)
        if not was_editing:
            return

        main_window = self.window()
        if main_window is None or not hasattr(main_window, "navigate_to") or not hasattr(main_window, "overview_page"):
            return

        def _go_back() -> None:
            mw = cast(Any, main_window)
            with suppress(Exception):
                mw.switchTo(mw.overview_page)
            mw.navigate_to("overview")

        QTimer.singleShot(0, _go_back)

    def _clear_form(self, *, silent: bool = False) -> None:
        """清空表单，重置为新建状态"""
        was_editing = self.editing_award is not None
        self.editing_award = None
        self._attachments_loaded_for_edit = False
        self.submit_btn.setText("保存荣誉")
        self.clear_btn.setText("清空表单")
        self.name_input.clear()
        today = QDate.currentDate()
        self.year_input.setValue(today.year())
        self.month_input.setValue(today.month())
        self.day_input.setValue(today.day())
        self.level_input.setCurrentIndex(0)
        self.rank_input.setCurrentIndex(0)
        self.certificate_input.clear()
        self.remarks_input.clear()
        self._refresh_flag_section()
        for flag in self.flag_defs:
            cb = self.flag_checkboxes.get(flag.key)
            if cb:
                cb.setChecked(bool(flag.default_value))
        self.selected_files = []
        self._selected_file_keys.clear()
        self._update_attachment_table()
        # 清空所有成员卡片
        for member_data in self.members_data[:]:  # 使用副本遍历
            member_card = member_data["card"]
            member_fields = member_data["fields"]
            self._remove_member_card(member_card, member_fields)
        # 添加一个空白成员卡片
        self._add_member_row()
        if not silent:
            message = "已退出编辑" if was_editing else "表单已清空"
            InfoBar.success("成功", message, duration=2000, parent=self.window())

    def _on_files_dropped(self, files: list[Path]) -> None:
        added = self._add_attachment_files(files)
        if added:
            InfoBar.success("成功", f"拖入 {added} 个附件", parent=self.window())
        else:
            InfoBar.info("无新增", "拖入的文件不可用或已存在", parent=self.window())

    def _add_attachment_files(self, files: Iterable[Path]) -> int:
        added = 0
        duplicates: list[str] = []
        for file_path in files:
            resolved = Path(file_path).resolve()
            if not resolved.exists():
                continue

            # MD5 去重：若数据库已有相同文件则提示并跳过
            md5_value = self._calculate_md5(resolved)
            try:
                size_value = resolved.stat().st_size
            except OSError:
                size_value = None
            current_award_id = getattr(getattr(self, "editing_award", None), "id", None)
            if (
                md5_value
                and md5_value != "无法计算"
                and self.ctx.attachments.has_duplicate(md5_value, size_value, award_id=current_award_id)
            ):
                duplicates.append(resolved.name)
                continue

            key = self._to_file_key(resolved)
            if key in self._selected_file_keys:
                continue
            self.selected_files.append(resolved)
            self._selected_file_keys.add(key)
            added += 1

        if added:
            self._update_attachment_table()
        if duplicates:
            sample = "，".join(duplicates[:3])
            more = "" if len(duplicates) <= 3 else f" 等 {len(duplicates)} 个"
            InfoBar.warning("重复附件", f"{sample}{more} 与已有附件 MD5 相同，已跳过", parent=self.window())
        return added

    def _resize_attachment_table(self, row_count: int) -> None:
        header = self.attach_table.horizontalHeader()
        header_height = header.height() or 40
        row_height = self.attach_table.verticalHeader().defaultSectionSize() or 48
        visible_rows = min(max(row_count, 3), 8)
        target_height = header_height + row_height * visible_rows + 12
        self.attach_table.setMinimumHeight(target_height)
        self.attach_table.setMaximumHeight(target_height)

    def _to_file_key(self, path: Path) -> str:
        return str(path.resolve()).lower()

    def _apply_theme(self) -> None:
        """应用主题到滚动区域"""
        is_dark = self.theme_manager.is_dark
        scroll_bg = "#232635" if is_dark else "#f4f6fb"

        scroll_stylesheet = f"""
            QScrollArea {{
                border: none;
                background-color: {scroll_bg};
            }}
            QScrollArea > QWidget {{
                background-color: {scroll_bg};
            }}
            QWidget#scrollContent {{
                background-color: {scroll_bg};
            }}
        """
        self.scrollArea.setStyleSheet(scroll_stylesheet)
        # 确保内部容器也有正确的背景色
        scroll_widget = self.scrollArea.widget()
        if scroll_widget:
            scroll_widget.setObjectName("scrollContent")
            scroll_widget.setAutoFillBackground(True)
            palette = scroll_widget.palette()
            palette.setColor(
                palette.ColorRole.Window,
                {"#232635": QColor(35, 38, 53), "#f4f6fb": QColor(244, 246, 251)}[scroll_bg],
            )
            scroll_widget.setPalette(palette)

    def _refresh_flag_section(self) -> None:
        def _clear_layout(layout: QLayout) -> None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                    continue
                child_layout = item.layout()
                if child_layout is not None:
                    _clear_layout(child_layout)
                    child_layout.deleteLater()

        _clear_layout(self.flags_container)
        self.flag_checkboxes.clear()
        try:
            self.flag_defs = self.ctx.flags.list_flags(enabled_only=True)
        except Exception:
            self.flag_defs = []
        if not self.flag_defs:
            return
        title = QLabel("自定义开关")
        title.setObjectName("formLabel")
        self.flags_container.addWidget(title)
        flags_row = QHBoxLayout()
        flags_row.setSpacing(12)
        for flag in self.flag_defs:
            cb = CheckBox(flag.label)
            cb.setChecked(bool(flag.default_value))
            self.flag_checkboxes[flag.key] = cb
            flags_row.addWidget(cb)
        flags_row.addStretch()
        self.flags_container.addLayout(flags_row)

    @Slot()
    def _on_theme_changed(self) -> None:
        """主题切换时重新应用样式"""
        # 更新滚动区域背景 - 卡片样式由 QSS 自动处理
        self._apply_theme()


class HistoryMemberDialog(MaskDialogBase):
    """历史成员选择对话框"""

    def __init__(self, members: list, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)

        self.members = members
        self.theme_manager = theme_manager
        self.selected_member = None
        self.member_widgets = []

        self.setWindowTitle("选择历史成员")
        self.setMinimumWidth(650)
        self.setMinimumHeight(500)
        self.widget.setGraphicsEffect(cast(QGraphicsEffect, None))

        self._init_ui()
        self._apply_theme()

    def _init_ui(self):
        """初始化UI（美化版）"""
        from qfluentwidgets import PushButton, SearchLineEdit

        # 使用 MaskDialogBase 的 widget 作为容器
        container = self.widget
        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(20)

        # === 标题 ===
        title_label = QLabel("选择历史成员")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title_label)

        # === 搜索框区域 ===
        search_card = QFrame()
        search_card.setProperty("card", True)
        search_layout = QHBoxLayout(search_card)
        search_layout.setContentsMargins(12, 12, 12, 12)
        search_layout.setSpacing(12)

        # 搜索输入框（带内置搜索图标）
        self.search_input = SearchLineEdit()
        self.search_input.setPlaceholderText("输入姓名、学号、手机号、邮箱或学院搜索...")
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.search_input.setMinimumHeight(36)
        search_layout.addWidget(self.search_input)

        layout.addWidget(search_card)

        # === 结果计数提示 ===
        self.result_label = QLabel(f"共 {len(self.members)} 位成员")
        is_dark = self.theme_manager.is_dark
        self.result_label.setStyleSheet(f"color: {'#a0a0a0' if is_dark else '#666'}; font-size: 12px;")
        layout.addWidget(self.result_label)

        # === 成员列表（滚动区域）===
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(420)
        scroll.setMinimumWidth(650)
        scroll.setObjectName("memberScrollArea")

        scroll_widget = QWidget()
        self.members_layout = QVBoxLayout(scroll_widget)
        self.members_layout.setSpacing(10)
        self.members_layout.setContentsMargins(0, 0, 8, 0)  # 右边留点空间给滚动条

        # 创建成员卡片
        for member in self.members:
            member_card = self._create_member_card(member)
            self.members_layout.addWidget(member_card)
            self.member_widgets.append((member, member_card))

        self.members_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # === 底部提示 ===
        hint_label = QLabel("点击任意成员卡片即可选择")
        hint_label.setStyleSheet(f"color: {'#808080' if is_dark else '#999'}; font-size: 11px;")
        hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint_label)

        # === 按钮区域 ===
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = PushButton("取消")
        cancel_btn.setMinimumWidth(100)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _create_member_card(self, member) -> QWidget:
        """创建美化的成员卡片"""
        card = QFrame()
        card.setProperty("card", True)  # 使用 QSS 定义的 Fluent 卡片样式
        card.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # 点击选择
        def select_member():
            self.selected_member = member
            self.accept()

        # 使用点击事件
        card.mousePressEvent = lambda e: select_member() if e.button() == Qt.MouseButton.LeftButton else None

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        # === 头部：姓名 + 学号标签 ===
        header = QHBoxLayout()
        header.setSpacing(12)

        # 姓名（加粗 + 大字体）
        name_label = QLabel(f"<b>{member.name or '未知'}</b>")
        name_label.setStyleSheet("font-size: 15px; font-weight: 600;")
        header.addWidget(name_label)

        header.addStretch()

        # 学号标签（蓝色背景徽章）
        if member.student_id:
            student_badge = QLabel(f" {member.student_id} ")
            is_dark = self.theme_manager.is_dark
            if is_dark:
                badge_style = """
                    background-color: #2d4a7c;
                    color: #5fa3ef;
                    border-radius: 4px;
                    padding: 4px 10px;
                    font-size: 11px;
                    font-weight: 500;
                """
            else:
                badge_style = """
                    background-color: #e6f4ff;
                    color: #1890ff;
                    border-radius: 4px;
                    padding: 4px 10px;
                    font-size: 11px;
                    font-weight: 500;
                """
            student_badge.setStyleSheet(badge_style)
            header.addWidget(student_badge)

        layout.addLayout(header)

        # === 分隔线 ===
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        is_dark = self.theme_manager.is_dark
        separator.setStyleSheet(f"background-color: {'#4a4a5e' if is_dark else '#e8e8e8'}; max-height: 1px;")
        layout.addWidget(separator)

        # === 详细信息网格（2列布局）===
        info_layout = QGridLayout()
        info_layout.setSpacing(10)
        info_layout.setColumnStretch(1, 1)
        info_layout.setColumnStretch(3, 1)

        info_data = [
            ("学校", member.school or "-"),
            ("学校代码", member.school_code or "-"),
            ("学院", member.college or "-"),
            ("专业", member.major or "-"),
            ("专业代码", member.major_code or "-"),
            ("班级", member.class_name or "-"),
            ("性别", member.gender or "-"),
            ("手机", member.phone or "-"),
            ("邮箱", member.email or "-"),
        ]

        for idx, (label, value) in enumerate(info_data):
            row = idx // 2
            col = (idx % 2) * 2

            # 标签（灰色小字）
            label_widget = QLabel(f"{label}")
            if is_dark:
                label_widget.setStyleSheet("color: #a0a0a0; font-size: 11px; min-width: 36px;")
            else:
                label_widget.setStyleSheet("color: #888; font-size: 11px; min-width: 36px;")

            # 值（正常字体）
            value_widget = QLabel(str(value))
            if is_dark:
                value_widget.setStyleSheet("color: #e0e0e0; font-size: 12px;")
            else:
                value_widget.setStyleSheet("color: #333; font-size: 12px;")
            value_widget.setWordWrap(True)

            info_layout.addWidget(
                label_widget,
                row,
                col,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            )
            info_layout.addWidget(value_widget, row, col + 1)

        layout.addLayout(info_layout)

        return card

    def _on_search_text_changed(self, text: str) -> None:
        """搜索框文本变化时自动清理并过滤"""
        import re

        # 自动移除所有空白字符
        cleaned_text = re.sub(r"\s+", "", text)

        # 如果清理后文本变化了，更新输入框（避免递归）
        if cleaned_text != text:
            # 暂时断开信号避免递归
            self.search_input.textChanged.disconnect(self._on_search_text_changed)
            self.search_input.setText(cleaned_text)
            # 重新连接信号
            self.search_input.textChanged.connect(self._on_search_text_changed)

        # 执行过滤
        self._filter_members(cleaned_text)

    def _filter_members(self, text: str):
        """根据搜索文本过滤成员（去除所有空白字符）"""
        import re

        # 移除所有空白字符（空格、制表符、换行符等）
        text = re.sub(r"\s+", "", text).lower()

        if not text:
            # 空文本显示所有
            for _member, card in self.member_widgets:
                card.show()
            self.result_label.setText(f"共 {len(self.members)} 位成员")
            return

        visible_count = 0
        for member, card in self.member_widgets:
            # 对所有字段也去除空白字符后再比较
            def clean(s):
                return re.sub(r"\s+", "", (s or "")).lower()

            match = (
                text in clean(member.name)
                or text in clean(member.student_id)
                or text in clean(member.phone)
                or text in clean(member.email)
                or text in clean(member.id_card)
                or text in clean(member.college)
                or text in clean(member.major)
                or text in clean(member.class_name)
            )
            card.setVisible(match)
            if match:
                visible_count += 1

        # 更新结果计数
        self.result_label.setText(f"找到 {visible_count} 位成员")

    def _apply_theme(self):
        """应用主题样式（使用统一的 QSS 颜色）"""
        is_dark = self.theme_manager.is_dark

        if is_dark:
            bg_color = "#232635"
            card_bg = "#2a2d3f"
            card_hover = "#353751"
            border_color = "rgba(138, 159, 255, 0.08)"
            text_color = "#f2f4ff"
        else:
            bg_color = "#f8f9fa"
            card_bg = "#ffffff"
            card_hover = "#f5f7fa"
            border_color = "#e0e0e0"
            text_color = "#333"

        # 设置中心 widget 的样式
        self.widget.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                color: {text_color};
            }}
            QLabel {{
                background-color: transparent;
            }}
            QFrame[card="true"] {{
                background-color: {card_bg};
                border: 1px solid {border_color};
                border-radius: 12px;
            }}
            QFrame[card="true"]:hover {{
                background-color: {card_hover};
                border: 1px solid #5a80f3;
            }}
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
            QScrollArea > QWidget > QWidget {{
                background-color: transparent;
            }}
            QScrollBar:vertical {{
                background-color: transparent;
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background-color: rgba(138, 159, 255, 0.3);
                border-radius: 4px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: rgba(138, 159, 255, 0.5);
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        # 设置对话框圆角
        self.widget.setObjectName("centerWidget")
        self.widget.setStyleSheet(
            self.widget.styleSheet()
            + f"""
            QWidget#centerWidget {{
                background-color: {bg_color};
                border-radius: 12px;
            }}
        """
        )
