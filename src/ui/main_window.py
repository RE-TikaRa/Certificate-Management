from __future__ import annotations

from qfluentwidgets import FluentIcon as FIF, FluentWindow, NavigationItemPosition, setTheme, Theme

from ..app_context import AppContext
from .pages.dashboard_page import DashboardPage
from .pages.entry_page import EntryPage
from .pages.home_page import HomePage
from .pages.management_page import ManagementPage
from .pages.recycle_page import RecyclePage
from .pages.settings_page import SettingsPage
from .pages.statistics_page import StatisticsPage


class MainWindow(FluentWindow):
    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        theme_mode = ctx.settings.get("theme_mode", "light")
        setTheme(Theme.DARK if theme_mode == "dark" else Theme.AUTO)
        self.setWindowTitle("证书管理系统")
        self.setMinimumSize(1200, 800)
        self._init_navigation()

    def _init_navigation(self) -> None:
        pages = [
            ("home", HomePage(self.ctx), FIF.HOME, "首页", NavigationItemPosition.TOP),
            ("dashboard", DashboardPage(self.ctx), FIF.SPEED_HIGH, "仪表盘", NavigationItemPosition.TOP),
            ("entry", EntryPage(self.ctx), FIF.ADD, "录入", NavigationItemPosition.TOP),
            ("statistics", StatisticsPage(self.ctx), FIF.PIE_SINGLE, "统计", NavigationItemPosition.TOP),
            ("management", ManagementPage(self.ctx), FIF.PEOPLE, "成员与标签", NavigationItemPosition.TOP),
            ("recycle", RecyclePage(self.ctx), FIF.DELETE, "附件回收站", NavigationItemPosition.TOP),
            ("settings", SettingsPage(self.ctx), FIF.SETTING, "系统设置", NavigationItemPosition.BOTTOM),
        ]
        self.route_keys: dict[str, str] = {}
        for route, widget, icon, text, position in pages:
            widget.setObjectName(route)
            key = self.addSubInterface(widget, icon, text, position=position)
            self.route_keys[route] = key
        self.navigate("home")

    def navigate(self, route: str) -> None:
        if route in self.route_keys:
            self.navigationInterface.setCurrentItem(self.route_keys[route])
