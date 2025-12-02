from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .base_page import BasePage


class RecyclePage(BasePage):
    def __init__(self, ctx):
        super().__init__(ctx)
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["编号", "原文件名", "删除时间", "路径"])
        layout.addWidget(self.table)
        btns = QHBoxLayout()
        restore_btn = QPushButton("恢复")
        restore_btn.clicked.connect(self._restore)
        purge_btn = QPushButton("彻底删除")
        purge_btn.clicked.connect(self._purge)
        btns.addWidget(restore_btn)
        btns.addWidget(purge_btn)
        layout.addLayout(btns)
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
