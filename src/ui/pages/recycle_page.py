from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
from qfluentwidgets import PrimaryPushButton, PushButton

from ..theme import apply_table_style, create_card, create_page_header, make_section_title

from .base_page import BasePage


class RecyclePage(BasePage):
    def __init__(self, ctx):
        super().__init__(ctx)
        layout = QVBoxLayout(self)
        layout.setSpacing(18)
        layout.addWidget(create_page_header("附件回收站", "统一管理已删除的附件"))

        card, card_layout = create_card()
        card_layout.addWidget(make_section_title("删除附件列表"))
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["编号", "原文件名", "删除时间", "路径"])
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
        attachments = self.ctx.attachments.list_deleted()
        self.table.setRowCount(len(attachments))
        for row, attachment in enumerate(attachments):
            self.table.setItem(row, 0, QTableWidgetItem(str(attachment.id)))
            self.table.setItem(row, 1, QTableWidgetItem(attachment.original_name))
            self.table.setItem(row, 2, QTableWidgetItem(str(attachment.deleted_at)))
            self.table.setItem(row, 3, QTableWidgetItem(attachment.relative_path))

    def _selected_ids(self) -> list[int]:
        ids = []
        selection = self.table.selectionModel()
        if selection is None:
            return ids
        for index in selection.selectedRows():
            ids.append(int(self.table.item(index.row(), 0).text()))
        return ids

    def _restore(self) -> None:
        ids = self._selected_ids()
        if not ids:
            return
        self.ctx.attachments.restore(ids)
        self.refresh()

    def _purge(self) -> None:
        ids = self._selected_ids()
        if not ids:
            return
        self.ctx.attachments.purge_deleted(ids)
        self.refresh()
