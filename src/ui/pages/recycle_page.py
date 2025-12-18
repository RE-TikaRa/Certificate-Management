import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QScrollArea,
    QTableView,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    FluentIcon,
    InfoBar,
    MessageBox,
    PrimaryPushButton,
    PushButton,
    TransparentToolButton,
)

from ..styled_theme import ThemeManager
from ..table_models import ObjectTableModel
from ..theme import (
    apply_table_style,
    create_card,
    create_page_header,
    make_section_title,
)
from ..utils.async_utils import run_in_thread_guarded
from .base_page import BasePage

logger = logging.getLogger(__name__)


class RecyclePage(BasePage):
    def __init__(self, ctx, theme_manager: ThemeManager):
        super().__init__(ctx, theme_manager)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        title_widget = QWidget()
        title_widget.setObjectName("pageRoot")
        title_layout = QVBoxLayout(title_widget)
        title_layout.setContentsMargins(32, 24, 32, 0)
        title_layout.setSpacing(0)
        title_layout.addWidget(create_page_header("回收站", "管理已删除的荣誉记录"))
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

        card, card_layout = create_card()

        header_layout = QHBoxLayout()
        header_layout.addWidget(make_section_title("已删除的荣誉列表"))
        header_layout.addStretch()
        refresh_btn = TransparentToolButton(FluentIcon.SYNC)
        refresh_btn.setToolTip("刷新数据")
        refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(refresh_btn)
        card_layout.addLayout(header_layout)
        headers = ["ID", "比赛名称", "级别", "奖项等级", "获奖日期", "删除时间"]
        accessors = [
            lambda a: a.id,
            lambda a: a.competition_name,
            lambda a: a.level,
            lambda a: a.rank,
            lambda a: a.award_date,
            lambda a: a.deleted_at.strftime("%Y-%m-%d %H:%M:%S") if a.deleted_at else "",
        ]
        self.model = ObjectTableModel(headers, accessors, self)
        self.table = QTableView()
        self.table.setModel(self.model)
        apply_table_style(self.table)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        card_layout.addWidget(self.table)
        btns = QHBoxLayout()
        restore_btn = PrimaryPushButton("恢复")
        restore_btn.clicked.connect(self._restore)
        purge_btn = PushButton("彻底删除")
        purge_btn.clicked.connect(self._purge)
        btns.addWidget(restore_btn)
        btns.addWidget(purge_btn)
        btns.addStretch()
        card_layout.addLayout(btns)
        layout.addWidget(card)
        self.refresh()

    def refresh(self) -> None:
        """刷新已删除的荣誉列表"""

        def on_loaded(payload) -> None:
            if isinstance(payload, Exception):
                logger.exception("加载回收站失败: %s", payload)
                InfoBar.error("加载失败", str(payload), parent=self.window())
                return
            self.model.set_objects(payload)

        run_in_thread_guarded(self.ctx.awards.list_deleted_awards, on_loaded, guard=self)

    def _selected_ids(self) -> list[int]:
        ids = []
        selection = self.table.selectionModel()
        if selection is None:
            return ids
        for index in selection.selectedRows():
            ids.append(int(self.model.object_at(index.row()).id))
        return ids

    def _restore(self) -> None:
        """恢复选中的荣誉记录"""
        ids = self._selected_ids()
        if not ids:
            InfoBar.warning("提示", "请选择要恢复的荣誉记录", parent=self.window())
            return

        box = MessageBox("确认恢复", f"确定要恢复选中的 {len(ids)} 条荣誉记录吗？", self.window())

        if box.exec():
            for award_id in ids:
                self.ctx.awards.restore_award(award_id)
            self.refresh()
            InfoBar.success("成功", f"已恢复 {len(ids)} 条荣誉记录", parent=self.window())

    def _purge(self) -> None:
        """彻底删除选中的荣誉记录"""
        ids = self._selected_ids()
        if not ids:
            InfoBar.warning("提示", "请选择要彻底删除的荣誉记录", parent=self.window())
            return

        box = MessageBox(
            "确认彻底删除",
            f"确定要彻底删除选中的 {len(ids)} 条荣誉记录吗？\n\n此操作不可恢复！",
            self.window(),
        )

        if box.exec():
            for award_id in ids:
                self.ctx.awards.permanently_delete_award(award_id)
            self.refresh()
            InfoBar.success("成功", f"已彻底删除 {len(ids)} 条荣誉记录", parent=self.window())
