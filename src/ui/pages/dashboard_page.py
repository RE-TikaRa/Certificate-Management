from typing import Any

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QPieSeries,
    QValueAxis,
)
from PySide6.QtCore import Qt, QTimer, QUrl, Slot
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QPainter
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import FluentIcon, IconWidget, InfoBar, ScrollArea, TableView, TransparentToolButton

from ..styled_theme import ThemeManager
from ..table_models import ObjectTableModel
from ..theme import (
    CARD_RADIUS,
    StyledCardWidget,
    apply_table_style,
    create_card,
    create_page_header,
    make_section_title,
)
from ..utils.async_utils import run_in_thread_guarded
from .base_page import BasePage


class DashboardPage(BasePage):
    def __init__(self, ctx, theme_manager: ThemeManager):
        super().__init__(ctx, theme_manager)
        self.metric_labels: dict[str, QLabel] = {}
        self._latest_awards = []
        self.setObjectName("pageRoot")

        self._cached_level_data = None
        self._cached_rank_data = None
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh)

        # 连接主题变化信号
        self.theme_manager.themeChanged.connect(self._on_theme_changed)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        title_widget = QWidget()
        title_widget.setObjectName("pageRoot")
        title_layout = QHBoxLayout(title_widget)
        title_layout.setContentsMargins(32, 24, 32, 0)
        title_layout.setSpacing(0)
        title_layout.addWidget(create_page_header("仪表盘与统计", "关键指标、趋势与分布一站式总览"))
        title_layout.addStretch()
        refresh_btn = TransparentToolButton(FluentIcon.SYNC)
        refresh_btn.setToolTip("刷新所有数据")
        refresh_btn.clicked.connect(self._refresh_all)
        title_layout.addWidget(refresh_btn)
        outer_layout.addWidget(title_widget)

        scroll = ScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer_layout.addWidget(scroll)
        self.content_widget = scroll

        container = QWidget()
        container.setObjectName("pageRoot")  # Apply background color from QSS
        scroll.setWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 28, 32, 32)
        layout.setSpacing(28)

        layout.addWidget(self._build_metric_section())
        layout.addWidget(self._build_distribution_section())
        layout.addWidget(self._build_breakdown_section())
        layout.addWidget(self._build_recent_section())
        layout.addStretch()
        self.refresh()

    def _build_metric_section(self) -> QWidget:
        card, card_layout = create_card()
        card_layout.addWidget(make_section_title("即时指标"))
        grid = QGridLayout()
        grid.setSpacing(16)
        tiles = [
            ("总荣誉数", FluentIcon.CERTIFICATE, "violet"),
            ("国家级", FluentIcon.FLAG, "gold"),
            ("省级", FluentIcon.TAG, "blue"),
            ("校级", FluentIcon.EDUCATION, "green"),
            ("一等奖", FluentIcon.ACCEPT, "cyan"),
            ("二等奖", FluentIcon.ACCEPT_MEDIUM, "purple"),
            ("三等奖", FluentIcon.CHECKBOX, "red"),
            ("优秀奖", FluentIcon.HEART, "orange"),
        ]
        for idx, (title, icon, accent) in enumerate(tiles):
            tile = self._create_metric_tile(title, icon, accent)
            row, col = divmod(idx, 4)
            grid.addWidget(tile, row, col)
        card_layout.addLayout(grid)
        return card

    def _create_metric_tile(self, title: str, icon: FluentIcon, accent: str) -> QWidget:
        frame = StyledCardWidget()
        frame.setProperty("metricTile", True)
        frame.setProperty("accent", accent)
        frame.setBorderRadius(CARD_RADIUS)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)
        icon_widget = IconWidget()
        icon_widget.setProperty("metricIcon", True)
        icon_widget.setFixedSize(24, 24)
        icon_widget.setIcon(icon)
        layout.addWidget(icon_widget)
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
        self.level_chart.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.level_chart.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.level_chart.setMinimumHeight(260)
        self.level_chart.setStyleSheet("background: transparent;")
        charts_row.addWidget(self.level_chart)

        self.rank_chart = QChartView()
        self.rank_chart.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.rank_chart.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.rank_chart.setMinimumHeight(260)
        self.rank_chart.setStyleSheet("background: transparent;")
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
        self.level_model = ObjectTableModel(["级别", "数量"], [lambda r: r[0], lambda r: r[1]], self)
        self.level_table = TableView()
        self.level_table.setModel(self.level_model)
        apply_table_style(self.level_table)
        self.level_table.setMinimumHeight(220)
        left.addWidget(self.level_table)
        stats_row.addLayout(left)

        right = QVBoxLayout()
        right.addWidget(make_section_title("等级汇总"))
        self.rank_model = ObjectTableModel(["等级", "数量"], [lambda r: r[0], lambda r: r[1]], self)
        self.rank_table = TableView()
        self.rank_table.setModel(self.rank_model)
        apply_table_style(self.rank_table)
        self.rank_table.setMinimumHeight(220)
        right.addWidget(self.rank_table)
        stats_row.addLayout(right)
        card_layout.addLayout(stats_row)
        return card

    def _build_recent_section(self) -> QWidget:
        card, card_layout = create_card()
        card_layout.addWidget(make_section_title("最近录入"))
        headers = ["比赛", "级别", "等级", "日期", "成员"]
        accessors = [
            lambda a: a.competition_name,
            lambda a: a.level,
            lambda a: a.rank,
            lambda a: str(a.award_date),
            lambda a: ", ".join(a.member_names),
        ]
        self.recent_model = ObjectTableModel(headers, accessors, self)
        self.recent_table = TableView()
        self.recent_table.setModel(self.recent_model)
        apply_table_style(self.recent_table)
        self.recent_table.setMinimumHeight(220)
        card_layout.addWidget(self.recent_table)
        return card

    def refresh(self) -> None:
        """异步刷新仪表盘数据"""

        def load_all():
            stats = self.ctx.statistics.get_overview()
            level_stats = self.ctx.statistics.get_group_by_level()
            rank_stats = self.ctx.statistics.get_group_by_rank()
            return stats, level_stats, rank_stats

        run_in_thread_guarded(load_all, self._on_data_loaded, guard=self)

    def _on_data_loaded(self, payload) -> None:
        if isinstance(payload, Exception):
            InfoBar.error("加载失败", str(payload), parent=self.window())
            return
        stats, level_stats, rank_stats = payload
        self._latest_awards = stats["latest_awards"]
        self.metric_labels["总荣誉数"].setText(str(stats["total"]))
        self.metric_labels["国家级"].setText(str(stats["national"]))
        self.metric_labels["省级"].setText(str(stats["provincial"]))
        self.metric_labels["校级"].setText(str(stats["school"]))
        self.metric_labels["一等奖"].setText(str(stats["first_prize"]))
        self.metric_labels["二等奖"].setText(str(stats["second_prize"]))
        self.metric_labels["三等奖"].setText(str(stats["third_prize"]))
        self.metric_labels["优秀奖"].setText(str(stats["excellent_prize"]))

        self.recent_model.set_objects(self._latest_awards)

        level_pairs = list(level_stats.items())
        rank_pairs = list(rank_stats.items())
        self.level_model.set_objects(level_pairs)
        self.rank_model.set_objects(rank_pairs)

        top_level = max(level_pairs, key=lambda x: x[1]) if level_pairs else ("--", 0)
        top_rank = max(rank_pairs, key=lambda x: x[1]) if rank_pairs else ("--", 0)

        self.level_chip.setText(f"最常见级别：{top_level[0]}（{top_level[1]} 项）")
        self.rank_chip.setText(f"最常见等级：{top_rank[0]}（{top_rank[1]} 项）")

        self._update_charts(level_stats, rank_stats)

    def _refresh_all(self) -> None:
        """刷新所有页面的数据 - 包括当前页面和其他已加载页面

        这个方法会：
        1. 刷新仪表板本身的数据
        2. 尝试刷新其他已加载的页面（总览、成员管理等）
        """
        # 刷新当前页面
        self.refresh()

        # 查找主窗口并刷新其他页面
        window: Any = self.window()
        for attr in ("overview_page", "entry_page", "management_page"):
            lazy_page = getattr(window, attr, None)
            loaded_page = getattr(lazy_page, "loaded_page", None)
            page = loaded_page() if callable(loaded_page) else lazy_page
            refresh = getattr(page, "refresh", None)
            if callable(refresh):
                refresh()

        # 显示刷新成功提示
        InfoBar.success(
            title="刷新成功",
            content="所有数据已更新",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            duration=2000,
            parent=self.window(),
        )

    @Slot()
    def _on_theme_changed(self) -> None:
        """主题变化时重新着色图表"""
        if self._cached_level_data and self._cached_rank_data:
            # 使用缓存的数据，只改颜色
            self._recolor_charts()
        else:
            # 首次调用，缓存还没有，执行完整更新
            level_stats = self.ctx.statistics.get_group_by_level()
            rank_stats = self.ctx.statistics.get_group_by_rank()
            self._update_charts(level_stats, rank_stats)

    def _update_charts(self, level_data: dict[str, int], rank_data: dict[str, int]) -> None:
        """更新图表数据"""

        # 检查数据是否改变
        if level_data == self._cached_level_data and rank_data == self._cached_rank_data:
            # 数据未变，只改颜色（主题切换场景）
            self._recolor_charts()
            return

        # 数据改变了，缓存新数据并重建
        self._cached_level_data = level_data
        self._cached_rank_data = rank_data

        # 获取主题颜色
        is_dark = self.theme_manager.is_dark
        text_color = QColor(255, 255, 255) if is_dark else QColor(30, 39, 70)
        grid_color = QColor(255, 255, 255, 80) if is_dark else QColor(90, 108, 243, 120)
        chart_bg_color = QColor(46, 49, 72) if is_dark else QColor(255, 255, 255)

        # 构建等级饼图
        level_series = QPieSeries()
        level_items = [(label, count) for label, count in level_data.items() if count > 0]
        if not level_items:
            level_items = [("暂无数据", 1)]
        for label, count in level_items:
            level_series.append(label, count)

        for slice in level_series.slices():
            slice.setLabelColor(text_color)

        level_chart = QChart()
        level_chart.addSeries(level_series)
        level_chart.setTitle("按级别分布")
        level_chart.setTitleBrush(QBrush(text_color))
        level_chart.legend().setLabelColor(text_color)
        level_chart.setAnimationOptions(QChart.AnimationOption.NoAnimation)
        level_chart.setBackgroundBrush(QBrush(chart_bg_color))
        self.level_chart.setChart(level_chart)

        # 构建等级柱图
        bar_series = QBarSeries()
        bar_set = QBarSet("数量")
        categories = []
        rank_items = [(label, count) for label, count in rank_data.items() if count > 0]
        if not rank_items:
            rank_items = [("暂无数据", 0)]
        for label, count in rank_items:
            bar_set.append(count)
            categories.append(label)
        bar_series.append(bar_set)

        bar_chart = QChart()
        bar_chart.addSeries(bar_series)

        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_x.setLabelsColor(text_color)
        axis_x.setGridLineColor(grid_color)

        axis_y = QValueAxis()
        axis_y.setRange(0, max((count for _, count in rank_items), default=1) or 1)
        axis_y.setLabelsColor(text_color)
        axis_y.setGridLineColor(grid_color)

        bar_chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        bar_chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        bar_series.attachAxis(axis_x)
        bar_series.attachAxis(axis_y)

        bar_chart.setTitle("按等级分布")
        bar_chart.setTitleBrush(QBrush(text_color))
        bar_chart.legend().setLabelColor(text_color)
        bar_chart.setAnimationOptions(QChart.AnimationOption.NoAnimation)
        bar_chart.setBackgroundBrush(QBrush(chart_bg_color))
        self.rank_chart.setChart(bar_chart)

    def _recolor_charts(self) -> None:
        """更新图表颜色"""
        is_dark = self.theme_manager.is_dark
        text_color = QColor(255, 255, 255) if is_dark else QColor(30, 39, 70)
        grid_color = QColor(255, 255, 255, 80) if is_dark else QColor(90, 108, 243, 120)
        chart_bg_color = QColor(46, 49, 72) if is_dark else QColor(255, 255, 255)

        # 修改等级图表颜色
        level_chart = self.level_chart.chart()
        if level_chart:
            level_chart.setTitleBrush(QBrush(text_color))
            level_chart.setBackgroundBrush(QBrush(chart_bg_color))
            level_chart.legend().setLabelColor(text_color)

            # 修改饼图切片标签颜色
            for series in level_chart.series():
                if isinstance(series, QPieSeries):
                    for slice in series.slices():
                        slice.setLabelColor(text_color)

        # 修改等级图表颜色
        rank_chart = self.rank_chart.chart()
        if rank_chart:
            rank_chart.setTitleBrush(QBrush(text_color))
            rank_chart.setBackgroundBrush(QBrush(chart_bg_color))
            rank_chart.legend().setLabelColor(text_color)

            # 修改轴颜色
            for axis in rank_chart.axes(Qt.Orientation.Horizontal):
                if hasattr(axis, "setLabelsColor"):
                    axis.setLabelsColor(text_color)
                if hasattr(axis, "setGridLineColor"):
                    axis.setGridLineColor(grid_color)

            for axis in rank_chart.axes(Qt.Orientation.Vertical):
                if hasattr(axis, "setLabelsColor"):
                    axis.setLabelsColor(text_color)
                if hasattr(axis, "setGridLineColor"):
                    axis.setGridLineColor(grid_color)

    @Slot()
    def _open_attachment_folder(self, row: int, _column: int) -> None:
        if row >= len(self._latest_awards):
            return
        award = self._latest_awards[row]
        folder = self.ctx.attachments.root / f"award_{award.id}"
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder.resolve())))

    def _navigate(self, route: str) -> None:
        window: Any = self.window()
        if hasattr(window, "navigate_to"):
            window.navigate_to(route)

    def _do_backup(self) -> None:
        path = self.ctx.backup.perform_backup()
        InfoBar.success("备份完成", str(path), duration=3000, parent=self.window())

    def showEvent(self, event) -> None:
        """页面显示时启动定时器并刷新数据"""
        super().showEvent(event)
        self.refresh()
        self.refresh_timer.start(5000)

    def closeEvent(self, event) -> None:
        """页面关闭时停止定时器"""
        self.refresh_timer.stop()
        super().closeEvent(event)

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self.refresh_timer.stop()
