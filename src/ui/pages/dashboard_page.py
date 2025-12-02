from __future__ import annotations

from PySide6.QtCharts import QBarCategoryAxis, QBarSeries, QBarSet, QChart, QChartView, QPieSeries, QValueAxis
from PySide6.QtCore import Qt, Slot, QUrl
from PySide6.QtGui import QDesktopServices, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)
from qfluentwidgets import InfoBar, PrimaryPushButton, PushButton

from ..theme import apply_table_style, create_card, create_page_header, make_section_title

from .base_page import BasePage


class DashboardPage(BasePage):
    def __init__(self, ctx):
        super().__init__(ctx)
        self.metric_labels: dict[str, QLabel] = {}
        self._latest_awards = []

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer_layout.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 24, 32, 32)
        layout.setSpacing(28)

        layout.addWidget(create_page_header("仪表盘与统计", "关键指标、趋势与分布一站式总览"))

        layout.addWidget(self._build_metric_section())
        layout.addWidget(self._build_distribution_section())
        layout.addWidget(self._build_breakdown_section())
        layout.addWidget(self._build_recent_section())
        layout.addWidget(self._build_action_section())
        layout.addStretch()
        self.refresh()

    def _build_metric_section(self) -> QWidget:
        card, card_layout = create_card()
        card_layout.addWidget(make_section_title("即时指标"))
        grid = QGridLayout()
        grid.setSpacing(16)
        tiles = [
            ("总荣誉数", "🗂", "violet"),
            ("国家级", "🏅", "blue"),
            ("省级", "🏆", "gold"),
            ("一等奖", "🎖", "green"),
        ]
        for idx, (title, icon, accent) in enumerate(tiles):
            tile = self._create_metric_tile(title, icon, accent)
            row, col = divmod(idx, 2)
            grid.addWidget(tile, row, col)
        card_layout.addLayout(grid)
        return card

    def _create_metric_tile(self, title: str, icon: str, accent: str) -> QWidget:
        frame = QFrame()
        frame.setProperty("metricTile", True)
        frame.setProperty("accent", accent)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)
        icon_label = QLabel(icon)
        icon_label.setAlignment(Qt.AlignLeft)
        icon_label.setStyleSheet("font-size: 24px;")
        layout.addWidget(icon_label)
        value = QLabel("0")
        value.setProperty("metricValue", True)
        layout.addWidget(value)
        caption = QLabel(title)
        caption.setProperty("metricCaption", True)
        layout.addWidget(caption)
        layout.addStretch()
        self.metric_labels[title] = value
        return frame

    def _build_distribution_section(self) -> QWidget:
        card, card_layout = create_card()
        card_layout.addWidget(make_section_title("荣誉构成与趋势"))
        charts_row = QHBoxLayout()
        charts_row.setSpacing(16)

        self.level_chart = QChartView()
        self.level_chart.setRenderHint(QPainter.Antialiasing)
        self.level_chart.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.level_chart.setMinimumHeight(260)
        charts_row.addWidget(self.level_chart)

        self.rank_chart = QChartView()
        self.rank_chart.setRenderHint(QPainter.Antialiasing)
        self.rank_chart.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.rank_chart.setMinimumHeight(260)
        charts_row.addWidget(self.rank_chart)

        card_layout.addLayout(charts_row)

        chip_row = QHBoxLayout()
        chip_row.setSpacing(12)
        self.level_chip = QLabel("最常见级别：--")
        self.level_chip.setProperty("dataChip", True)
        chip_row.addWidget(self.level_chip)
        self.rank_chip = QLabel("最常见等级：--")
        self.rank_chip.setProperty("dataChip", True)
        chip_row.addWidget(self.rank_chip)
        chip_row.addStretch()
        card_layout.addLayout(chip_row)
        return card

    def _build_breakdown_section(self) -> QWidget:
        card, card_layout = create_card()
        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)

        left = QVBoxLayout()
        left.addWidget(make_section_title("级别汇总"))
        self.level_table = QTableWidget(0, 2)
        self.level_table.setHorizontalHeaderLabels(["级别", "数量"])
        apply_table_style(self.level_table)
        self.level_table.setMinimumHeight(220)
        left.addWidget(self.level_table)
        stats_row.addLayout(left)

        right = QVBoxLayout()
        right.addWidget(make_section_title("等级汇总"))
        self.rank_table = QTableWidget(0, 2)
        self.rank_table.setHorizontalHeaderLabels(["等级", "数量"])
        apply_table_style(self.rank_table)
        self.rank_table.setMinimumHeight(220)
        right.addWidget(self.rank_table)
        stats_row.addLayout(right)
        card_layout.addLayout(stats_row)
        return card

    def _build_recent_section(self) -> QWidget:
        card, card_layout = create_card()
        card_layout.addWidget(make_section_title("最近录入"))
        self.recent_table = QTableWidget(0, 5)
        self.recent_table.setHorizontalHeaderLabels(["比赛", "级别", "等级", "日期", "成员"])
        apply_table_style(self.recent_table)
        self.recent_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.recent_table.cellDoubleClicked.connect(self._open_attachment_folder)
        self.recent_table.setMinimumHeight(220)
        card_layout.addWidget(self.recent_table)
        return card

    def _build_action_section(self) -> QWidget:
        card, card_layout = create_card(shadow=False)
        card_layout.addWidget(make_section_title("快捷操作"))
        quick_layout = QHBoxLayout()
        quick_layout.setSpacing(12)
        actions = [
            ("录入荣誉", lambda: self._navigate("entry")),
            ("成员与标签", lambda: self._navigate("management")),
            ("附件回收站", lambda: self._navigate("recycle")),
        ]
        for text, handler in actions:
            btn = PrimaryPushButton(text)
            btn.clicked.connect(handler)
            quick_layout.addWidget(btn)
        backup_btn = PushButton("立即备份")
        backup_btn.clicked.connect(self._do_backup)
        quick_layout.addWidget(backup_btn)
        quick_layout.addStretch()
        card_layout.addLayout(quick_layout)
        return card

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
        top_level = max(level_stats.items(), key=lambda x: x[1]) if level_stats else ("--", 0)
        self.level_table.setRowCount(len(level_stats))
        for row, (level, count) in enumerate(level_stats.items()):
            self.level_table.setItem(row, 0, QTableWidgetItem(level))
            self.level_table.setItem(row, 1, QTableWidgetItem(str(count)))

        rank_stats = self.ctx.statistics.get_group_by_rank()
        top_rank = max(rank_stats.items(), key=lambda x: x[1]) if rank_stats else ("--", 0)
        self.rank_table.setRowCount(len(rank_stats))
        for row, (rank, count) in enumerate(rank_stats.items()):
            self.rank_table.setItem(row, 0, QTableWidgetItem(rank))
            self.rank_table.setItem(row, 1, QTableWidgetItem(str(count)))

        self.level_chip.setText(f"最常见级别：{top_level[0]}（{top_level[1]} 项）")
        self.rank_chip.setText(f"最常见等级：{top_rank[0]}（{top_rank[1]} 项）")

        self._update_charts(level_stats, rank_stats)

    def _update_charts(self, level_data: dict[str, int], rank_data: dict[str, int]) -> None:
        level_series = QPieSeries()
        for label, count in level_data.items():
            level_series.append(label, count)
        level_chart = QChart()
        level_chart.addSeries(level_series)
        level_chart.setTitle("按级别分布")
        level_chart.setAnimationOptions(QChart.SeriesAnimations)
        level_chart.setBackgroundVisible(False)
        self.level_chart.setChart(level_chart)

        bar_series = QBarSeries()
        bar_set = QBarSet("数量")
        categories = []
        for label, count in rank_data.items():
            bar_set << count
            categories.append(label)
        bar_series.append(bar_set)
        bar_chart = QChart()
        bar_chart.addSeries(bar_series)
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_y = QValueAxis()
        axis_y.setRange(0, max(rank_data.values(), default=1))
        bar_chart.addAxis(axis_x, Qt.AlignBottom)
        bar_chart.addAxis(axis_y, Qt.AlignLeft)
        bar_series.attachAxis(axis_x)
        bar_series.attachAxis(axis_y)
        bar_chart.setTitle("按等级分布")
        bar_chart.setAnimationOptions(QChart.SeriesAnimations)
        bar_chart.setBackgroundVisible(False)
        self.rank_chart.setChart(bar_chart)

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
