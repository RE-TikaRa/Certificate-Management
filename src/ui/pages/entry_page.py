from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QDateEdit,
    QComboBox,
    QLabel,
    QInputDialog,
    QScrollArea,
    QMenu,
    QDialog,
    QDialogButtonBox,
    QCheckBox,
)
from qfluentwidgets import PrimaryPushButton, PushButton

from ..theme import create_card, create_page_header, make_section_title

from .base_page import BasePage


class EntryPage(BasePage):
    def __init__(self, ctx):
        super().__init__(ctx)
        self.selected_files: list[Path] = []
        self._build_ui()

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer_layout.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 24, 32, 32)
        layout.setSpacing(28)
        layout.addWidget(create_page_header("荣誉录入", "集中采集证书信息并同步团队"))

        info_card, info_layout = create_card()
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        form_layout.setSpacing(18)
        form_layout.setContentsMargins(0, 0, 0, 0)

        self.name_input = QLineEdit()
        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDate(QDate.currentDate())
        self.level_input = QComboBox()
        self.level_input.addItems(["国家级", "省级", "市级", "校级"])
        self.rank_input = QComboBox()
        self.rank_input.addItems(["一等奖", "二等奖", "三等奖", "优胜奖"])
        self.certificate_input = QLineEdit()
        self.remarks_input = QTextEdit()
        self.remarks_input.setMinimumHeight(140)

        form_layout.addRow("比赛名称", self.name_input)
        form_layout.addRow("获奖日期", self.date_input)
        form_layout.addRow("赛事级别", self.level_input)
        form_layout.addRow("奖项等级", self.rank_input)
        form_layout.addRow("证书编号", self.certificate_input)
        form_layout.addRow("备注", self.remarks_input)
        info_layout.addWidget(form_widget)
        layout.addWidget(info_card)

        lists_card, lists_layout = create_card()
        lists_layout.addWidget(make_section_title("成员与标签"))
        selection_layout = QGridLayout()
        selection_layout.setHorizontalSpacing(24)
        selection_layout.setVerticalSpacing(16)
        self.members_list = QListWidget()
        self.tags_list = QListWidget()
        self.members_list.setMinimumHeight(160)
        self.tags_list.setMinimumHeight(160)
        selection_layout.addWidget(self._build_list_header("成员", self.members_list, target="member"), 0, 0)
        selection_layout.addWidget(self.members_list, 1, 0)
        selection_layout.addWidget(self._build_list_header("标签", self.tags_list, target="tag"), 0, 1)
        selection_layout.addWidget(self.tags_list, 1, 1)
        lists_layout.addLayout(selection_layout)

        btn_row = QHBoxLayout()
        member_btn = PushButton("新增成员")
        member_btn.clicked.connect(self._add_member)
        tag_btn = PushButton("新增标签")
        tag_btn.clicked.connect(self._add_tag)
        member_import = PushButton("批量选择成员")
        member_import.clicked.connect(lambda: self._import_existing("member"))
        tag_import = PushButton("批量选择标签")
        tag_import.clicked.connect(lambda: self._import_existing("tag"))
        btn_row.addWidget(member_btn)
        btn_row.addWidget(member_import)
        btn_row.addWidget(tag_btn)
        btn_row.addWidget(tag_import)
        btn_row.addStretch()
        lists_layout.addLayout(btn_row)
        layout.addWidget(lists_card)

        attachment_card, attachment_layout = create_card()
        attachment_layout.addWidget(make_section_title("附件"))
        attach_row = QHBoxLayout()
        self.attach_label = QLabel("未选择附件")
        self.attach_label.setProperty("inputField", True)
        attach_row.addWidget(self.attach_label)
        attach_row.addStretch()
        attach_btn = PushButton("选择文件")
        attach_btn.clicked.connect(self._pick_files)
        attach_row.addWidget(attach_btn)
        attachment_layout.addLayout(attach_row)
        layout.addWidget(attachment_card)

        action_row = QHBoxLayout()
        action_row.addStretch()
        clear_btn = PushButton("清空表单")
        clear_btn.clicked.connect(self._clear_form)
        submit_btn = PrimaryPushButton("保存荣誉")
        submit_btn.clicked.connect(self._submit)
        action_row.addWidget(clear_btn)
        action_row.addWidget(submit_btn)
        layout.addLayout(action_row)
        layout.addStretch()

        self.refresh()

    def _build_list_header(self, title: str, target_list: QListWidget, target: str) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        label = QLabel(title)
        row.addWidget(label)
        row.addStretch()
        more_btn = PushButton("管理")
        more_btn.setFixedHeight(30)
        more_btn.clicked.connect(lambda: self._show_selection_menu(target_list, target))
        row.addWidget(more_btn)
        return container

    def _show_selection_menu(self, widget: QListWidget, target: str) -> None:
        menu = QMenu(self)
        check_all = menu.addAction("全选")
        uncheck_all = menu.addAction("全不选")
        import_existing = menu.addAction("从现有导入选择")
        action = menu.exec(QCursor.pos())
        if action == check_all:
            for i in range(widget.count()):
                widget.item(i).setCheckState(Qt.Checked)
        elif action == uncheck_all:
            for i in range(widget.count()):
                widget.item(i).setCheckState(Qt.Unchecked)
        elif action == import_existing:
            self._import_existing(target)

    def refresh(self) -> None:
        self.members_list.clear()
        for member in self.ctx.awards.list_members():
            item = QListWidgetItem(member.name)
            item.setCheckState(Qt.Unchecked)
            self.members_list.addItem(item)

        self.tags_list.clear()
        for tag in self.ctx.awards.list_tags():
            item = QListWidgetItem(tag.name)
            item.setCheckState(Qt.Unchecked)
            self.tags_list.addItem(item)

    def _add_member(self) -> None:
        name, ok = QInputDialog.getText(self, "新增成员", "成员姓名")
        if ok and name.strip():
            self.ctx.awards.add_member(name.strip())
            self.refresh()

    def _add_tag(self) -> None:
        name, ok = QInputDialog.getText(self, "新增标签", "标签名称")
        if ok and name.strip():
            self.ctx.awards.add_tag(name.strip())
            self.refresh()

    def _import_existing(self, target: str) -> None:
        if target == "member":
            items = self.ctx.awards.list_members()
            widget = self.members_list
            title = "选择成员"
        else:
            items = self.ctx.awards.list_tags()
            widget = self.tags_list
            title = "选择标签"

        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog_layout = QVBoxLayout(dialog)
        checkboxes: list[QCheckBox] = []
        current = {widget.item(i).text(): widget.item(i).checkState() == Qt.Checked for i in range(widget.count())}

        for item in items:
            name = item.name
            cb = QCheckBox(name)
            cb.setChecked(current.get(name, False))
            dialog_layout.addWidget(cb)
            checkboxes.append(cb)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        dialog_layout.addWidget(buttons)

        if dialog.exec() == QDialog.Accepted:
            for cb in checkboxes:
                for i in range(widget.count()):
                    if widget.item(i).text() == cb.text():
                        widget.item(i).setCheckState(Qt.Checked if cb.isChecked() else Qt.Unchecked)
                        break

    def _pick_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "选择附件")
        self.selected_files = [Path(f) for f in files]
        if self.selected_files:
            self.attach_label.setText(f"已选择 {len(self.selected_files)} 个文件")
        else:
            self.attach_label.setText("未选择附件")

    def _get_checked(self, widget: QListWidget) -> list[str]:
        checked = []
        for i in range(widget.count()):
            item = widget.item(i)
            if item.checkState() == Qt.Checked:
                checked.append(item.text())
        return checked

    def _submit(self) -> None:
        issues = self._validate_form()
        if issues:
            QMessageBox.warning(self, "表单不合法", "\n".join(issues))
            return
        award = self.ctx.awards.create_award(
            competition_name=self.name_input.text().strip(),
            award_date=self.date_input.date().toPython(),
            level=self.level_input.currentText(),
            rank=self.rank_input.currentText(),
            certificate_code=self.certificate_input.text().strip() or None,
            remarks=self.remarks_input.toPlainText().strip() or None,
            member_names=self._get_checked(self.members_list),
            tag_names=self._get_checked(self.tags_list),
            attachment_files=self.selected_files,
        )
        QMessageBox.information(self, "成功", f"已保存：{award.competition_name}")
        self._clear_form()

    def _clear_form(self) -> None:
        self.name_input.clear()
        self.date_input.setDate(QDate.currentDate())
        self.level_input.setCurrentIndex(0)
        self.rank_input.setCurrentIndex(0)
        self.certificate_input.clear()
        self.remarks_input.clear()
        self.selected_files = []
        self.attach_label.setText("未选择附件")
        for widget in (self.members_list, self.tags_list):
            for i in range(widget.count()):
                widget.item(i).setCheckState(Qt.Unchecked)

    def _validate_form(self) -> list[str]:
        issues: list[str] = []
        name = self.name_input.text().strip()
        if not name:
            issues.append("比赛名称不能为空。")
        if self.date_input.date() > QDate.currentDate():
            issues.append("获奖日期不能晚于今天。")
        members_selected = any(self.members_list.item(i).checkState() == Qt.Checked for i in range(self.members_list.count()))
        tags_selected = any(self.tags_list.item(i).checkState() == Qt.Checked for i in range(self.tags_list.count()))
        if not (members_selected or tags_selected):
            issues.append("请至少选择一名成员或一个标签。")
        code = self.certificate_input.text().strip()
        if len(code) > 128:
            issues.append("证书编号长度不能超过 128 字符。")
        return issues
