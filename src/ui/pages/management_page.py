from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
    QLabel,
)
from qfluentwidgets import PrimaryPushButton, PushButton

from ..theme import create_card, create_page_header, make_section_title

from .base_page import BasePage


class ManagementPage(BasePage):
    def __init__(self, ctx):
        super().__init__(ctx)
        layout = QVBoxLayout(self)
        layout.setSpacing(18)
        layout.addWidget(create_page_header("成员与标签", "构建有序的团队与标签体系"))

        main_row = QHBoxLayout()
        main_row.setSpacing(16)

        self.members_list = QListWidget()
        member_panel = self._build_panel("成员", self.members_list, self._add_member, self._remove_member)
        main_row.addWidget(member_panel)

        self.tags_list = QListWidget()
        tag_panel = self._build_panel("标签", self.tags_list, self._add_tag, self._remove_tag)
        main_row.addWidget(tag_panel)

        layout.addLayout(main_row)

        self.refresh()

    def _build_panel(self, title: str, list_widget: QListWidget, add_slot, remove_slot) -> QWidget:
        panel, layout = create_card()
        layout.addWidget(make_section_title(title))
        layout.addWidget(list_widget)
        btn_row = QHBoxLayout()
        add_btn = PrimaryPushButton("新增")
        add_btn.clicked.connect(add_slot)
        remove_btn = PushButton("删除")
        remove_btn.clicked.connect(remove_slot)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(remove_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        return panel

    def refresh(self) -> None:
        self.members_list.clear()
        for member in self.ctx.awards.list_members():
            self.members_list.addItem(QListWidgetItem(member.name))
        self.tags_list.clear()
        for tag in self.ctx.awards.list_tags():
            self.tags_list.addItem(QListWidgetItem(tag.name))

    def _add_member(self) -> None:
        name, ok = QInputDialog.getText(self, "新增成员", "名称")
        if ok and name.strip():
            self.ctx.awards.add_member(name.strip())
            self.refresh()

    def _remove_member(self) -> None:
        current = self.members_list.currentItem()
        if not current:
            return
        self.ctx.awards.remove_member(current.text())
        self.refresh()

    def _add_tag(self) -> None:
        name, ok = QInputDialog.getText(self, "新增标签", "名称")
        if ok and name.strip():
            self.ctx.awards.add_tag(name.strip())
            self.refresh()

    def _remove_tag(self) -> None:
        current = self.tags_list.currentItem()
        if not current:
            return
        self.ctx.awards.remove_tag(current.text())
        self.refresh()
