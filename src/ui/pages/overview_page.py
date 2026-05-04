import logging
from collections.abc import Iterable
from contextlib import suppress
from datetime import date
from functools import partial
from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import QDate, QPoint, QRect, Qt, QTimer, Slot
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QFileDialog,
    QGraphicsEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    CheckBox,
    ComboBox,
    DateEdit,
    FluentIcon,
    IconWidget,
    InfoBar,
    LineEdit,
    MaskDialogBase,
    MessageBox,
    PrimaryPushButton,
    PushButton,
    ScrollArea,
    SpinBox,
    TitleLabel,
    TransparentToolButton,
)

from ...services.doc_extractor import extract_member_info_from_doc
from ...services.validators import FormValidator
from ..styled_theme import ThemeManager
from ..table_models import AttachmentTableModel
from ..theme import create_card, create_page_header, make_section_title
from ..utils.async_utils import run_in_thread_guarded
from ..widgets.attachment_preview_dialog import AttachmentPreviewDialog
from ..widgets.attachment_table_view import AttachmentTableView
from ..widgets.fluent_dialogs import FluentProgressDialog
from ..widgets.major_search import MajorSearchWidget
from ..widgets.school_search import SchoolSearchWidget
from .base_page import BasePage

logger = logging.getLogger(__name__)


def clean_input_text(line_edit: LineEdit) -> None:
    """
    为 LineEdit 添加自动清理空白字符功能
    自动删除用户输入中的所有空格、制表符、换行符等空白字符

    Args:
        line_edit: 要应用清理功能的 LineEdit 组件
    """
    import re

    def on_text_changed(text: str) -> None:
        cleaned = re.sub(r"\s+", "", text)
        if cleaned != text:
            line_edit.textChanged.disconnect(on_text_changed)
            line_edit.setText(cleaned)
            line_edit.setCursorPosition(len(cleaned))
            line_edit.textChanged.connect(on_text_changed)

    line_edit.textChanged.connect(on_text_changed)


