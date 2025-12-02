from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QDateEdit,
    QComboBox,
    QLabel,
    QInputDialog,
)
from qfluentwidgets import PrimaryPushButton

from .base_page import BasePage


class EntryPage(BasePage):
    def __init__(self, ctx):
        super().__init__(ctx)
        self.selected_files: list[Path] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form_box = QGroupBox("荣誉信息")
        form_layout = QFormLayout(form_box)

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

        form_layout.addRow("比赛名称", self.name_input)
        form_layout.addRow("获奖日期", self.date_input)
        form_layout.addRow("赛事级别", self.level_input)
        form_layout.addRow("奖项等级", self.rank_input)
        form_layout.addRow("证书编号", self.certificate_input)
        form_layout.addRow("备注", self.remarks_input)

        layout.addWidget(form_box)

        selection_layout = QGridLayout()
        self.members_list = QListWidget()
        self.tags_list = QListWidget()
        selection_layout.addWidget(QLabel("成员"), 0, 0)
        selection_layout.addWidget(self.members_list, 1, 0)
        selection_layout.addWidget(QLabel("标签"), 0, 1)
        selection_layout.addWidget(self.tags_list, 1, 1)
        layout.addLayout(selection_layout)

        member_btn = QPushButton("新增成员")
        member_btn.clicked.connect(self._add_member)
        tag_btn = QPushButton("新增标签")
        tag_btn.clicked.connect(self._add_tag)
        layout.addWidget(member_btn)
        layout.addWidget(tag_btn)

        attach_box = QGroupBox("附件")
        attach_layout = QHBoxLayout(attach_box)
        self.attach_label = QLabel("未选择附件")
        attach_btn = QPushButton("选择文件")
        attach_btn.clicked.connect(self._pick_files)
        attach_layout.addWidget(self.attach_label)
        attach_layout.addWidget(attach_btn)
        layout.addWidget(attach_box)

        submit_btn = PrimaryPushButton("保存荣誉")
        submit_btn.clicked.connect(self._submit)
        layout.addWidget(submit_btn)
        layout.addStretch()

        self.refresh()

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
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "提示", "请填写比赛名称")
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
        self.selected_files = []
        self.attach_label.setText("未选择附件")
        self.name_input.clear()
        self.certificate_input.clear()
        self.remarks_input.clear()
        self.refresh()
