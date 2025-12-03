from __future__ import annotations

import time
import logging
from PySide6.QtGui import QColor
from PySide6.QtCore import QTimer, QRect
from PySide6.QtWidgets import QApplication
from qfluentwidgets import FluentIcon as FIF, FluentWindow, NavigationItemPosition, setTheme, Theme

from ..app_context import AppContext
from .pages.dashboard_page import DashboardPage
from .pages.entry_page import EntryPage
from .pages.home_page import HomePage
from .pages.management_page import ManagementPage
from .pages.overview_page import OverviewPage
from .pages.recycle_page import RecyclePage
from .pages.settings_page import SettingsPage
from .styled_theme import ThemeManager

logger = logging.getLogger(__name__)


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
        
        # 将窗口设置在屏幕中心
        self._center_window()
        
        # Apply complete stylesheet AFTER super().__init__() 
        # This overrides FluentWindow's default transparent AcrylicWindow background
        self.apply_theme_stylesheet()
        
        # 快速初始化导航栏和首页
        self._init_navigation_fast()
        
        # 后台加载其他页面（不会阻塞 UI）
        QTimer.singleShot(100, self._load_remaining_pages)
    
    def _center_window(self) -> None:
        """将窗口居中显示在屏幕上"""
        screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        window_geometry = self.frameGeometry()
        center_point = screen_geometry.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())
    
    def apply_theme_stylesheet(self) -> None:
        """Apply complete theme stylesheet to window.
        This includes both FluentWindow background override and page styles.
        Must be called AFTER super().__init__() because FluentWindow resets styleSheet.
        """
        stylesheet = self.theme_manager.get_window_stylesheet()
        self.setStyleSheet(stylesheet)

    def _init_navigation_fast(self) -> None:
        """快速初始化导航栏和首页（不加载其他页面）"""
        # 立即创建首页
        page_start = time.time()
        home_page = HomePage(self.ctx, self.theme_manager)
        logger.debug(f"HomePage initialized in {time.time() - page_start:.2f}s")
        
        # 保存页面引用（其他页面为None）
        self.entry_page = None
        self.dashboard_page = None
        self.management_page = None
        self.overview_page = None
        self.recycle_page = None
        self.settings_page = None
        
        # 只注册首页到导航栏
        self.route_keys: dict[str, str] = {}
        key = self.addSubInterface(home_page, FIF.HOME, "首页", position=NavigationItemPosition.TOP)
        self.route_keys["home"] = key
        self.navigate("home")

    def _load_remaining_pages(self) -> None:
        """在后台加载其他页面"""
        # 创建页面实例
        page_start = time.time()
        dashboard_page = DashboardPage(self.ctx, self.theme_manager)
        logger.debug(f"DashboardPage initialized in {time.time() - page_start:.2f}s")
        
        page_start = time.time()
        overview_page = OverviewPage(self.ctx, self.theme_manager)
        logger.debug(f"OverviewPage initialized in {time.time() - page_start:.2f}s")
        
        page_start = time.time()
        entry_page = EntryPage(self.ctx, self.theme_manager)
        logger.debug(f"EntryPage initialized in {time.time() - page_start:.2f}s")
        
        page_start = time.time()
        management_page = ManagementPage(self.ctx, self.theme_manager)
        logger.debug(f"ManagementPage initialized in {time.time() - page_start:.2f}s")
        
        page_start = time.time()
        recycle_page = RecyclePage(self.ctx, self.theme_manager)
        logger.debug(f"RecyclePage initialized in {time.time() - page_start:.2f}s")
        
        page_start = time.time()
        settings_page = SettingsPage(self.ctx, self.theme_manager)
        logger.debug(f"SettingsPage initialized in {time.time() - page_start:.2f}s")
        
        # 保存页面引用
        self.entry_page = entry_page
        self.dashboard_page = dashboard_page
        self.management_page = management_page
        self.overview_page = overview_page
        self.recycle_page = recycle_page
        self.settings_page = settings_page
        
        # 添加页面到导航栏
        pages = [
            ("dashboard", dashboard_page, FIF.SPEED_HIGH, "仪表盘", NavigationItemPosition.TOP),
            ("overview", overview_page, FIF.ALIGNMENT, "总览", NavigationItemPosition.TOP),
            ("entry", entry_page, FIF.ADD, "录入", NavigationItemPosition.TOP),
            ("management", management_page, FIF.PEOPLE, "成员管理", NavigationItemPosition.TOP),
            ("recycle", recycle_page, FIF.DELETE, "附件回收站", NavigationItemPosition.TOP),
            ("settings", settings_page, FIF.SETTING, "系统设置", NavigationItemPosition.BOTTOM),
        ]
        
        for route, widget, icon, text, position in pages:
            widget.setObjectName(route)
            key = self.addSubInterface(widget, icon, text, position=position)
            self.route_keys[route] = key
        
        logger.debug("All pages loaded in background")


    def navigate(self, route: str) -> None:
        if route in self.route_keys:
            self.navigationInterface.setCurrentItem(self.route_keys[route])
