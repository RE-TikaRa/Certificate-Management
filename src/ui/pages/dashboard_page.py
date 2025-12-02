from __future__ import annotations

from PySide6.QtCore import Qt, Slot, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import CardWidget, InfoBar, PrimaryPushButton

from .base_page import BasePage


class DashboardPage(BasePage):
    def __init__(self, ctx):
        super().__init__(ctx)
        self.metric_labels: dict[str, QLabel] = {}
        self._latest_awards = []

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        title = QLabel("仪表盘")
        title.setProperty("h1", True)
        layout.addWidget(title)

        metrics_widget = QWidget()
        self.metrics_grid = QGridLayout(metrics_widget)
        layout.addWidget(metrics_widget)
        self._add_metric_card(0, 0, "总荣誉数")
        self._add_metric_card(0, 1, "国家级")
        self._add_metric_card(0, 2, "省级")
        self._add_metric_card(0, 3, "一等奖")

        layout.addWidget(QLabel("最近录入"))
        self.recent_table = QTableWidget(0, 5)
        self.recent_table.setHorizontalHeaderLabels(["比赛", "级别", "等级", "日期", "成员"])
        self.recent_table.horizontalHeader().setStretchLastSection(True)
        self.recent_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.recent_table.cellDoubleClicked.connect(self._open_attachment_folder)
        layout.addWidget(self.recent_table)

        layout.addWidget(QLabel("快捷操作"))
        quick_layout = QHBoxLayout()
        for text, handler in [
            ("录入荣誉", lambda: self._navigate("entry")),
            ("统计分析", lambda: self._navigate("statistics")),
            ("成员与标签", lambda: self._navigate("management")),
            ("立即备份", self._do_backup),
        ]:
            btn = PrimaryPushButton(text)
            btn.clicked.connect(handler)
            quick_layout.addWidget(btn)
        quick_widget = QWidget()
        quick_widget.setLayout(quick_layout)
        layout.addWidget(quick_widget)

        layout.addWidget(QLabel("按级别统计"))
        self.level_table = QTableWidget(0, 2)
        self.level_table.setHorizontalHeaderLabels(["级别", "数量"])
        self.level_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.level_table)

        layout.addWidget(QLabel("按等级统计"))
        self.rank_table = QTableWidget(0, 2)
        self.rank_table.setHorizontalHeaderLabels(["等级", "数量"])
        self.rank_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.rank_table)

        layout.addStretch()
        self.refresh()

    def _add_metric_card(self, row: int, col: int, title: str) -> None:
        card = CardWidget()
        card_layout = QVBoxLayout(card)
        label = QLabel(title)
        value = QLabel("0")
        value.setProperty("h2", True)
        card_layout.addWidget(label)
        card_layout.addWidget(value)
        self.metrics_grid.addWidget(card, row, col)
        self.metric_labels[title] = value

    def refresh(self) -> None:
        stats = self.ctx.statistics.get_overview()
        self._latest_awards = stats["latest_awards"]
        self.metric_labels["总荣誉数"].setText(str(stats["total"]))
        self.metric_labels["国家级"].setText(str(stats["national"]))
        self.metric_labels["省级"].setText(str(stats["provincial"]))
        self.metric_labels["一等奖"].setText(str(stats["first_prize"]))

        self.recent_table.setRowCount(len(self._latest_awards))
        for row, award in enumerate(self._latest_awards):
            self.recent_table.setItem(row, 0, QTableWidgetItem(award.competition_name))
            self.recent_table.setItem(row, 1, QTableWidgetItem(award.level))
            self.recent_table.setItem(row, 2, QTableWidgetItem(award.rank))
            self.recent_table.setItem(row, 3, QTableWidgetItem(str(award.award_date)))
            members = ", ".join(member.name for member in award.members)
            self.recent_table.setItem(row, 4, QTableWidgetItem(members))

        level_stats = self.ctx.statistics.get_group_by_level()
        self.level_table.setRowCount(len(level_stats))
        for row, (level, count) in enumerate(level_stats.items()):
            self.level_table.setItem(row, 0, QTableWidgetItem(level))
            self.level_table.setItem(row, 1, QTableWidgetItem(str(count)))

        rank_stats = self.ctx.statistics.get_group_by_rank()
        self.rank_table.setRowCount(len(rank_stats))
        for row, (rank, count) in enumerate(rank_stats.items()):
            self.rank_table.setItem(row, 0, QTableWidgetItem(rank))
            self.rank_table.setItem(row, 1, QTableWidgetItem(str(count)))

    @Slot()
    def _open_attachment_folder(self, row: int, _column: int) -> None:
        if row >= len(self._latest_awards):
            return
        award = self._latest_awards[row]
        folder = self.ctx.attachments.root / f"award_{award.id}"
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder.resolve())))

    def _navigate(self, route: str) -> None:
        window = self.window()
        if hasattr(window, "navigate"):
            window.navigate(route)

    def _do_backup(self) -> None:
        path = self.ctx.backup.perform_backup()
        InfoBar.success("备份完成", str(path), duration=3000, parent=self)