class OverviewPage(BasePage):
    """总览页面 - 显示所有已输入的荣誉项目"""

    MAX_OVERVIEW_ITEMS = 5000

    def __init__(self, ctx, theme_manager: ThemeManager):
        super().__init__(ctx, theme_manager)
        self.awards_list = []
        self.selected_award_ids = set()
        self.is_batch_mode = False
        self.card_checkboxes: dict[int, CheckBox] = {}

        self.PAGE_SIZE = 20
        self.current_page = 0
        self.total_awards = 0
        self.load_more_btn = None  # 保存加载更多按钮引用
        self._load_more_container: QWidget | None = None
        self._loaded_count = 0
        self._loading_more = False

        # 筛选条件
        self.filter_level = "全部"  # 等级筛选
        self.filter_rank = "全部"  # 奖项筛选
        self.filter_start_date: date | None = None  # 开始日期
        self.filter_end_date: date | None = None  # 结束日期
        self.filter_keyword = ""  # 关键词搜索
        self.flag_defs: list = []
        self.flag_defaults: dict[str, bool] = {}
        self.flag_filters: dict[str, str] = {}
        self.flag_filter_widgets: dict[str, ComboBox] = {}
        self.award_flag_values: dict[int, dict[str, bool]] = {}

        # 排序条件
        self.sort_by = "日期降序"  # 默认按日期降序

        # 连接主题变化信号
        self.theme_manager.themeChanged.connect(self._on_theme_changed)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        title_widget = QWidget()
        title_widget.setObjectName("pageRoot")
        title_layout = QVBoxLayout(title_widget)
        title_layout.setContentsMargins(32, 24, 32, 0)
        title_layout.setSpacing(0)
        title_layout.addWidget(create_page_header("所有荣誉项目", "查看和管理已输入的所有荣誉信息"))
        outer_layout.addWidget(title_widget)

        self.scrollArea = ScrollArea()
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

        # 筛选区域
        filter_card, filter_layout = create_card()
        self._create_filter_section(filter_layout)
        layout.addWidget(filter_card)

        # 荣誉项目卡片
        card, card_layout = create_card()

        # 标题和刷新按钮
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        header_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(make_section_title("荣誉列表"))
        header_layout.addStretch()
        from qfluentwidgets import FluentIcon, TransparentToolButton

        header_tools = QHBoxLayout()
        header_tools.setContentsMargins(0, 0, 0, 0)
        header_tools.setSpacing(8)

        # 批量选择操作按钮
        self.select_all_btn = PushButton("全选")
        self.select_all_btn.setFixedWidth(72)
        self.select_all_btn.setVisible(False)
        self.select_all_btn.clicked.connect(self._select_all_awards)
        header_tools.addWidget(self.select_all_btn)

        self.invert_selection_btn = PushButton("反选")
        self.invert_selection_btn.setFixedWidth(72)
        self.invert_selection_btn.setVisible(False)
        self.invert_selection_btn.clicked.connect(self._invert_selection)
        header_tools.addWidget(self.invert_selection_btn)

        self.clear_selection_btn = PushButton("全不选")
        self.clear_selection_btn.setFixedWidth(72)
        self.clear_selection_btn.setVisible(False)
        self.clear_selection_btn.clicked.connect(self._clear_selection)
        header_tools.addWidget(self.clear_selection_btn)

        # 批量删除按钮
        self.batch_delete_btn = TransparentToolButton(FluentIcon.DELETE, self)
        self.batch_delete_btn.setToolTip("删除选中项目")
        self.batch_delete_btn.clicked.connect(self._batch_delete_awards)
        self.batch_delete_btn.setEnabled(False)
        self.batch_delete_btn.hide()
        header_tools.addWidget(self.batch_delete_btn)

        # 批量管理按钮
        self.batch_mode_btn = TransparentToolButton(FluentIcon.EDIT, self)
        self.batch_mode_btn.setToolTip("批量管理")
        self.batch_mode_btn.setCheckable(True)
        self.batch_mode_btn.toggled.connect(self._toggle_batch_mode)
        header_tools.addWidget(self.batch_mode_btn)

        refresh_btn = TransparentToolButton(FluentIcon.SYNC)
        refresh_btn.setToolTip("刷新数据")
        refresh_btn.clicked.connect(self.refresh)
        header_tools.addWidget(refresh_btn)
        header_layout.addLayout(header_tools)
        card_layout.addLayout(header_layout)

        # 荣誉项目容器
        self.awards_container = QWidget()
        self.awards_layout = QVBoxLayout(self.awards_container)
        self.awards_layout.setContentsMargins(0, 0, 0, 0)
        self.awards_layout.setSpacing(12)

        card_layout.addWidget(self.awards_container)

        layout.addWidget(card)
        layout.addStretch()

        self._cached_award_signature: tuple[int, str] | None = None
        self._refresh_seq = 0

        # 自动刷新定时器（每5秒检查一次数据）
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._auto_refresh)
        self.refresh_timer.setInterval(5000)

        self._apply_theme()

    def _create_filter_section(self, parent_layout: QVBoxLayout) -> None:
        """创建筛选区域"""
        # 标题
        parent_layout.addWidget(make_section_title("筛选条件"))

        # 第一行：等级、奖项、关键词搜索
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        # 等级筛选
        level_label = BodyLabel("等级:")
        level_label.setMinimumWidth(44)
        row1.addWidget(level_label)

        self.level_combo = ComboBox()
        self.level_combo.addItems(["全部", "国家级", "省级", "校级"])
        self.level_combo.setCurrentText(self.filter_level)
        self.level_combo.currentTextChanged.connect(self._on_filter_changed)
        self.level_combo.setMinimumWidth(96)
        self.level_combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        row1.addWidget(self.level_combo)

        # 奖项筛选
        rank_label = BodyLabel("奖项:")
        rank_label.setMinimumWidth(44)
        row1.addWidget(rank_label)

        self.rank_combo = ComboBox()
        self.rank_combo.addItems(["全部", "一等奖", "二等奖", "三等奖", "优秀奖"])
        self.rank_combo.setCurrentText(self.filter_rank)
        self.rank_combo.currentTextChanged.connect(self._on_filter_changed)
        self.rank_combo.setMinimumWidth(96)
        self.rank_combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        row1.addWidget(self.rank_combo)

        # 关键词搜索
        keyword_label = BodyLabel("关键词:")
        keyword_label.setMinimumWidth(44)
        row1.addWidget(keyword_label)

        self.keyword_input = LineEdit()
        self.keyword_input.setPlaceholderText("输入竞赛名称或证书编号...")
        self.keyword_input.textChanged.connect(self._on_keyword_changed)
        self.keyword_input.setMinimumWidth(120)
        self.keyword_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row1.addWidget(self.keyword_input)

        row1.addStretch()
        parent_layout.addLayout(row1)

        parent_layout.addSpacing(12)

        # 第二行：日期范围
        row2 = QHBoxLayout()
        row2.setSpacing(10)

        # 开始日期
        start_label = BodyLabel("开始日期:")
        start_label.setMinimumWidth(44)
        row2.addWidget(start_label)

        self.start_date_edit = DateEdit()
        self.start_date_edit.setDate(QDate(2020, 1, 1))  # 默认起始日期
        self.start_date_edit.dateChanged.connect(self._on_filter_changed)
        self.start_date_edit.setMinimumWidth(96)
        self.start_date_edit.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.start_date_edit.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.start_date_edit.setSymbolVisible(False)
        row2.addWidget(self.start_date_edit)

        # 结束日期
        end_label = BodyLabel("结束日期:")
        end_label.setMinimumWidth(44)
        row2.addWidget(end_label)

        self.end_date_edit = DateEdit()
        self.end_date_edit.setDate(QDate.currentDate())  # 默认当前日期
        self.end_date_edit.dateChanged.connect(self._on_filter_changed)
        self.end_date_edit.setMinimumWidth(96)
        self.end_date_edit.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.end_date_edit.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.end_date_edit.setSymbolVisible(False)
        row2.addWidget(self.end_date_edit)

        # 排序方式
        sort_label = BodyLabel("排序:")
        sort_label.setMinimumWidth(44)
        row2.addWidget(sort_label)

        self.sort_combo = ComboBox()
        self.sort_combo.addItems(
            [
                "日期降序",
                "日期升序",
                "等级降序",
                "等级升序",
                "奖项降序",
                "奖项升序",
                "名称A-Z",
                "名称Z-A",
            ]
        )
        self.sort_combo.setCurrentText(self.sort_by)
        self.sort_combo.currentTextChanged.connect(self._on_sort_changed)
        self.sort_combo.setMinimumWidth(96)
        self.sort_combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        row2.addWidget(self.sort_combo)

        # 重置按钮
        reset_btn = PushButton("重置筛选")
        reset_btn.setIcon(FluentIcon.ERASE_TOOL)
        reset_btn.clicked.connect(self._reset_filters)
        reset_btn.setMinimumWidth(88)
        reset_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        row2.addWidget(reset_btn)

        row2.addStretch()
        parent_layout.addLayout(row2)

        # 动态：自定义开关筛选
        self.flag_filter_container = QVBoxLayout()
        self.flag_filter_container.setSpacing(6)
        parent_layout.addLayout(self.flag_filter_container)
        self._load_flag_definitions()
        self._rebuild_flag_filters()

    def _on_filter_changed(self) -> None:
        """筛选条件改变时触发"""
        self.filter_level = self.level_combo.currentText()
        self.filter_rank = self.rank_combo.currentText()
        self.filter_start_date = cast(date, self.start_date_edit.date().toPython())
        self.filter_end_date = cast(date, self.end_date_edit.date().toPython())
        self.refresh()

    def _on_sort_changed(self, text: str) -> None:
        """排序方式改变时触发"""
        self.sort_by = text
        self.refresh()

    def _on_keyword_changed(self, text: str) -> None:
        """关键词搜索（防抖处理）"""
        self.filter_keyword = text.strip()
        # 使用定时器防抖，500ms后触发搜索
        if hasattr(self, "_search_timer"):
            self._search_timer.stop()
        else:
            self._search_timer = QTimer(self)
            self._search_timer.setSingleShot(True)
            self._search_timer.timeout.connect(self.refresh)
        self._search_timer.start(500)

    def _reset_filters(self) -> None:
        """重置所有筛选条件"""
        self.level_combo.setCurrentText("全部")
        self.rank_combo.setCurrentText("全部")
        self.start_date_edit.setDate(QDate(2020, 1, 1))
        self.end_date_edit.setDate(QDate.currentDate())
        self.keyword_input.clear()
        self.sort_combo.setCurrentText("日期降序")
        self.filter_level = "全部"
        self.filter_rank = "全部"
        self.filter_start_date = cast(date, self.start_date_edit.date().toPython())
        self.filter_end_date = cast(date, self.end_date_edit.date().toPython())
        self.filter_keyword = ""
        self.sort_by = "日期降序"
        for key, combo in self.flag_filter_widgets.items():
            combo.setCurrentText("全部")
            self.flag_filters[key] = "全部"
        self.refresh()

    def _load_flag_definitions(self) -> None:
        try:
            self.flag_defs = self.ctx.flags.list_flags(enabled_only=True)
            self.flag_defaults = {f.key: bool(f.default_value) for f in self.flag_defs}
        except Exception as exc:
            logger.warning("加载自定义开关失败: %s", exc)
            self.flag_defs = []
            self.flag_defaults = {}
        # 初始化过滤状态
        for flag in self.flag_defs:
            self.flag_filters.setdefault(flag.key, "全部")

    def _rebuild_flag_filters(self) -> None:
        # 清空容器
        while self.flag_filter_container.count():
            item = self.flag_filter_container.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.flag_filter_widgets.clear()

        if not self.flag_defs:
            return

        title = BodyLabel("自定义开关筛选（是/否）")
        title.setStyleSheet("color: #666;")
        self.flag_filter_container.addWidget(title)

        for flag in self.flag_defs:
            row = QHBoxLayout()
            row.setSpacing(10)
            label = BodyLabel(flag.label)
            label.setMinimumWidth(72)
            combo = ComboBox()
            combo.addItems(["全部", "是", "否"])
            combo.setCurrentText(self.flag_filters.get(flag.key, "全部"))
            combo.currentTextChanged.connect(lambda text, k=flag.key: self._on_flag_filter_changed(k, text))
            combo.setMinimumWidth(96)
            combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            row.addWidget(label)
            row.addWidget(combo)
            row.addStretch()
            self.flag_filter_widgets[flag.key] = combo
            self.flag_filter_container.addLayout(row)

    def _on_flag_filter_changed(self, key: str, value: str) -> None:
        self.flag_filters[key] = value
        self.refresh()

    def _auto_refresh(self) -> None:
        """检测数据变化并刷新"""
        if self.is_batch_mode:
            return
        try:
            from sqlalchemy import func, select

            from ...data.models import Award

            with self.ctx.db.session_scope() as session:
                count, max_updated = session.execute(
                    select(func.count(Award.id), func.max(Award.updated_at)).where(Award.deleted.is_(False))
                ).one()

            signature = (int(count or 0), max_updated.isoformat() if max_updated else "")
            if signature != self._cached_award_signature:
                self._cached_award_signature = signature
                self.refresh()
        except Exception as e:
            logger.debug(f"自动刷新失败: {e}")

    def refresh(self) -> None:
        """刷新荣誉列表"""
        try:
            # 刷新 flag 定义与过滤器
            prev_keys = {f.key for f in getattr(self, "flag_defs", [])}
            self._load_flag_definitions()
            new_keys = {f.key for f in self.flag_defs}
            if new_keys != prev_keys:
                self._rebuild_flag_filters()

            self._clear_awards_layout()
            self.awards_list = []
            self.total_awards = 0
            self._loaded_count = 0
            self._loading_more = False
            self._load_more_container = None
            self.load_more_btn = None

            level = None if self.filter_level == "全部" else self.filter_level
            rank = None if self.filter_rank == "全部" else self.filter_rank
            sort_by = self.sort_by
            keyword = self.filter_keyword
            date_from = self.filter_start_date
            date_to = self.filter_end_date
            flag_filters = dict(self.flag_filters)

            self._refresh_seq += 1
            seq = self._refresh_seq

            def build():
                return self.ctx.awards.list_awards_overview(
                    query=keyword,
                    level=level,
                    rank=rank,
                    date_from=date_from,
                    date_to=date_to,
                    sort_by=sort_by,
                    flag_filters=flag_filters,
                    offset=0,
                    limit=self.PAGE_SIZE,
                )

            def on_done(result: tuple[list, dict, int] | Exception) -> None:
                if seq != self._refresh_seq:
                    return
                if isinstance(result, Exception):
                    logger.error(f"刷新失败: {result}", exc_info=True)
                    InfoBar.error("错误", f"刷新失败: {result}", parent=self.window())
                    return

                awards, flag_values, total = result
                self.award_flag_values = flag_values or {}
                self.awards_list = list(awards)
                total = int(total or 0)
                if total >= self.MAX_OVERVIEW_ITEMS:
                    InfoBar.warning(
                        "结果过多",
                        f"为避免卡顿，已限制显示前 {self.MAX_OVERVIEW_ITEMS} 条结果，建议进一步筛选。",
                        parent=self.window(),
                    )
                self.total_awards = min(total, self.MAX_OVERVIEW_ITEMS)
                self._loaded_count = len(awards)
                self._prune_selection()

                if not awards:
                    self._show_empty_state()
                    self._update_batch_actions_state()
                    self._cached_award_signature = self._get_award_signature()
                    return

                self.current_page = 1
                self._append_awards(awards)

                if self._loaded_count < self.total_awards:
                    self._add_load_more_button()
                else:
                    self.awards_layout.addStretch()

                logger.debug(f"已加载 {self._loaded_count}/{self.total_awards} 个荣誉项目")
                self._update_batch_actions_state()
                self._cached_award_signature = self._get_award_signature()

            run_in_thread_guarded(build, on_done, guard=self)
        except Exception as e:
            logger.error(f"刷新失败: {e}", exc_info=True)

    def _get_award_signature(self) -> tuple[int, str]:
        from sqlalchemy import func, select

        from ...data.models import Award

        with self.ctx.db.session_scope() as session:
            count, max_updated = session.execute(
                select(func.count(Award.id), func.max(Award.updated_at)).where(Award.deleted.is_(False))
            ).one()
        return int(count or 0), max_updated.isoformat() if max_updated else ""

    def _clear_awards_layout(self) -> None:
        """清空布局"""
        self.card_checkboxes.clear()
        widgets_to_delete = []
        while self.awards_layout.count():
            item = self.awards_layout.takeAt(0)
            if item.widget():
                widget = item.widget()
                if widget:
                    widget.setVisible(False)
                    widgets_to_delete.append(widget)

        for widget in widgets_to_delete:
            widget.deleteLater()

    def _show_empty_state(self) -> None:
        """显示空状态"""
        self.awards_layout.addStretch()

        empty_container = QWidget()
        empty_layout = QVBoxLayout(empty_container)
        empty_layout.setContentsMargins(0, 0, 0, 0)
        empty_layout.setSpacing(12)
        empty_layout.addStretch()

        empty_icon = IconWidget()
        empty_icon.setIcon(FluentIcon.DOCUMENT)
        empty_icon.setFixedSize(40, 40)
        empty_layout.addWidget(empty_icon, alignment=Qt.AlignmentFlag.AlignCenter)

        empty_text = BodyLabel("暂无项目数据")
        empty_text.setProperty("emptyStateTitle", True)
        empty_layout.addWidget(empty_text, alignment=Qt.AlignmentFlag.AlignCenter)

        empty_hint = CaptionLabel("点击「录入」页添加新项目")
        empty_hint.setProperty("emptyStateHint", True)
        empty_layout.addWidget(empty_hint, alignment=Qt.AlignmentFlag.AlignCenter)

        empty_layout.addStretch()
        self.awards_layout.addWidget(empty_container)
        self.awards_layout.addStretch()

    def _append_awards(self, awards: list) -> None:
        """追加荣誉卡片到列表"""
        for award in awards:
            card = self._create_award_card(award)
            self._insert_award_card(card)

    def _insert_award_card(self, card: QWidget) -> None:
        if self._load_more_container is None:
            self.awards_layout.addWidget(card)
            return
        index = self.awards_layout.indexOf(self._load_more_container)
        if index < 0:
            self.awards_layout.addWidget(card)
            return
        self.awards_layout.insertWidget(index, card)

    def _add_load_more_button(self) -> None:
        """添加加载更多按钮"""
        if self._load_more_container is None:
            btn_container = QWidget()
            btn_layout = QHBoxLayout(btn_container)
            btn_layout.setContentsMargins(0, 16, 0, 16)

            self.load_more_btn = PrimaryPushButton("加载更多")
            self.load_more_btn.setFixedWidth(160)
            self.load_more_btn.clicked.connect(self._on_load_more_clicked)
            btn_layout.addStretch()
            btn_layout.addWidget(self.load_more_btn)
            btn_layout.addStretch()
            self._load_more_container = btn_container

        if self._load_more_container.parent() is None:
            self.awards_layout.addWidget(self._load_more_container)

    def _remove_load_more_button(self) -> None:
        if self._load_more_container is None:
            return
        self.awards_layout.removeWidget(self._load_more_container)
        self._load_more_container.deleteLater()
        self._load_more_container = None
        self.load_more_btn = None

    def _on_load_more_clicked(self) -> None:
        """加载更多数据"""
        if self._loading_more:
            return
        self._loading_more = True
        if self.load_more_btn is not None:
            self.load_more_btn.setEnabled(False)

        level = None if self.filter_level == "全部" else self.filter_level
        rank = None if self.filter_rank == "全部" else self.filter_rank
        sort_by = self.sort_by
        keyword = self.filter_keyword
        date_from = self.filter_start_date
        date_to = self.filter_end_date
        flag_filters = dict(self.flag_filters)
        offset = self._loaded_count
        seq = self._refresh_seq

        def build():
            return self.ctx.awards.list_awards_overview(
                query=keyword,
                level=level,
                rank=rank,
                date_from=date_from,
                date_to=date_to,
                sort_by=sort_by,
                flag_filters=flag_filters,
                offset=offset,
                limit=self.PAGE_SIZE,
            )

        def on_done(result):
            if seq != self._refresh_seq:
                return
            self._loading_more = False
            if self.load_more_btn is not None:
                self.load_more_btn.setEnabled(True)
            if isinstance(result, Exception):
                logger.exception("加载更多失败: %s", result)
                InfoBar.error("错误", f"加载失败: {result!s}", parent=self.window())
                return

            awards, flag_values, total = result
            total = int(total or 0)
            if total >= self.MAX_OVERVIEW_ITEMS:
                total = self.MAX_OVERVIEW_ITEMS
            self.total_awards = total
            if flag_values:
                self.award_flag_values.update(flag_values)
            if awards:
                self._append_awards(awards)
                self.awards_list.extend(awards)
                self._loaded_count += len(awards)
                self.current_page += 1
                logger.debug(f"当前已加载 {self._loaded_count}/{self.total_awards} 条")

            if self._loaded_count >= self.total_awards:
                self._remove_load_more_button()
                self.awards_layout.addStretch()
            else:
                self._add_load_more_button()

        run_in_thread_guarded(build, on_done, guard=self)

    def _create_award_card(self, award) -> QWidget:
        """创建单个荣誉卡片"""
        card = CardWidget()
        card.setProperty("card", True)
        card.setMinimumHeight(100)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(8)

        # 顶部：标题 + 级别标签
        top_layout = QHBoxLayout()

        # 批量选择复选框
        checkbox = CheckBox()
        checkbox.setFixedSize(24, 24)
        checkbox.setVisible(self.is_batch_mode)
        checkbox.setChecked(award.id in self.selected_award_ids)
        self.card_checkboxes[award.id] = checkbox
        # 使用闭包捕获 award.id
        checkbox.stateChanged.connect(lambda state, aid=award.id: self._on_card_checked(state, aid))
        top_layout.addWidget(checkbox)

        # 标题和级别
        title_level_layout = QVBoxLayout()

        # 荣誉名称
        title = TitleLabel(award.competition_name)
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        title_level_layout.addWidget(title)

        # 级别等级
        level_text = f"{award.level} • {award.rank}"
        if award.certificate_code:
            level_text += f" • {award.certificate_code}"
        level_label = CaptionLabel(level_text)
        title_level_layout.addWidget(level_label)

        top_layout.addLayout(title_level_layout, 1)

        # 日期和人数 - 右上角
        date_people_layout = QVBoxLayout()
        date_text = BodyLabel(award.award_date.strftime("%Y-%m-%d"))
        people_count = BodyLabel(f"{len(award.member_names)} 人")
        date_people_layout.addWidget(date_text)
        date_people_layout.addWidget(people_count)
        top_layout.addLayout(date_people_layout)

        card_layout.addLayout(top_layout)

        # 中部：成员列表
        if award.member_names:
            members_text = ", ".join(award.member_names)
            members_label = BodyLabel(members_text)
            members_label.setWordWrap(True)
            members_label.setStyleSheet("font-size: 12px;")
            card_layout.addWidget(members_label)

        # 底部：备注和按钮
        if award.remarks:
            remarks_label = CaptionLabel(f"备注: {award.remarks}")
            remarks_label.setWordWrap(True)
            remarks_label.setStyleSheet("font-size: 11px;")
            card_layout.addWidget(remarks_label)

        # 自定义开关展示
        if self.flag_defs:
            flags_row = QHBoxLayout()
            flags_row.setSpacing(8)
            values = self.award_flag_values.get(award.id, {})
            for flag in self.flag_defs:
                val = values.get(flag.key, self.flag_defaults.get(flag.key, False))
                pill = QLabel(f"{flag.label}: {'是' if val else '否'}")
                pill.setStyleSheet(
                    "padding:4px 8px; border-radius:8px; font-size:11px;"
                    f"background-color: {'#e6f4ff' if val else '#f0f0f0'};"
                    f"color: {'#1890ff' if val else '#666'};"
                )
                flags_row.addWidget(pill)
            flags_row.addStretch()
            card_layout.addLayout(flags_row)

        # 操作按钮
        action_layout = QHBoxLayout()
        action_layout.addStretch()

        export_pdf_btn = PushButton("导出PDF")
        export_pdf_btn.setFixedWidth(80)
        export_pdf_btn.setFixedHeight(28)
        export_pdf_btn.clicked.connect(lambda: self._export_award_pdf(award))

        export_qr_btn = PushButton("二维码")
        export_qr_btn.setFixedWidth(60)
        export_qr_btn.setFixedHeight(28)
        export_qr_btn.clicked.connect(lambda: self._export_award_qr(award))

        edit_btn = PrimaryPushButton("编辑")
        edit_btn.setFixedWidth(60)
        edit_btn.setFixedHeight(28)
        edit_btn.clicked.connect(lambda: self._edit_award(award))

        delete_btn = PushButton("删除")
        delete_btn.setFixedWidth(60)
        delete_btn.setFixedHeight(28)
        delete_btn.clicked.connect(lambda: self._delete_award(award))

        # 批量模式下隐藏单个操作按钮
        if self.is_batch_mode:
            export_pdf_btn.hide()
            export_qr_btn.hide()
            edit_btn.hide()
            delete_btn.hide()

        action_layout.addWidget(export_pdf_btn)
        action_layout.addSpacing(6)
        action_layout.addWidget(export_qr_btn)
        action_layout.addSpacing(6)
        action_layout.addWidget(edit_btn)
        action_layout.addSpacing(6)
        action_layout.addWidget(delete_btn)

        card_layout.addLayout(action_layout)

        return card

    def _toggle_batch_mode(self, checked: bool):
        """切换批量管理模式"""
        self.is_batch_mode = checked
        self.batch_delete_btn.setVisible(checked)
        self.select_all_btn.setVisible(checked)
        self.invert_selection_btn.setVisible(checked)
        self.clear_selection_btn.setVisible(checked)

        # 如果退出批量模式，清空选择
        if not checked:
            self.selected_award_ids.clear()

        for checkbox in self.card_checkboxes.values():
            checkbox.setVisible(checked)

        # 更新所有卡片的显示状态
        for i in range(self.awards_layout.count()):
            item = self.awards_layout.itemAt(i)
            widget = item.widget()
            if widget and widget.property("card"):
                # 查找操作按钮并反向显示
                buttons = widget.findChildren(PushButton)  # 编辑和删除按钮
                for btn in buttons:
                    if btn.text() in ["编辑", "删除"]:
                        btn.setVisible(not checked)
        self._sync_checkboxes_with_selection()
        self._update_batch_actions_state()

    def _on_card_checked(self, state, award_id):
        """处理卡片选中状态"""
        if state == 2:  # Checked
            self.selected_award_ids.add(award_id)
        else:
            self.selected_award_ids.discard(award_id)

        self._update_batch_actions_state()

    def _select_all_awards(self) -> None:
        """选中当前筛选条件下的全部荣誉"""
        if not self.awards_list:
            return
        self.selected_award_ids = {award.id for award in self.awards_list}
        self._sync_checkboxes_with_selection()
        self._update_batch_actions_state()

    def _clear_selection(self) -> None:
        """取消所有选中"""
        if not self.selected_award_ids:
            return
        self.selected_award_ids.clear()
        self._sync_checkboxes_with_selection()
        self._update_batch_actions_state()

    def _invert_selection(self) -> None:
        """反选当前筛选结果"""
        if not self.awards_list:
            return
        all_ids = {award.id for award in self.awards_list}
        self.selected_award_ids = all_ids - self.selected_award_ids
        self._sync_checkboxes_with_selection()
        self._update_batch_actions_state()

    def _prune_selection(self) -> None:
        """移除已不在当前列表中的选中项"""
        if not self.selected_award_ids:
            return
        valid_ids = {award.id for award in self.awards_list}
        self.selected_award_ids.intersection_update(valid_ids)

    def _sync_checkboxes_with_selection(self) -> None:
        """同步所有复选框为当前的选中状态"""
        for award_id, checkbox in self.card_checkboxes.items():
            checkbox.blockSignals(True)
            checkbox.setChecked(award_id in self.selected_award_ids)
            checkbox.blockSignals(False)

    def _update_batch_actions_state(self) -> None:
        """更新批量操作按钮状态"""
        has_awards = bool(self.awards_list)
        allow_batch_ops = self.is_batch_mode and has_awards
        self.select_all_btn.setEnabled(allow_batch_ops)
        self.invert_selection_btn.setEnabled(allow_batch_ops)
        self.clear_selection_btn.setEnabled(self.is_batch_mode and bool(self.selected_award_ids))
        self.batch_delete_btn.setEnabled(bool(self.selected_award_ids))

    def _batch_delete_awards(self):
        """批量删除选中的荣誉"""
        if not self.selected_award_ids:
            return

        count = len(self.selected_award_ids)
        title = "确认批量删除"
        content = f"确定要删除选中的 {count} 个荣誉项目吗？\n这些项目将被移至回收站。"

        w = MessageBox(title, content, self.window())
        if w.exec():
            try:
                deleted_count = self.ctx.awards.batch_delete_awards(list(self.selected_award_ids))
                InfoBar.success("成功", f"已删除 {deleted_count} 个项目", parent=self.window())

                # 退出批量模式并刷新
                self.batch_mode_btn.setChecked(False)
                self.refresh()
            except Exception as e:
                logger.exception("批量删除失败")
                InfoBar.error("错误", f"批量删除失败: {e}", parent=self.window())

    def _edit_award(self, award) -> None:
        """编辑荣誉"""
        try:
            main_window = self.window()
            if main_window is None or not hasattr(main_window, "navigate_to") or not hasattr(main_window, "entry_page"):
                raise RuntimeError("MainWindow 未找到，无法跳转到录入页编辑")

            try:
                entry_lazy = cast(Any, cast(Any, main_window).entry_page)
                entry_page = cast(Any, entry_lazy).load()
                if not hasattr(entry_page, "load_award_for_editing"):
                    raise RuntimeError("EntryPage 不支持 load_award_for_editing()")
                cast(Any, entry_page).load_award_for_editing(award)
            except Exception as exc:
                logger.exception("打开录入页编辑失败: %s", exc)
                InfoBar.error("错误", f"打开录入页编辑失败: {exc!s}", parent=self.window())
                return

            # 强制切换到录入页（避免仅选中导航项但不触发页面切换）
            with suppress(Exception):
                cast(Any, main_window).switchTo(cast(Any, main_window).entry_page)
            cast(Any, main_window).navigate_to("entry")
        except Exception as e:
            logger.exception(f"编辑失败: {e}")
            InfoBar.error("错误", f"编辑失败: {e!s}", parent=self.window())

    def _delete_award(self, award) -> None:
        """删除荣誉(移入回收站)"""
        box = MessageBox(
            "确认删除",
            f"确定要删除 '{award.competition_name}' 吗？\n删除后可以在回收站中恢复。",
            self.window(),
        )

        if box.exec():
            try:
                self.ctx.awards.delete_award(award.id)
                self.refresh()
                InfoBar.success("成功", "已移入回收站", parent=self.window())
            except Exception as e:
                logger.exception(f"删除失败: {e}")
                InfoBar.error("错误", f"删除失败: {e!s}", parent=self.window())

    def _safe_filename(self, name: str, suffix: str) -> str:
        invalid = '<>:"/\\|?*'
        cleaned = "".join("_" if c in invalid else c for c in (name or "").strip())
        cleaned = cleaned.strip().rstrip(".")
        if not cleaned:
            cleaned = "award"
        return f"{cleaned}{suffix}"

    def _export_award_pdf(self, award) -> None:
        default_name = self._safe_filename(award.competition_name, ".pdf")
        path, _ = QFileDialog.getSaveFileName(self, "导出 PDF", default_name, "PDF (*.pdf)")
        if not path:
            return

        def task():
            return self.ctx.importer.export_award_pdf(award.id, Path(path))

        def on_done(result) -> None:
            if isinstance(result, Exception):
                InfoBar.error("导出失败", str(result), parent=self.window())
                return
            InfoBar.success("导出成功", str(result), parent=self.window())

        run_in_thread_guarded(task, on_done, guard=self)

    def _export_award_qr(self, award) -> None:
        default_name = self._safe_filename(f"{award.competition_name}_二维码", ".png")
        path, _ = QFileDialog.getSaveFileName(self, "导出二维码", default_name, "PNG (*.png)")
        if not path:
            return

        def task():
            return self.ctx.importer.export_award_qr(award.id, Path(path))

        def on_done(result) -> None:
            if isinstance(result, Exception):
                InfoBar.error("导出失败", str(result), parent=self.window())
                return
            InfoBar.success("导出成功", str(result), parent=self.window())

        run_in_thread_guarded(task, on_done, guard=self)

    def closeEvent(self, event):
        """页面关闭时停止定时器"""
        if self.refresh_timer:
            self.refresh_timer.stop()
        super().closeEvent(event)

    def showEvent(self, event):
        """页面显示时启动定时器"""
        super().showEvent(event)
        if self.refresh_timer:
            self.refresh_timer.start()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        if self.refresh_timer:
            self.refresh_timer.stop()

    def _apply_theme(self) -> None:
        """应用主题到滚动区域"""
        scroll_stylesheet = """
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollArea > QWidget {
                background: transparent;
            }
            QWidget#scrollContent {
                background: transparent;
            }
        """
        self.scrollArea.setStyleSheet(scroll_stylesheet)
        scroll_widget = self.scrollArea.widget()
        if scroll_widget:
            scroll_widget.setObjectName("scrollContent")
            scroll_widget.setAutoFillBackground(False)

    @Slot()
    def _on_theme_changed(self) -> None:
        """主题切换时重新应用样式"""
        # 更新滚动区域背景
        self._apply_theme()


