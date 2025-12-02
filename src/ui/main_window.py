from __future__ import annotations

from PySide6.QtGui import QColor
from qfluentwidgets import FluentIcon as FIF, FluentWindow, NavigationItemPosition, setTheme, Theme

from ..app_context import AppContext
from .pages.dashboard_page import DashboardPage
from .pages.entry_page import EntryPage
from .pages.home_page import HomePage
from .pages.management_page import ManagementPage
from .pages.recycle_page import RecyclePage
from .pages.settings_page import SettingsPage
from .styled_theme import ThemeManager


class MainWindow(FluentWindow):
    def __init__(self, ctx: AppContext, theme_manager: ThemeManager):
        # Set theme BEFORE calling super().__init__()
        q_theme = Theme.DARK if theme_manager.is_dark else Theme.LIGHT
        setTheme(q_theme)
        
        super().__init__()
        self.ctx = ctx
        self.theme_manager = theme_manager
        self.setWindowTitle("证书管理系统")
        self.setMinimumSize(1200, 800)
        
        # Apply complete stylesheet AFTER super().__init__() 
        # This overrides FluentWindow's default transparent AcrylicWindow background
        self.apply_theme_stylesheet()
        
        self._init_navigation()
    
    def apply_theme_stylesheet(self) -> None:
        """Apply complete theme stylesheet to window.
        This includes both FluentWindow background override and page styles.
        Must be called AFTER super().__init__() because FluentWindow resets styleSheet.
        """
        stylesheet = self.theme_manager.get_window_stylesheet()
        self.setStyleSheet(stylesheet)

    def _init_navigation(self) -> None:
        # 创建页面实例
        home_page = HomePage(self.ctx, self.theme_manager)
        dashboard_page = DashboardPage(self.ctx, self.theme_manager)
        entry_page = EntryPage(self.ctx, self.theme_manager)
        management_page = ManagementPage(self.ctx, self.theme_manager)
        recycle_page = RecyclePage(self.ctx, self.theme_manager)
        settings_page = SettingsPage(self.ctx, self.theme_manager)
        
        # 保存页面引用
        self.entry_page = entry_page
        self.dashboard_page = dashboard_page
        self.management_page = management_page
        
        pages = [
            ("home", home_page, FIF.HOME, "首页", NavigationItemPosition.TOP),
            ("dashboard", dashboard_page, FIF.SPEED_HIGH, "仪表盘", NavigationItemPosition.TOP),
            ("entry", entry_page, FIF.ADD, "录入", NavigationItemPosition.TOP),
            ("management", management_page, FIF.PEOPLE, "成员管理", NavigationItemPosition.TOP),
            ("recycle", recycle_page, FIF.DELETE, "附件回收站", NavigationItemPosition.TOP),
            (
                "settings",
                settings_page,
                FIF.SETTING,
                "系统设置",
                NavigationItemPosition.BOTTOM,
            ),
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
