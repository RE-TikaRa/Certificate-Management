from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QLabel,
    QInputDialog,
    QScrollArea,
    QMenu,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
)
from qfluentwidgets import CheckBox, PrimaryPushButton, PushButton

from ..theme import create_card, create_page_header, make_section_title
from ..styled_theme import ThemeManager

from .base_page import BasePage


class EntryPage(BasePage):
    def __init__(self, ctx, theme_manager: ThemeManager):
        super().__init__(ctx, theme_manager)
        self.selected_files: list[Path] = []
        self.editing_award = None  # 当前正在编辑的荣誉
        self._build_ui()

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer_layout.addWidget(scroll)

        container = QWidget()
        container.setObjectName("pageRoot")  # Apply background color from QSS
        scroll.setWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 24, 32, 32)
        layout.setSpacing(28)
        layout.addWidget(create_page_header("荣誉录入", "集中采集证书信息并同步团队"))

        # === Basic Info Card ===
        info_card, info_layout = create_card()
        
        # Row 1: 比赛名称 + 获奖日期
        row1 = QHBoxLayout()
        row1.setSpacing(16)
        name_col = QVBoxLayout()
        name_label = QLabel("比赛名称")
        name_label.setObjectName("formLabel")
        self.name_input = QLineEdit()
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
        self.year_input = QSpinBox()
        self.year_input.setRange(1900, 2100)
        today = QDate.currentDate()
        self.year_input.setValue(today.year())
        self.year_input.setMaximumWidth(80)
        
        # Month input
        month_label = QLabel("月")
        month_label.setObjectName("formLabel")
        month_label.setMaximumWidth(20)
        self.month_input = QSpinBox()
        self.month_input.setRange(1, 12)
        self.month_input.setValue(today.month())
        self.month_input.setMaximumWidth(80)
        
        # Day input
        day_label = QLabel("日")
        day_label.setObjectName("formLabel")
        day_label.setMaximumWidth(20)
        self.day_input = QSpinBox()
        self.day_input.setRange(1, 31)
        self.day_input.setValue(today.day())
        self.day_input.setMaximumWidth(80)
        
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
        self.level_input = QComboBox()
        self.level_input.addItems(["国家级", "省级", "校级"])
        level_col.addWidget(level_label)
        level_col.addWidget(self.level_input)
        
        rank_col = QVBoxLayout()
        rank_label = QLabel("奖项等级")
        rank_label.setObjectName("formLabel")
        self.rank_input = QComboBox()
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
        self.certificate_input = QLineEdit()
        cert_col.addWidget(cert_label)
        cert_col.addWidget(self.certificate_input)
        info_layout.addLayout(cert_col)
        
        # Row 4: 备注
        remark_col = QVBoxLayout()
        remark_label = QLabel("备注")
        remark_label.setObjectName("formLabel")
        self.remarks_input = QLineEdit()
        remark_col.addWidget(remark_label)
        remark_col.addWidget(self.remarks_input)
        info_layout.addLayout(remark_col)
        
        layout.addWidget(info_card)

        # 成员输入卡片
        members_card, members_layout = create_card()
        members_layout.addWidget(make_section_title("参与成员"))
        
        # 创建成员表格（11列：姓名、性别、年龄、身份证号、手机号、学号、联系电话、邮箱、专业、班级、学院）
        self.members_table = QTableWidget(0, 12)
        self.members_table.setHorizontalHeaderLabels([
            "姓名", "性别", "年龄", "身份证号", "手机号", "学号",
            "联系电话", "邮箱", "专业", "班级", "学院", "删除"
        ])
        
        # 设置列宽
        widths = [100, 60, 50, 120, 100, 80, 100, 120, 100, 100, 100, 60]
        for i, w in enumerate(widths):
            self.members_table.setColumnWidth(i, w)
        
        self.members_table.setMinimumHeight(250)
        from ..theme import apply_table_style
        apply_table_style(self.members_table)
        members_layout.addWidget(self.members_table)
        
        # 添加成员按钮
        add_member_btn = PrimaryPushButton("添加成员")
        add_member_btn.clicked.connect(self._add_member_row)
        members_layout.addWidget(add_member_btn)
        
        layout.addWidget(members_card)

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
        self.clear_btn = PushButton("清空表单")
        self.clear_btn.clicked.connect(self._clear_form)
        self.submit_btn = PrimaryPushButton("保存荣誉")
        self.submit_btn.clicked.connect(self._submit)
        action_row.addWidget(self.clear_btn)
        action_row.addWidget(self.submit_btn)
        layout.addLayout(action_row)
        layout.addStretch()

        self.refresh()
    def _add_member_row(self) -> None:
        """添加新的成员行到表格"""
        row = self.members_table.rowCount()
        self.members_table.insertRow(row)
        
        # 字段列表：姓名、性别、年龄、身份证号、手机号、学号、联系电话、邮箱、专业、班级、学院
        for col in range(11):
            input_widget = QLineEdit()
            self.members_table.setCellWidget(row, col, input_widget)
        
        # 删除按钮
        delete_btn = PushButton("删除")
        delete_btn.clicked.connect(lambda: self._remove_member_row(row))
        self.members_table.setCellWidget(row, 11, delete_btn)

    def _remove_member_row(self, row: int) -> None:
        """删除一行成员"""
        self.members_table.removeRow(row)

    def _get_members_data(self) -> list[dict]:
        """获取表格中的成员数据"""
        members = []
        field_names = ['name', 'gender', 'age', 'id_card', 'phone', 'student_id',
                       'contact_phone', 'email', 'major', 'class_name', 'college']
        
        for row in range(self.members_table.rowCount()):
            name_widget = self.members_table.cellWidget(row, 0)
            
            if isinstance(name_widget, QLineEdit):
                name = name_widget.text().strip()
                if name:  # 只记录有姓名的成员
                    member_info = {'name': name}
                    
                    # 收集其他字段
                    for col, field in enumerate(field_names[1:], start=1):
                        widget = self.members_table.cellWidget(row, col)
                        if isinstance(widget, QLineEdit):
                            value = widget.text().strip()
                            if value:
                                # 年龄转换为整数
                                if field == 'age':
                                    try:
                                        member_info[field] = int(value)
                                    except ValueError:
                                        pass
                                else:
                                    member_info[field] = value
                    
                    members.append(member_info)
        return members

    def _pick_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "选择附件")
        self.selected_files = [Path(f) for f in files]
        if self.selected_files:
            self.attach_label.setText(f"已选择 {len(self.selected_files)} 个文件")
        else:
            self.attach_label.setText("未选择附件")

    def load_award_for_editing(self, award) -> None:
        """加载荣誉信息用于编辑"""
        self.editing_award = award
        self.submit_btn.setText("更新荣誉")
        self.clear_btn.setText("取消编辑")
        
        # 填充基本信息
        self.name_input.setText(award.competition_name)
        self.year_input.setValue(award.award_date.year)
        self.month_input.setValue(award.award_date.month)
        self.day_input.setValue(award.award_date.day)
        self.level_input.setCurrentText(award.level)
        self.rank_input.setCurrentText(award.rank)
        self.certificate_input.setText(award.certificate_code or "")
        self.remarks_input.setText(award.remarks or "")
        
        # 清空并填充成员信息
        self.members_table.setRowCount(0)
        for member in award.members:
            row = self.members_table.rowCount()
            self.members_table.insertRow(row)
            
            # 填充各字段
            fields = [
                member.name or "",
                member.gender or "",
                str(member.age) if member.age else "",
                member.id_card or "",
                member.phone or "",
                member.student_id or "",
                member.contact_phone or "",
                member.email or "",
                member.major or "",
                member.class_name or "",
                member.college or "",
            ]
            
            for col, value in enumerate(fields):
                widget = QLineEdit()
                widget.setText(value)
                self.members_table.setCellWidget(row, col, widget)
            
            # 删除按钮
            delete_btn = PushButton("删除")
            delete_btn.clicked.connect(lambda checked, r=row: self._remove_member_row(r))
            self.members_table.setCellWidget(row, 11, delete_btn)
        
        self.selected_files = []
        self.attach_label.setText("未选择附件")

    def refresh(self) -> None:
        """刷新页面（可选）"""
        pass

    def _submit(self) -> None:
        issues = self._validate_form()
        if issues:
            QMessageBox.warning(self, "表单不合法", "\n".join(issues))
            return
        
        # 获取成员数据
        members_data = self._get_members_data()
        if not members_data:
            QMessageBox.warning(self, "表单不合法", "请至少添加一名成员。")
            return
        
        if self.editing_award:
            # 编辑模式：更新现有荣誉
            award = self.editing_award
            award.competition_name = self.name_input.text().strip()
            award.award_date = QDate(self.year_input.value(), self.month_input.value(), self.day_input.value()).toPython()
            award.level = self.level_input.currentText()
            award.rank = self.rank_input.currentText()
            award.certificate_code = self.certificate_input.text().strip() or None
            award.remarks = self.remarks_input.text().strip() or None
            
            # 更新成员关联
            with self.ctx.db.session_scope() as session:
                db_award = session.get(type(award), award.id)
                if db_award:
                    # 清空现有成员
                    db_award.members.clear()
                    # 添加新成员
                    for member_info in members_data:
                        member = self.ctx.awards._get_or_create_member_with_info(session, member_info)
                        db_award.members.append(member)
                    session.commit()
            
            QMessageBox.information(self, "成功", f"已更新：{award.competition_name}")
        else:
            # 创建模式：创建新荣誉
            award = self.ctx.awards.create_award(
                competition_name=self.name_input.text().strip(),
                award_date=QDate(self.year_input.value(), self.month_input.value(), self.day_input.value()).toPython(),
                level=self.level_input.currentText(),
                rank=self.rank_input.currentText(),
                certificate_code=self.certificate_input.text().strip() or None,
                remarks=self.remarks_input.text().strip() or None,
                member_names=members_data,
                tag_names=[],
                attachment_files=self.selected_files,
            )
            QMessageBox.information(self, "成功", f"已保存：{award.competition_name}")
        
        self._clear_form()

    def _clear_form(self) -> None:
        self.name_input.clear()
        today = QDate.currentDate()
        self.year_input.setValue(today.year())
        self.month_input.setValue(today.month())
        self.day_input.setValue(today.day())
        self.level_input.setCurrentIndex(0)
        self.rank_input.setCurrentIndex(0)
        self.certificate_input.clear()
        self.remarks_input.clear()
        self.selected_files = []
        self.attach_label.setText("未选择附件")
        # 清空成员表格
        self.members_table.setRowCount(0)
        
        # 退出编辑模式
        if self.editing_award:
            self.editing_award = None
            self.submit_btn.setText("保存荣誉")
            self.clear_btn.setText("清空表单")

    def _validate_form(self) -> list[str]:
        issues: list[str] = []
        name = self.name_input.text().strip()
        if not name:
            issues.append("比赛名称不能为空。")
        try:
            award_date = QDate(self.year_input.value(), self.month_input.value(), self.day_input.value())
            if not award_date.isValid():
                issues.append("获奖日期不合法。")
            elif award_date > QDate.currentDate():
                issues.append("获奖日期不能晚于今天。")
        except Exception:
            issues.append("获奖日期不合法。")
        
        # 检查是否有成员输入
        has_members = any(
            self.members_table.cellWidget(row, 0).text().strip() 
            for row in range(self.members_table.rowCount())
            if isinstance(self.members_table.cellWidget(row, 0), QLineEdit)
        )
        if not has_members:
            issues.append("请至少添加一名成员。")
        
        code = self.certificate_input.text().strip()
        if len(code) > 128:
            issues.append("证书编号长度不能超过 128 字符。")
        return issues
