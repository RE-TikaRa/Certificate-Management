from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
from qfluentwidgets import PrimaryPushButton, PushButton, InfoBar, MessageBox

from ..theme import apply_table_style, create_card, create_page_header, make_section_title
from ..styled_theme import ThemeManager

from .base_page import BasePage


class RecyclePage(BasePage):
    def __init__(self, ctx, theme_manager: ThemeManager):
        super().__init__(ctx, theme_manager)
        self.setObjectName("pageRoot")
        layout = QVBoxLayout(self)
        layout.setSpacing(18)
        layout.addWidget(create_page_header("荣誉回收站", "管理已删除的荣誉记录"))

        card, card_layout = create_card()
        
        # 标题和刷新按钮
        header_layout = QHBoxLayout()
        header_layout.addWidget(make_section_title("已删除的荣誉列表"))
        header_layout.addStretch()
        from qfluentwidgets import TransparentToolButton, FluentIcon
        refresh_btn = TransparentToolButton(FluentIcon.SYNC)
        refresh_btn.setToolTip("刷新数据")
        refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(refresh_btn)
        card_layout.addLayout(header_layout)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["ID", "比赛名称", "级别", "奖项等级", "获奖日期", "删除时间"])
        apply_table_style(self.table)
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
        awards = self.ctx.awards.list_deleted_awards()
        self.table.setRowCount(len(awards))
        for row, award in enumerate(awards):
            item0 = QTableWidgetItem(str(award.id))
            item0.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, item0)
            
            item1 = QTableWidgetItem(award.competition_name)
            item1.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 1, item1)
            
            item2 = QTableWidgetItem(award.level)
            item2.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 2, item2)
            
            item3 = QTableWidgetItem(award.rank)
            item3.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 3, item3)
            
            item4 = QTableWidgetItem(str(award.award_date))
            item4.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 4, item4)
            
            deleted_time = award.deleted_at.strftime("%Y-%m-%d %H:%M:%S") if award.deleted_at else ""
            item5 = QTableWidgetItem(deleted_time)
            item5.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 5, item5)

    def _selected_ids(self) -> list[int]:
        ids = []
        selection = self.table.selectionModel()
        if selection is None:
            return ids
        for index in selection.selectedRows():
            ids.append(int(self.table.item(index.row(), 0).text()))
        return ids

    def _restore(self) -> None:
        """恢复选中的荣誉记录"""
        ids = self._selected_ids()
        if not ids:
            InfoBar.warning("提示", "请选择要恢复的荣誉记录", parent=self.window())
            return
        
        box = MessageBox(
            "确认恢复",
            f"确定要恢复选中的 {len(ids)} 条荣誉记录吗？",
            self.window()
        )
        
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
            self.window()
        )
        
        if box.exec():
            for award_id in ids:
                self.ctx.awards.permanently_delete_award(award_id)
            self.refresh()
            InfoBar.success("成功", f"已彻底删除 {len(ids)} 条荣誉记录", parent=self.window())
