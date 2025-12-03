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

from ...services.validators import FormValidator
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
        
        # 成员列表容器 - 直接使用 QWidget，会自动扩展
        self.members_container = QWidget()
        self.members_container.setStyleSheet("QWidget { background-color: transparent; }")
        self.members_list_layout = QVBoxLayout(self.members_container)
        self.members_list_layout.setContentsMargins(0, 0, 0, 0)
        self.members_list_layout.setSpacing(12)
        self.members_list_layout.setSizeConstraint(QVBoxLayout.SetMinAndMaxSize)  # 自动调整大小
        
        # 成员卡片会自动扩展父容器的高度
        members_layout.addWidget(self.members_container)
        
        # 存储成员数据的列表（用于保存和提取）
        self.members_data = []
        
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
        """添加新的成员卡片（表单列表风格）"""
        import logging
        from ...services.validators import FormValidator
        
        logger = logging.getLogger(__name__)
        
        # 创建成员卡片
        member_card = QWidget()
        # 深色模式和浅色模式的样式
        is_dark = self.theme_manager.is_dark
        if is_dark:
            card_style = """
                QWidget {
                    background-color: #353751;
                    border-radius: 8px;
                    border: 1px solid #4a4a5e;
                }
            """
            label_style = "color: #a0a0a0; font-size: 12px;"
            input_style = """
                QLineEdit {
                    border: 1px solid #4a4a5e;
                    border-radius: 4px;
                    padding: 6px;
                    background-color: #2a2a3a;
                    color: #e0e0e0;
                }
                QLineEdit:focus {
                    border: 2px solid #4a90e2;
                    color: #e0e0e0;
                }
            """
        else:
            card_style = """
                QWidget {
                    background-color: #f5f5f5;
                    border-radius: 8px;
                    border: 1px solid #e0e0e0;
                }
            """
            label_style = "color: #666; font-size: 12px;"
            input_style = """
                QLineEdit {
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    padding: 6px;
                    background-color: white;
                    color: #333;
                }
                QLineEdit:focus {
                    border: 2px solid #1890ff;
                    color: #333;
                }
            """
        
        member_card.setStyleSheet(card_style)
        member_layout = QVBoxLayout(member_card)
        member_layout.setContentsMargins(12, 12, 12, 12)
        member_layout.setSpacing(10)
        
        # 成员编号和删除按钮
        header_layout = QHBoxLayout()
        member_index = len(self.members_data) + 1
        member_label = QLabel(f"成员 #{member_index}")
        member_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        header_layout.addWidget(member_label)
        header_layout.addStretch()
        
        delete_btn = PushButton("删除")
        delete_btn.setMaximumWidth(60)
        member_layout.addLayout(header_layout)
        
        # 创建3列的表单布局
        form_grid = QGridLayout()
        form_grid.setSpacing(12)
        form_grid.setColumnStretch(1, 1)
        form_grid.setColumnStretch(3, 1)
        
        # 字段配置：标签、输入框（按2列布局）
        field_names = ['name', 'gender', 'id_card', 'phone', 'student_id', 
                       'email', 'major', 'class_name', 'college']
        field_labels = ['姓名', '性别', '身份证号', '手机号', '学号', 
                        '邮箱', '专业', '班级', '学院']
        
        # 存储该成员的所有字段输入框
        member_fields = {}
        
        # 首先创建所有输入框
        for field_name, label in zip(field_names, field_labels):
            input_widget = QLineEdit()
            input_widget.setPlaceholderText(f"请输入{label}")
            input_widget.setStyleSheet(input_style)
            member_fields[field_name] = input_widget
        
        # 然后按2列布局添加到表单
        for idx, (field_name, label) in enumerate(zip(field_names, field_labels)):
            col = (idx % 2) * 2
            row = idx // 2
            
            label_widget = QLabel(label)
            label_widget.setStyleSheet(label_style)
            label_widget.setMinimumWidth(50)
            label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 标签居中
            
            form_grid.addWidget(label_widget, row, col, alignment=Qt.AlignmentFlag.AlignCenter)
            form_grid.addWidget(member_fields[field_name], row, col + 1)
        
        member_layout.addLayout(form_grid)
        
        # 删除按钮
        delete_btn.clicked.connect(lambda: self._remove_member_card(member_card, member_fields))
        header_layout.addWidget(delete_btn)
        
        # 保存成员数据
        member_data = {
            'card': member_card,
            'fields': member_fields
        }
        self.members_data.append(member_data)
        
        # 添加到列表
        self.members_list_layout.addWidget(member_card)
        
        logger.debug(f"成员 #{member_index} 已添加，总成员数：{len(self.members_data)}")

    def _remove_member_card(self, member_card: QWidget, member_fields: dict) -> None:
        """删除一个成员卡片"""
        # 从列表中移除
        for idx, data in enumerate(self.members_data):
            if data['card'] == member_card:
                self.members_data.pop(idx)
                break
        
        # 从UI中移除
        member_card.deleteLater()

    def _get_members_data(self) -> list[dict]:
        """获取成员卡片中的成员数据"""
        members = []
        field_names = ['name', 'gender', 'id_card', 'phone', 'student_id',
                       'email', 'major', 'class_name', 'college']
        
        for member_data in self.members_data:
            member_fields = member_data['fields']
            
            # 获取姓名，如果有则表示成员有效
            name_widget = member_fields.get('name')
            if isinstance(name_widget, QLineEdit):
                name = name_widget.text().strip()
                if name:  # 只记录有姓名的成员
                    member_info = {'name': name}
                    
                    # 收集其他字段
                    for field_name in field_names[1:]:
                        widget = member_fields.get(field_name)
                        if isinstance(widget, QLineEdit):
                            value = widget.text().strip()
                            if value:
                                member_info[field_name] = value
                    
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
        
        # 清空并填充成员信息（使用新的表单卡片风格）
        for member_data in self.members_data:
            member_data['card'].deleteLater()
        self.members_data.clear()
        
        for member in award.members:
            # 添加新的成员卡片
            self._add_member_row()
            
            # 填充最后添加的成员卡片的数据
            member_data = self.members_data[-1]
            member_fields = member_data['fields']
            
            # 映射成员数据到表单字段
            field_mapping = {
                'name': member.name or "",
                'gender': member.gender or "",
                'id_card': member.id_card or "",
                'age': str(member.age) if member.age else "",
                'phone': member.phone or "",
                'student_id': member.student_id or "",
                'email': member.email or "",
                'major': member.major or "",
                'class_name': member.class_name or "",
                'college': member.college or "",
            }
            
            for field_name, value in field_mapping.items():
                if field_name in member_fields:
                    member_fields[field_name].setText(value)
        
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
        # 清空成员卡片
        for member_data in self.members_data:
            member_data['card'].deleteLater()
        self.members_data.clear()
        
        # 退出编辑模式
        if self.editing_award:
            self.editing_award = None
            self.submit_btn.setText("保存荣誉")
            self.clear_btn.setText("清空表单")

    def _validate_form(self) -> list[str]:
        """
        Validate the entire award form using FormValidator.
        Returns list of error messages (empty if valid).
        """
        issues: list[str] = []
        
        # Validate competition name
        name = self.name_input.text().strip()
        valid, msg = FormValidator.validate_competition_name(name)
        if not valid:
            issues.append(msg)
        
        # Validate award date
        try:
            award_date = QDate(self.year_input.value(), self.month_input.value(), self.day_input.value())
            if not award_date.isValid():
                issues.append("获奖日期不合法。")
            elif award_date > QDate.currentDate():
                issues.append("获奖日期不能晚于今天。")
        except Exception:
            issues.append("获奖日期不合法。")
        
        # Validate certificate code
        code = self.certificate_input.text().strip()
        valid, msg = FormValidator.validate_certificate_code(code)
        if not valid:
            issues.append(msg)
        
        # Validate remarks
        remarks = self.remarks_input.text().strip()
        valid, msg = FormValidator.validate_remarks(remarks)
        if not valid:
            issues.append(msg)
        
        # Validate members
        members_data = self._get_members_data()
        if not members_data:
            issues.append("请至少添加一名成员。")
        else:
            # Validate each member's information
            for i, member in enumerate(members_data, 1):
                member_errors = FormValidator.validate_member_info(member)
                for error in member_errors:
                    issues.append(f"成员 {i} - {error}")
        
        return issues