class AwardDetailDialog(MaskDialogBase):
    """荣誉详情编辑对话框 - 和录入页相同的结构"""

    def __init__(self, parent, award, theme_manager: ThemeManager, ctx):
        super().__init__(parent)
        self.award = award
        self.theme_manager = theme_manager
        self.ctx = ctx
        self.members_data = []  # 存储成员卡片数据
        self.selected_files: list[Path] = []  # 存储选中的附件文件
        self._selected_file_keys: set[str] = set()
        self._attachments_loaded = False
        self.flag_checkboxes: dict[str, CheckBox] = {}
        self.flag_defs: list = []

        self.setWindowTitle(f"荣誉详情 - {award.competition_name}")
        self.setMinimumWidth(700)
        self.setMinimumHeight(600)
        self.widget.setGraphicsEffect(cast(QGraphicsEffect, None))
        self.widget.setObjectName("centerWidget")

        self._init_ui()
        self._apply_theme()
        self.theme_manager.themeChanged.connect(self._on_dialog_theme_changed)

    def showEvent(self, e) -> None:
        parent = self.parentWidget()
        if parent is not None:
            top_left = parent.mapToGlobal(QPoint(0, 0))
            self.setGeometry(QRect(top_left, parent.size()))
        super().showEvent(e)

    def _init_ui(self):
        from ..theme import create_card, make_section_title

        layout = QVBoxLayout(self.widget)  # 添加到 self.widget 而不是 self
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 滚动区域
        scroll = ScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # 内容容器
        content = QWidget()
        content.setObjectName("pageRoot")
        scroll.setWidget(content)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        # === 基本信息卡片 ===
        info_card, info_layout = create_card()

        # Row 1: 比赛名称 + 获奖日期
        row1 = QHBoxLayout()
        row1.setSpacing(16)
        name_col = QVBoxLayout()
        name_label = QLabel("比赛名称")
        name_label.setObjectName("formLabel")
        self.name_input = LineEdit()
        self.name_input.setText(self.award.competition_name)
        name_col.addWidget(name_label)
        name_col.addWidget(self.name_input)

        date_col = QVBoxLayout()
        date_label = QLabel("获奖日期")
        date_label.setObjectName("formLabel")
        date_row = QHBoxLayout()
        date_row.setSpacing(8)

        self.year_input = SpinBox()
        self.year_input.setRange(1900, 2100)
        self.year_input.setValue(self.award.award_date.year)
        self.year_input.setMinimumWidth(100)

        self.month_input = SpinBox()
        self.month_input.setRange(1, 12)
        self.month_input.setValue(self.award.award_date.month)
        self.month_input.setMinimumWidth(80)

        self.day_input = SpinBox()
        self.day_input.setRange(1, 31)
        self.day_input.setValue(self.award.award_date.day)
        self.day_input.setMinimumWidth(80)

        year_label = QLabel("年")
        year_label.setObjectName("formLabel")
        year_label.setMaximumWidth(20)
        month_label = QLabel("月")
        month_label.setObjectName("formLabel")
        month_label.setMaximumWidth(20)
        day_label = QLabel("日")
        day_label.setObjectName("formLabel")
        day_label.setMaximumWidth(20)

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
        level_label = QLabel("竞赛级别")
        level_label.setObjectName("formLabel")
        self.level_input = ComboBox()
        self.level_input.addItems(["国家级", "省级", "校级"])
        self.level_input.setCurrentText(self.award.level)
        level_col.addWidget(level_label)
        level_col.addWidget(self.level_input)

        rank_col = QVBoxLayout()
        rank_label = QLabel("获奖等级")
        rank_label.setObjectName("formLabel")
        self.rank_input = ComboBox()
        self.rank_input.addItems(["一等奖", "二等奖", "三等奖", "优秀奖"])
        self.rank_input.setCurrentText(self.award.rank)
        rank_col.addWidget(rank_label)
        rank_col.addWidget(self.rank_input)

        row2.addLayout(level_col, 1)
        row2.addLayout(rank_col, 1)
        info_layout.addLayout(row2)

        # Row 3: 证书编号
        cert_col = QVBoxLayout()
        cert_label = QLabel("证书编号")
        cert_label.setObjectName("formLabel")
        self.cert_input = LineEdit()
        clean_input_text(self.cert_input)
        self.cert_input.setText(self.award.certificate_code or "")
        cert_col.addWidget(cert_label)
        cert_col.addWidget(self.cert_input)
        info_layout.addLayout(cert_col)

        # Row 4: 备注
        remark_col = QVBoxLayout()
        remark_label = QLabel("备注")
        remark_label.setObjectName("formLabel")
        self.remarks_input = LineEdit()
        self.remarks_input.setText(self.award.remarks or "")
        remark_col.addWidget(remark_label)
        remark_col.addWidget(self.remarks_input)
        info_layout.addLayout(remark_col)

        # 自定义开关
        self.flags_container = QVBoxLayout()
        self.flags_container.setSpacing(8)
        info_layout.addLayout(self.flags_container)
        self._refresh_flag_section()
        if self.flag_defs:
            try:
                flag_values = self.ctx.flags.get_award_flags(self.award.id)
            except Exception:
                flag_values = {}
            for key, cb in self.flag_checkboxes.items():
                cb.setChecked(bool(flag_values.get(key, cb.isChecked())))

        content_layout.addWidget(info_card)

        # === 成员卡片 ===
        members_card, members_layout = create_card()
        members_layout.addWidget(make_section_title("参与成员"))

        self.members_container = QWidget()
        self.members_container.setStyleSheet("QWidget { background-color: transparent; }")
        self.members_list_layout = QVBoxLayout(self.members_container)
        self.members_list_layout.setContentsMargins(0, 0, 0, 0)
        self.members_list_layout.setSpacing(12)
        self.members_list_layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinAndMaxSize)

        members_layout.addWidget(self.members_container)

        # 加载已有成员
        for assoc in self.award.award_members:
            self._add_member_card(assoc)

        # 添加成员按钮
        add_member_btn = PrimaryPushButton("添加成员")
        add_member_btn.clicked.connect(self._add_member_row)
        members_layout.addWidget(add_member_btn)

        content_layout.addWidget(members_card)

        # === 附件表格卡片 ===
        attachment_card, attachment_layout = create_card()

        # 标题和添加按钮
        attach_header = QHBoxLayout()
        attach_header.setSpacing(12)
        attach_header.setAlignment(Qt.AlignmentFlag.AlignVCenter)
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
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.attach_table.verticalHeader().setVisible(False)
        self.attach_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.attach_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        from ..theme import apply_table_style

        apply_table_style(self.attach_table)
        self.attach_table.fileDropped.connect(self._on_files_dropped)
        self.attach_table.doubleClicked.connect(self._on_attachment_double_clicked)
        attachment_layout.addWidget(self.attach_table)
        content_layout.addWidget(attachment_card)
        self._resize_attachment_table(0)

        content_layout.addStretch()

        layout.addWidget(scroll)

        # === 按钮 ===
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        save_btn = PrimaryPushButton("更新荣誉")
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        cancel_btn = PushButton("取消编辑")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

        # 加载现有附件
        self._load_existing_attachments()

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

    def _get_flag_values(self) -> dict[str, bool]:
        return {key: cb.isChecked() for key, cb in self.flag_checkboxes.items()}

    def _load_existing_attachments(self) -> None:
        """加载现有荣誉的附件到表格"""
        try:
            # 从数据库重新查询 award，预加载附件关系
            from sqlalchemy.orm import joinedload

            from ...data.models import Award

            self.selected_files = []
            self._selected_file_keys.clear()
            with self.ctx.db.session_scope() as session:
                # 使用 joinedload 预加载附件
                award = (
                    session.query(Award)
                    .options(joinedload(Award.attachments))
                    .filter(Award.id == self.award.id)
                    .first()
                )

                if award and award.attachments:
                    # 获取附件根目录
                    root = Path(self.ctx.settings.get("attachment_root", "attachments"))

                    # 将附件路径添加到 selected_files
                    for attachment in award.attachments:
                        if getattr(attachment, "deleted", False):
                            continue
                        file_path = (root / attachment.relative_path).resolve()
                        if not file_path.exists():
                            logger.warning(f"附件文件不存在: {file_path}")
                            continue
                        key = self._to_file_key(file_path)
                        if key in self._selected_file_keys:
                            continue
                        self.selected_files.append(file_path)
                        self._selected_file_keys.add(key)

                    # 更新表格显示
                    self._update_attachment_table()

                    logger.info(f"已加载 {len(self.selected_files)} 个附件")
                self._attachments_loaded = True
        except Exception as e:
            logger.error(f"加载附件失败: {e}", exc_info=True)
            self._attachments_loaded = False

    def _add_member_card(self, assoc=None):
        """添加成员卡片"""
        # 使用 CardWidget 并设置 card 属性以使用 QSS 定义的样式
        member_card = CardWidget()
        member_card.setProperty("card", True)

        # 获取当前样式用于标签
        is_dark = self.theme_manager.is_dark
        label_style = "color: #a6aabb; font-size: 12px;" if is_dark else "color: #666; font-size: 12px;"

        member_layout = QVBoxLayout(member_card)
        member_layout.setContentsMargins(16, 16, 16, 16)
        member_layout.setSpacing(12)

        # 头部：成员编号和删除按钮
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        member_index = len(self.members_data) + 1
        member_label = QLabel(f"成员 #{member_index}")
        member_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        header_layout.addWidget(member_label)
        join_checkbox = CheckBox("加入成员库")
        linked_member = getattr(assoc, "member", None) if assoc is not None else None
        join_checkbox.setChecked(bool(linked_member) and getattr(assoc, "member_id", None) is not None)
        header_layout.addWidget(join_checkbox)
        header_layout.addStretch()

        # 上/下移动按钮
        up_btn = TransparentToolButton(FluentIcon.UP)
        up_btn.setToolTip("上移")
        up_btn.setFixedSize(28, 28)
        header_layout.addWidget(up_btn)

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
        history_btn.setMinimumWidth(95)
        history_btn.setFixedHeight(28)
        header_layout.addWidget(history_btn)

        # 删除按钮
        delete_btn = PushButton("删除")
        delete_btn.setFixedWidth(60)
        delete_btn.setFixedHeight(28)
        header_layout.addWidget(delete_btn)

        # 表单布局
        form_grid = QGridLayout()
        form_grid.setSpacing(12)
        form_grid.setColumnStretch(1, 1)
        form_grid.setColumnStretch(3, 1)

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

        member_fields = {}
        label_widgets: dict[str, QLabel] = {}
        for field_name, label in zip(field_names, field_labels, strict=False):
            # 专业字段使用特殊的搜索组件
            if field_name == "major":
                input_widget = MajorSearchWidget(self.ctx.majors, self.theme_manager, parent=member_card)
                if linked_member:
                    value = getattr(linked_member, field_name, "")
                    if value:
                        input_widget.set_text(str(value))
            elif field_name == "school":
                input_widget = SchoolSearchWidget(self.ctx.schools, self.theme_manager, parent=member_card)
                if linked_member:
                    input_widget.set_school(linked_member.school or "", linked_member.school_code)
            else:
                input_widget = LineEdit()
                clean_input_text(input_widget)  # 自动删除空白字符
                input_widget.setPlaceholderText(f"请输入{label}")

                # 如果是编辑现有成员，填充数据
                if field_name == "name" and assoc is not None:
                    input_widget.setText(getattr(assoc, "member_name", "") or "")
                elif linked_member:
                    value = getattr(linked_member, field_name, "")
                    if value:
                        input_widget.setText(str(value))

            member_fields[field_name] = input_widget

        # 按2列布局
        for idx, (field_name, label) in enumerate(zip(field_names, field_labels, strict=False)):
            col = (idx % 2) * 2
            row = idx // 2

            label_widget = QLabel(label)
            label_widget.setStyleSheet(label_style)
            label_widget.setMinimumWidth(50)
            label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)

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

        # 组装
        member_layout.addLayout(header_layout)
        member_layout.addLayout(form_grid)
        self._connect_member_field_signals(member_fields)
        self._apply_member_initial_filters(member_fields)

        # 连接按钮信号
        import_btn.clicked.connect(lambda: self._import_from_doc(member_fields))
        history_btn.clicked.connect(lambda: self._select_from_history(member_fields, join_checkbox))
        delete_btn.clicked.connect(lambda: self._remove_member_card(member_card, member_fields))
        up_btn.clicked.connect(lambda: self._move_member_up(member_card))
        down_btn.clicked.connect(lambda: self._move_member_down(member_card))

        member_data = {
            "card": member_card,
            "fields": member_fields,
            "label": member_label,
            "join_checkbox": join_checkbox,
        }
        self.members_data.append(member_data)
        self.members_list_layout.addWidget(member_card)
        self._update_member_indices()

    def _add_member_row(self):
        """添加空白成员卡片"""
        self._add_member_card()

    def _apply_member_card_style(self, card: CardWidget) -> None:
        """刷新成员卡片的样式以匹配当前主题"""
        card.setProperty("memberCard", True)
        card.style().unpolish(card)
        card.style().polish(card)

    @Slot()
    def _on_dialog_theme_changed(self) -> None:
        """Dialog主题切换时重新应用样式"""
        # 1. 更新对话框背景
        self._apply_theme()

        # 2. 重新应用所有成员卡片的样式
        for member_data in self.members_data:
            card = member_data["card"]
            self._apply_member_card_style(card)

    def _remove_member_card(self, member_card, member_fields):
        """删除成员卡片"""
        for idx, data in enumerate(self.members_data):
            if data["card"] == member_card:
                self.members_data.pop(idx)
                break
        member_card.deleteLater()
        self._update_member_indices()

    def _connect_member_field_signals(self, member_fields: dict) -> None:
        school_widget = member_fields.get("school")
        school_code_widget = member_fields.get("school_code")
        major_widget = member_fields.get("major")

        if isinstance(school_widget, SchoolSearchWidget):
            school_widget.schoolSelected.connect(partial(self._on_school_selected, member_fields))

        if isinstance(school_code_widget, LineEdit):
            school_code_widget.textChanged.connect(partial(self._on_school_code_changed, member_fields))

        if isinstance(major_widget, MajorSearchWidget):
            major_widget.majorSelected.connect(partial(self._on_major_selected, member_fields))

    def _apply_member_initial_filters(self, member_fields: dict) -> None:
        school_widget = member_fields.get("school")
        school_code_widget = member_fields.get("school_code")
        major_widget = member_fields.get("major")

        if not isinstance(major_widget, MajorSearchWidget):
            return

        school_name = school_widget.text() if isinstance(school_widget, SchoolSearchWidget) else None
        school_code: str | None = None
        if isinstance(school_code_widget, LineEdit):
            school_code = school_code_widget.text().strip() or None
        if school_code is None and isinstance(school_widget, SchoolSearchWidget):
            school_code = school_widget.selected_code()

        major_widget.set_school_filter(name=school_name, code=school_code)

    def _on_school_selected(self, member_fields: dict, name: str, code: str | None) -> None:
        school_code_widget = member_fields.get("school_code")
        major_widget = member_fields.get("major")
        major_code_widget = member_fields.get("major_code")
        college_widget = member_fields.get("college")

        if isinstance(school_code_widget, LineEdit):
            school_code_widget.blockSignals(True)
            school_code_widget.setText(code or "")
            school_code_widget.blockSignals(False)

        if isinstance(major_widget, MajorSearchWidget):
            major_widget.set_school_filter(name=name, code=code or None)
            major_widget.clear()

        if isinstance(major_code_widget, LineEdit):
            major_code_widget.clear()
        if isinstance(college_widget, LineEdit):
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
        if isinstance(major_code_widget, LineEdit):
            major_code_widget.setText(code or "")
        if isinstance(college_widget, LineEdit) and college:
            college_widget.setText(college)

    def _move_member_up(self, member_card: QWidget) -> None:
        """将成员卡片上移一位"""
        idx = next((i for i, data in enumerate(self.members_data) if data["card"] == member_card), -1)
        if idx <= 0:
            return
        self.members_data[idx - 1], self.members_data[idx] = self.members_data[idx], self.members_data[idx - 1]
        self.members_list_layout.removeWidget(member_card)
        self.members_list_layout.insertWidget(idx - 1, member_card)
        self._update_member_indices()

    def _move_member_down(self, member_card: QWidget) -> None:
        """将成员卡片下移一位"""
        idx = next((i for i, data in enumerate(self.members_data) if data["card"] == member_card), -1)
        if idx == -1 or idx >= len(self.members_data) - 1:
            return
        self.members_data[idx + 1], self.members_data[idx] = self.members_data[idx], self.members_data[idx + 1]
        self.members_list_layout.removeWidget(member_card)
        self.members_list_layout.insertWidget(idx + 1, member_card)
        self._update_member_indices()

    def _update_member_indices(self) -> None:
        """同步成员索引标签"""
        for index, data in enumerate(self.members_data, start=1):
            label = data.get("label")
            if label:
                label.setText(f"成员 #{index}")

    def _import_from_doc(self, member_fields: dict) -> None:
        """从 .doc 文档导入成员信息"""
        # 打开文件选择对话框
        file_path, _ = QFileDialog.getOpenFileName(self, "选择成员信息文档", "", "Word 文档 (*.doc);;所有文件 (*.*)")

        if not file_path:
            return

        # 创建美化的进度对话框（适配主题）
        progress = FluentProgressDialog(parent=self.window())
        progress.setWindowTitle("导入成员信息")

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
            f"<p style='font-size: 14px; margin-bottom: 8px; color: {text_color};'><b>正在处理文档...</b></p>"
            f"<p style='font-size: 12px; color: {desc_color};'>正在打开 Word 文档并提取成员信息</p>"
            f"<p style='font-size: 12px; color: {hint_color};'>这可能需要几秒钟，请耐心等待</p>"
            "</div>"
        )
        progress.setRange(0, 0)  # 不确定进度，显示滚动条
        progress.setMinimumWidth(400)
        progress.setMinimumHeight(150)
        progress.setCancelButton(None)  # 不可取消
        progress.setWindowModality(Qt.WindowModality.WindowModal)

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

    def _select_from_history(self, member_fields: dict, join_checkbox: CheckBox) -> None:
        """从历史成员中选择"""
        # 获取所有历史成员
        from ...services.member_service import MemberService
        from .entry_page import HistoryMemberDialog

        service = MemberService(self.ctx.db)
        members = service.list_members()

        if not members:
            InfoBar.warning("提示", "暂无历史成员记录", parent=self.window())
            return

        # 创建历史成员选择对话框
        dialog = HistoryMemberDialog(members, self.theme_manager, self.window())
        if dialog.exec():
            selected_member = dialog.selected_member
            if selected_member:
                join_checkbox.setChecked(True)
                # 填充所有字段
                member_fields["name"].setText(selected_member.name or "")
                member_fields["gender"].setText(selected_member.gender or "")
                member_fields["id_card"].setText(selected_member.id_card or "")
                member_fields["phone"].setText(selected_member.phone or "")
                member_fields["student_id"].setText(selected_member.student_id or "")
                member_fields["email"].setText(selected_member.email or "")
                school_widget = member_fields.get("school")
                if isinstance(school_widget, SchoolSearchWidget):
                    school_widget.set_school(selected_member.school or "", selected_member.school_code)
                else:
                    widget = member_fields.get("school")
                    if isinstance(widget, LineEdit):
                        widget.setText(selected_member.school or "")

                school_code_widget = member_fields.get("school_code")
                if isinstance(school_code_widget, LineEdit):
                    school_code_widget.setText(selected_member.school_code or "")

                # 专业字段特殊处理
                major_widget = member_fields["major"]
                if isinstance(major_widget, MajorSearchWidget):
                    major_widget.set_text(selected_member.major or "")
                else:
                    major_widget.setText(selected_member.major or "")

                major_code_widget = member_fields.get("major_code")
                if isinstance(major_code_widget, LineEdit):
                    major_code_widget.setText(selected_member.major_code or "")

                member_fields["class_name"].setText(selected_member.class_name or "")
                member_fields["college"].setText(selected_member.college or "")
                InfoBar.success("成功", f"已选择成员: {selected_member.name}", parent=self.window())

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

            md5_value = self._calculate_md5(resolved)
            try:
                size_value = resolved.stat().st_size
            except OSError:
                size_value = None
            current_award_id = getattr(getattr(self, "award", None), "id", None)
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

    def _to_file_key(self, path: Path) -> str:
        return str(path.resolve()).lower()

    def _resize_attachment_table(self, row_count: int) -> None:
        header = self.attach_table.horizontalHeader()
        header_height = header.height() or 40
        row_height = self.attach_table.verticalHeader().defaultSectionSize() or 48
        visible_rows = min(max(row_count, 3), 8)
        target_height = header_height + row_height * visible_rows + 12
        self.attach_table.setMinimumHeight(target_height)
        self.attach_table.setMaximumHeight(target_height)

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
        for row_idx, _ in enumerate(rows):
            preview_btn = PushButton("预览")
            preview_btn.setFixedHeight(26)
            preview_btn.setFixedWidth(56)
            preview_btn.clicked.connect(lambda checked=False, r=row_idx: self._preview_attachment_row(r))
            delete_btn = TransparentToolButton(FluentIcon.DELETE)
            delete_btn.setToolTip("删除此附件")
            delete_btn.clicked.connect(lambda checked, r=row_idx: self._remove_attachment(r))
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(4, 0, 4, 0)
            btn_layout.addWidget(preview_btn)
            btn_layout.addWidget(delete_btn)
            btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            index = self.attach_model.index(row_idx, 4)
            self.attach_table.setIndexWidget(index, btn_widget)
        self._resize_attachment_table(len(rows))

    def _calculate_md5(self, file_path: Path) -> str:
        """计算文件MD5值"""
        try:
            return self.ctx.attachments.calculate_md5(file_path)
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

    def _on_attachment_double_clicked(self, index) -> None:
        if not index.isValid():
            return
        self._preview_attachment_row(index.row())

    def _preview_attachment_row(self, row: int) -> None:
        try:
            data = self.attach_model.object_at(row)
        except Exception:
            return
        if not isinstance(data, dict):
            return
        path = data.get("path")
        if isinstance(path, Path):
            file_path = path
        elif path:
            file_path = Path(str(path))
        else:
            return
        if not file_path.exists():
            InfoBar.warning("附件预览", "文件不存在，无法预览", parent=self.window())
            return
        dialog = AttachmentPreviewDialog(self.window(), path=file_path)
        dialog.show()

    def _save(self):
        """保存编辑"""
        try:
            issues = self._validate_form()
            if issues:
                InfoBar.warning("表单不合法", issues[0], parent=self.window())
                return

            # 获取成员数据
            members = self._get_members_data()

            self.ctx.awards.update_award(
                self.award.id,
                competition_name=self.name_input.text().strip(),
                award_date=cast(
                    date,
                    QDate(
                        self.year_input.value(),
                        self.month_input.value(),
                        self.day_input.value(),
                    ).toPython(),
                ),
                level=self.level_input.currentText(),
                rank=self.rank_input.currentText(),
                certificate_code=self.cert_input.text().strip() or None,
                remarks=self.remarks_input.text().strip() or None,
                member_names=members,
                attachment_files=self.selected_files if self._attachments_loaded else None,
                flag_values=self._get_flag_values(),
            )

            InfoBar.success("成功", f"已更新：{self.name_input.text().strip()}", parent=self.window())

            self.accept()
        except Exception as e:
            logger.exception(f"保存奖项失败: {e}")
            InfoBar.error("错误", f"保存失败: {e!s}", parent=self.window())

    def _validate_form(self) -> list[str]:
        issues: list[str] = []

        name = self.name_input.text().strip()
        valid, msg = FormValidator.validate_competition_name(name)
        if not valid:
            issues.append(msg)
            self._highlight_field_error(self.name_input)
            return issues

        try:
            award_date = QDate(
                self.year_input.value(),
                self.month_input.value(),
                self.day_input.value(),
            )
            if not award_date.isValid():
                issues.append("获奖日期不合法。")
                return issues
            if award_date > QDate.currentDate():
                issues.append("获奖日期不能晚于今天。")
                return issues
        except Exception:
            issues.append("获奖日期不合法。")
            return issues

        code = self.cert_input.text().strip()
        valid, msg = FormValidator.validate_certificate_code(code)
        if not valid:
            issues.append(msg)
            self._highlight_field_error(self.cert_input)
            return issues

        remarks = self.remarks_input.text().strip()
        valid, msg = FormValidator.validate_remarks(remarks)
        if not valid:
            issues.append(msg)
            self._highlight_field_error(self.remarks_input)
            return issues

        members_data = self._get_members_data()
        if not members_data:
            issues.append("请至少添加一名成员。")
            return issues

        for i, member in enumerate(members_data, 1):
            member_errors = FormValidator.validate_member_info(member)
            if member_errors:
                issues.append(f"成员 {i} - {member_errors[0]}")
                self._highlight_member_error(i - 1)
                return issues

        return issues

    def _highlight_field_error(self, field_widget: LineEdit) -> None:
        field_widget.setStyleSheet("""
            LineEdit {
                border: 2px solid #d13438;
                border-radius: 8px;
                padding: 4px;
                background-color: rgba(209, 52, 56, 0.08);
            }
        """)
        QTimer.singleShot(3000, lambda: field_widget.setStyleSheet(""))

    def _highlight_member_error(self, member_index: int) -> None:
        if 0 <= member_index < len(self.members_data):
            member_card = self.members_data[member_index]["card"]
            member_card.setStyleSheet("""
                CardWidget {
                    border: 2px solid #d13438;
                    border-radius: 8px;
                }
            """)
            QTimer.singleShot(3000, lambda: member_card.setStyleSheet(""))

    def _get_members_data(self):
        """获取成员数据"""
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
            name_widget = member_fields.get("name")
            if isinstance(name_widget, LineEdit):
                name = name_widget.text().strip()
                if name:
                    member_info = {"name": name, "join_member_library": join_member_library}
                    if join_member_library:
                        for field_name in field_names[1:]:
                            widget = member_fields.get(field_name)
                            if isinstance(widget, (MajorSearchWidget, SchoolSearchWidget, LineEdit)):
                                value = widget.text().strip()
                            else:
                                value = ""

                            if value:
                                member_info[field_name] = value
                    members.append(member_info)
        return members

    def _apply_theme(self):
        """应用主题 - 标题栏、背景和控件都跟随系统主题"""
        is_dark = self.theme_manager.is_dark
        if is_dark:
            bg_color = "#232635"  # 对话框背景跟随主题背景
            text_color = "#f2f4ff"
            input_bg = "#2a2a3a"
            border_color = "#4a4a5e"
        else:
            bg_color = "#f4f6fb"  # 浅色背景
            text_color = "#1e2746"
            input_bg = "#ffffff"
            border_color = "#e0e0e0"

        self.setStyleSheet(f"""
            #centerWidget {{
                background-color: {bg_color};
                border-radius: 8px;
                border: 1px solid {border_color};
            }}
            QDialog {{
                background-color: {bg_color};
                color: {text_color};
            }}
            QLabel {{
                color: {text_color};
            }}
            LineEdit {{
                border: 1px solid {border_color};
                border-radius: 8px;
                padding: 6px;
                background-color: {input_bg};
                color: {text_color};
            }}
            QComboBox {{
                border: 1px solid {border_color};
                border-radius: 8px;
                padding: 6px;
                background-color: {input_bg};
                color: {text_color};
            }}
            QSpinBox {{
                border: 1px solid {border_color};
                border-radius: 8px;
                padding: 6px;
                background-color: {input_bg};
                color: {text_color};
            }}
            QGroupBox {{
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }}
        """)

        # 设置 Palette 使标题栏也跟随主题
        palette = QPalette()
        if is_dark:
            palette.setColor(QPalette.ColorRole.Window, QColor("#232635"))
            palette.setColor(QPalette.ColorRole.WindowText, QColor("#f2f4ff"))
            palette.setColor(QPalette.ColorRole.Base, QColor("#2a2a3a"))
            palette.setColor(QPalette.ColorRole.Text, QColor("#f2f4ff"))
            palette.setColor(QPalette.ColorRole.Button, QColor("#2a2a3a"))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor("#f2f4ff"))
        else:
            palette.setColor(QPalette.ColorRole.Window, QColor("#f4f6fb"))
            palette.setColor(QPalette.ColorRole.WindowText, QColor("#1e2746"))
            palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
            palette.setColor(QPalette.ColorRole.Text, QColor("#1e2746"))
            palette.setColor(QPalette.ColorRole.Button, QColor("#ffffff"))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor("#1e2746"))
        self.setPalette(palette)

        # 关键：在Windows上强制设置标题栏颜色
        # 通过设置WA_NoSystemBackground来禁用系统默认背景，然后自己绘制
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
