from __future__ import annotations

from PySide6.QtCharts import QChart, QChartView, QPieSeries, QBarSeries, QBarSet, QBarCategoryAxis, QValueAxis
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from .base_page import BasePage


class StatisticsPage(BasePage):
    def __init__(self, ctx):
        super().__init__(ctx)
        layout = QVBoxLayout(self)
        self.level_chart = QChartView()
        self.rank_chart = QChartView()
        layout.addWidget(self.level_chart)
        layout.addWidget(self.rank_chart)
        self.refresh()

    def refresh(self) -> None:
        level_data = self.ctx.statistics.get_group_by_level()
        series = QPieSeries()
        for label, count in level_data.items():
            series.append(label, count)
        chart = QChart()
        chart.addSeries(series)
        chart.setTitle("按级别分布")
        self.level_chart.setChart(chart)

        rank_data = self.ctx.statistics.get_group_by_rank()
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
        self.rank_chart.setChart(bar_chart)
