from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt, QDate, Slot
from PySide6.QtGui import QCursor, QColor, QPalette
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QLabel,
    QScrollArea,
    QMenu,
    QFrame,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)
from qfluentwidgets import CheckBox, PrimaryPushButton, PushButton, InfoBar, MaskDialogBase, TransparentToolButton, FluentIcon

from ...services.validators import FormValidator
from ..theme import create_card, create_page_header, make_section_title
from ..styled_theme import ThemeManager

from .base_page import BasePage


class EntryPage(BasePage):
    def __init__(self, ctx, theme_manager: ThemeManager):
        super().__init__(ctx, theme_manager)
        self.selected_files: list[Path] = []
        self.editing_award = None  # 当前正在编辑的荣誉
        
        # 连接主题变化信号
        self.theme_manager.themeChanged.connect(self._on_theme_changed)
        
        self._build_ui()

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        self.scrollArea = QScrollArea()
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer_layout.addWidget(self.scrollArea)

        container = QWidget()
        container.setObjectName("pageRoot")  # Apply background color from QSS
        self.scrollArea.setWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 24, 32, 32)
        layout.setSpacing(28)
        
        # 页面标题和刷新按钮
        header_layout = QHBoxLayout()
        header_layout.addWidget(create_page_header("荣誉录入", "集中采集证书信息并同步团队"))
        header_layout.addStretch()
        from qfluentwidgets import TransparentToolButton, FluentIcon
        refresh_btn = TransparentToolButton(FluentIcon.SYNC)
        refresh_btn.setToolTip("清空表单")
        refresh_btn.clicked.connect(self._clear_form)
        header_layout.addWidget(refresh_btn)
        layout.addLayout(header_layout)

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

        # === 附件表格卡片 ===
        attachment_card, attachment_layout = create_card()
        
        # 标题和添加按钮
        attach_header = QHBoxLayout()
        attach_header.addWidget(make_section_title("附件"))
        attach_header.addStretch()
        attach_btn = PrimaryPushButton("添加文件")
        attach_btn.clicked.connect(self._pick_files)
        attach_header.addWidget(attach_btn)
        attachment_layout.addLayout(attach_header)
        
        # 附件表格
        self.attach_table = QTableWidget()
        self.attach_table.setColumnCount(5)
        self.attach_table.setHorizontalHeaderLabels(["序号", "附件名", "MD5", "大小", "操作"])
        self.attach_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 序号
        self.attach_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)  # 附件名
        self.attach_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)  # MD5
        self.attach_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 大小
        self.attach_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)  # 操作
        self.attach_table.setMaximumHeight(200)
        self.attach_table.setMinimumHeight(100)
        self.attach_table.verticalHeader().setVisible(False)
        self.attach_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.attach_table.setSelectionBehavior(QTableWidget.SelectRows)
        from ..theme import apply_table_style
        apply_table_style(self.attach_table)
        attachment_layout.addWidget(self.attach_table)
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

        self._apply_theme()
        self.refresh()

    def _add_member_row(self) -> None:
        """添加新的成员卡片（表单列表风格）"""
        import logging
        from ...services.validators import FormValidator
        
        logger = logging.getLogger(__name__)
        
        # 创建成员卡片
        member_card = QWidget()
        # 应用成员卡片样式
        self._apply_member_card_style(member_card)
        
        # 获取当前样式用于标签和输入框
        is_dark = self.theme_manager.is_dark
        if is_dark:
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
        member_layout = QVBoxLayout(member_card)
        member_layout.setContentsMargins(12, 12, 12, 12)
        member_layout.setSpacing(10)
        
        # 成员编号和删除按钮
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)  # 增加按钮间距
        member_index = len(self.members_data) + 1
        member_label = QLabel(f"成员 #{member_index}")
        member_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        header_layout.addWidget(member_label)
        header_layout.addStretch()
        
        # 从历史成员选择按钮
        history_btn = PushButton("从历史选择")
        history_btn.setMinimumWidth(95)  # 使用最小宽度而非最大宽度
        history_btn.setFixedHeight(28)   # 固定高度
        header_layout.addWidget(history_btn)
        
        delete_btn = PushButton("删除")
        delete_btn.setFixedWidth(60)
        delete_btn.setFixedHeight(28)
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
        
        # 从历史成员选择按钮连接
        history_btn.clicked.connect(lambda: self._select_from_history(member_fields))
        
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
    
    def _apply_member_card_style(self, card: QWidget) -> None:
        """应用成员卡片样式（支持主题切换）"""
        is_dark = self.theme_manager.is_dark
        if is_dark:
            card_style = "background-color: #353751; border-radius: 8px; border: 1px solid #4a4a5e;"
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
            card_style = "background-color: #f5f5f5; border-radius: 8px; border: 1px solid #e0e0e0;"
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
        card.setStyleSheet(card_style)
        
        # 更新所有输入框的样式
        for line_edit in card.findChildren(QLineEdit):
            line_edit.setStyleSheet(input_style)

    def _remove_member_card(self, member_card: QWidget, member_fields: dict) -> None:
        """删除一个成员卡片"""
        # 从列表中移除
        for idx, data in enumerate(self.members_data):
            if data['card'] == member_card:
                self.members_data.pop(idx)
                break
        
        # 从UI中移除
        member_card.deleteLater()

    def _select_from_history(self, member_fields: dict) -> None:
        """从历史成员中选择"""
        # 获取所有历史成员
        from ...services.member_service import MemberService
        service = MemberService(self.ctx.db)
        members = service.list_members()
        
        if not members:
            InfoBar.warning("提示", "暂无历史成员记录", parent=self.window())
            return
        
        # 创建成员选择对话框
        dialog = HistoryMemberDialog(members, self.theme_manager, self.window())
        if dialog.exec():
            selected_member = dialog.selected_member
            if selected_member:
                # 填充成员信息到表单
                member_fields['name'].setText(selected_member.name)
                member_fields['gender'].setText(selected_member.gender)
                member_fields['id_card'].setText(selected_member.id_card)
                member_fields['phone'].setText(selected_member.phone)
                member_fields['student_id'].setText(selected_member.student_id)
                member_fields['email'].setText(selected_member.email)
                member_fields['major'].setText(selected_member.major)
                member_fields['class_name'].setText(selected_member.class_name)
                member_fields['college'].setText(selected_member.college)
                InfoBar.success("成功", f"已选择成员: {selected_member.name}", parent=self.window())

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
        """选择附件文件并添加到表格"""
        files, _ = QFileDialog.getOpenFileNames(self, "选择附件")
        if not files:
            return
        
        # 添加到已选文件列表
        for file_path in files:
            path = Path(file_path)
            if path not in self.selected_files:
                self.selected_files.append(path)
        
        # 更新表格显示
        self._update_attachment_table()
    
    def _update_attachment_table(self) -> None:
        """更新附件表格显示"""
        self.attach_table.setRowCount(len(self.selected_files))
        
        for row, file_path in enumerate(self.selected_files):
            # 序号
            item0 = QTableWidgetItem(str(row + 1))
            item0.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.attach_table.setItem(row, 0, item0)
            
            # 文件名
            item1 = QTableWidgetItem(file_path.name)
            item1.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.attach_table.setItem(row, 1, item1)
            
            # MD5
            md5_hash = self._calculate_md5(file_path)
            item2 = QTableWidgetItem(md5_hash[:16] + "...")  # 显示前16位
            item2.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.attach_table.setItem(row, 2, item2)
            
            # 大小
            size_str = self._format_file_size(file_path.stat().st_size)
            item3 = QTableWidgetItem(size_str)
            item3.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.attach_table.setItem(row, 3, item3)
            
            # 删除按钮
            delete_btn = TransparentToolButton(FluentIcon.DELETE)
            delete_btn.setToolTip("删除")
            delete_btn.clicked.connect(lambda checked, r=row: self._remove_attachment(r))
            
            # 创建容器居中按钮
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(4, 0, 4, 0)
            btn_layout.addWidget(delete_btn)
            btn_layout.setAlignment(Qt.AlignCenter)
            self.attach_table.setCellWidget(row, 4, btn_widget)
    
    def _calculate_md5(self, file_path: Path) -> str:
        """计算文件MD5值"""
        try:
            md5_hash = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    md5_hash.update(chunk)
            return md5_hash.hexdigest()
        except Exception:
            return "无法计算"
    
    def _format_file_size(self, size: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def _remove_attachment(self, row: int) -> None:
        """删除指定行的附件"""
        if 0 <= row < len(self.selected_files):
            self.selected_files.pop(row)
            self._update_attachment_table()

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
        # ✅ 优化：快速失败机制 - 第一个错误立即返回
        issues = self._validate_form()
        if issues:
            # 只显示第一个错误（快速反馈）
            InfoBar.warning("表单不合法", issues[0], parent=self.window())
            return
        
        # 数据已验证，可以直接获取
        members_data = self._get_members_data()
        
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
            
            InfoBar.success("成功", f"已更新：{award.competition_name}", parent=self.window())
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
                attachment_files=self.selected_files,
            )
            InfoBar.success("成功", f"已保存：{award.competition_name}", parent=self.window())
        
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
        ✅ 优化：提前退出机制 + 快速失败检测
        """
        issues: list[str] = []
        
        # 1️⃣ 验证比赛名称（必填）
        name = self.name_input.text().strip()
        valid, msg = FormValidator.validate_competition_name(name)
        if not valid:
            issues.append(msg)
            self._highlight_field_error(self.name_input)
            return issues  # ✅ 快速失败：基本信息错误立即返回
        
        # 2️⃣ 验证获奖日期（必填）
        try:
            award_date = QDate(self.year_input.value(), self.month_input.value(), self.day_input.value())
            if not award_date.isValid():
                issues.append("获奖日期不合法。")
                return issues
            elif award_date > QDate.currentDate():
                issues.append("获奖日期不能晚于今天。")
                return issues
        except Exception:
            issues.append("获奖日期不合法。")
            return issues
        
        # 3️⃣ 验证证书号和备注（可选，轻量检查）
        code = self.certificate_input.text().strip()
        valid, msg = FormValidator.validate_certificate_code(code)
        if not valid:
            issues.append(msg)
            self._highlight_field_error(self.certificate_input)
            return issues
        
        remarks = self.remarks_input.text().strip()
        valid, msg = FormValidator.validate_remarks(remarks)
        if not valid:
            issues.append(msg)
            self._highlight_field_error(self.remarks_input)
            return issues
        
        # 4️⃣ 验证成员（最后验证，因为最复杂）
        members_data = self._get_members_data()
        if not members_data:
            issues.append("请至少添加一名成员。")
            return issues  # ✅ 快速失败
        
        # 批量验证成员，但在第一个错误时停止
        for i, member in enumerate(members_data, 1):
            member_errors = FormValidator.validate_member_info(member)
            if member_errors:  # ✅ 找到错误立即返回
                issues.append(f"成员 {i} - {member_errors[0]}")
                # 高亮错误的成员卡片
                if i - 1 < len(self.members_data):
                    self._highlight_member_error(i - 1)
                return issues
        
        return issues
    
    def _highlight_field_error(self, field_widget: QLineEdit) -> None:
        """高亮出错的字段 - 快速反馈"""
        field_widget.setStyleSheet("""
            QLineEdit {
                border: 2px solid #ff6b6b;
                border-radius: 4px;
                padding: 4px;
                background-color: rgba(255, 107, 107, 0.1);
            }
        """)
        # 3 秒后移除高亮
        from PySide6.QtCore import QTimer
        QTimer.singleShot(3000, lambda: field_widget.setStyleSheet(""))
    
    def _highlight_member_error(self, member_index: int) -> None:
        """高亮出错的成员卡片"""
        if 0 <= member_index < len(self.members_data):
            member_card = self.members_data[member_index]['card']
            member_card.setStyleSheet("""
                QFrame {
                    border: 2px solid #ff6b6b;
                    border-radius: 8px;
                }
            """)
            # 3 秒后移除高亮
            from PySide6.QtCore import QTimer
            QTimer.singleShot(3000, lambda: member_card.setStyleSheet(""))
    
    def _clear_form(self) -> None:
        """清空表单，重置为新建状态"""
        self.editing_award = None
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
        self._update_attachment_table()
        # 清空所有成员卡片
        for member_data in self.members_data[:]:  # 使用副本遍历
            member_card = member_data['card']
            member_fields = member_data['fields']
            self._remove_member_card(member_card, member_fields)
        # 添加一个空白成员卡片
        self._add_member_card()
        from qfluentwidgets import InfoBar
        InfoBar.success("成功", "表单已清空", duration=2000, parent=self.window())
    
    def _apply_theme(self) -> None:
        """应用主题到滚动区域"""
        is_dark = self.theme_manager.is_dark
        scroll_bg = "#1c1f2e" if is_dark else "#f4f6fb"
        
        scroll_stylesheet = f"""
            QScrollArea {{
                border: none;
                background-color: {scroll_bg};
            }}
            QScrollArea > QWidget {{
                background-color: {scroll_bg};
            }}
            QWidget#scrollContent {{
                background-color: {scroll_bg};
            }}
        """
        self.scrollArea.setStyleSheet(scroll_stylesheet)
        # 确保内部容器也有正确的背景色
        scroll_widget = self.scrollArea.widget()
        if scroll_widget:
            scroll_widget.setObjectName("scrollContent")
            scroll_widget.setAutoFillBackground(True)
            palette = scroll_widget.palette()
            palette.setColor(palette.ColorRole.Window, 
                           {"#1c1f2e": QColor(28, 31, 46), "#f4f6fb": QColor(244, 246, 251)}[scroll_bg])
            scroll_widget.setPalette(palette)
    
    @Slot()
    def _on_theme_changed(self) -> None:
        """主题切换时重新应用样式"""
        # 1. 更新滚动区域背景
        self._apply_theme()
        
        # 2. 重新应用所有成员卡片的样式（包括内部组件）
        for member_data in self.members_data:
            card = member_data['card']
            self._apply_member_card_style(card)


class HistoryMemberDialog(MaskDialogBase):
    """历史成员选择对话框"""
    
    def __init__(self, members: list, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        
        self.members = members
        self.theme_manager = theme_manager
        self.selected_member = None
        self.member_widgets = []
        
        self.setWindowTitle("选择历史成员")
        self.setMinimumWidth(650)
        self.setMinimumHeight(500)
        
        # 设置主题
        from qfluentwidgets import setTheme, Theme
        if theme_manager.is_dark:
            setTheme(Theme.DARK)
        else:
            setTheme(Theme.LIGHT)
        
        self._init_ui()
        self._apply_theme()
    
    def _init_ui(self):
        """初始化UI"""
        from qfluentwidgets import LineEdit, PrimaryPushButton, PushButton
        
        # 使用 MaskDialogBase 的 widget 作为容器
        container = self.widget
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # 搜索框
        search_layout = QHBoxLayout()
        search_label = QLabel("搜索:")
        self.search_input = LineEdit()
        self.search_input.setPlaceholderText("输入姓名、学号或手机号搜索...")
        self.search_input.textChanged.connect(self._filter_members)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)
        
        # 成员列表（滚动区域）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(400)
        scroll.setMinimumWidth(600)
        
        scroll_widget = QWidget()
        self.members_layout = QVBoxLayout(scroll_widget)
        self.members_layout.setSpacing(8)
        
        # 创建成员卡片
        for member in self.members:
            member_card = self._create_member_card(member)
            self.members_layout.addWidget(member_card)
            self.member_widgets.append((member, member_card))
        
        self.members_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = PushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
    
    def _create_member_card(self, member) -> QWidget:
        """创建成员卡片"""
        card = QFrame()
        card.setObjectName("memberCard")
        card.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        # 点击选择
        def select_member():
            self.selected_member = member
            self.accept()
        
        # 使用点击事件
        from PySide6.QtCore import QEvent
        card.mousePressEvent = lambda e: select_member() if e.button() == Qt.MouseButton.LeftButton else None
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        
        # 姓名和学号（标题行）
        header = QHBoxLayout()
        name_label = QLabel(f"<b>{member.name}</b>")
        name_label.setStyleSheet("font-size: 14px;")
        student_id_label = QLabel(f"学号: {member.student_id}")
        student_id_label.setStyleSheet("color: #666; font-size: 12px;")
        header.addWidget(name_label)
        header.addStretch()
        header.addWidget(student_id_label)
        layout.addLayout(header)
        
        # 详细信息
        info_layout = QGridLayout()
        info_layout.setSpacing(8)
        
        info_data = [
            ("性别", member.gender),
            ("手机", member.phone),
            ("学院", member.college),
            ("专业", member.major),
            ("班级", member.class_name),
            ("邮箱", member.email),
        ]
        
        for idx, (label, value) in enumerate(info_data):
            row = idx // 2
            col = (idx % 2) * 2
            
            label_widget = QLabel(f"{label}:")
            label_widget.setStyleSheet("color: #888; font-size: 11px;")
            value_widget = QLabel(value or "-")
            value_widget.setStyleSheet("font-size: 11px;")
            
            info_layout.addWidget(label_widget, row, col)
            info_layout.addWidget(value_widget, row, col + 1)
        
        layout.addLayout(info_layout)
        
        return card
    
    def _filter_members(self, text: str):
        """根据搜索文本过滤成员"""
        text = text.lower().strip()
        
        for member, card in self.member_widgets:
            if not text:
                card.show()
            else:
                # 搜索姓名、学号、手机号
                match = (
                    text in member.name.lower() or
                    text in member.student_id.lower() or
                    text in member.phone.lower()
                )
                card.setVisible(match)
    
    def _apply_theme(self):
        """应用主题样式"""
        is_dark = self.theme_manager.is_dark
        
        if is_dark:
            bg_color = "#2a2a3a"
            card_bg = "#353751"
            card_hover = "#3d3f5e"
            border_color = "#4a4a5e"
            text_color = "#e0e0e0"
        else:
            bg_color = "#f5f5f5"
            card_bg = "#ffffff"
            card_hover = "#f0f0f0"
            border_color = "#e0e0e0"
            text_color = "#333"
        
        # 设置中心 widget 的样式
        self.widget.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                color: {text_color};
            }}
            QFrame#memberCard {{
                background-color: {card_bg};
                border: 1px solid {border_color};
                border-radius: 6px;
            }}
            QFrame#memberCard:hover {{
                background-color: {card_hover};
                border: 2px solid #1890ff;
            }}
            QScrollArea {{
                border: 1px solid {border_color};
                border-radius: 4px;
                background-color: {bg_color};
            }}
        """)
        
        # 设置对话框圆角
        self.widget.setObjectName("centerWidget")
        self.widget.setStyleSheet(self.widget.styleSheet() + f"""
            QWidget#centerWidget {{
                background-color: {bg_color};
                border-radius: 12px;
            }}
        """)
