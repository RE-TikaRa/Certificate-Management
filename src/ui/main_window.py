import logging
import time
from typing import Any, cast

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from qfluentwidgets import (
    FluentIcon as FIF,
    FluentWindow,
    NavigationItemPosition,
    Theme,
    setTheme,
)

from ..app_context import AppContext
from .pages.about_page import AboutPage
from .pages.base_page import BasePage
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

        # 连接主题变化信号以更新标题栏颜色
        self.theme_manager.themeChanged.connect(self._on_theme_changed)

        # 连接堆栈切换信号：记录即将显示的页，动画结束再刷新
        self._pending_refresh_index: int | None = None
        self.stackedWidget.currentChanged.connect(self._on_page_changed)
        # qfluentwidgets 使用 PopUpAniStackedWidget，动画结束信号为 aniFinished
        if hasattr(self.stackedWidget, "view") and hasattr(self.stackedWidget.view, "aniFinished"):
            self.stackedWidget.view.aniFinished.connect(self._on_page_animation_finished)

        # 初始化导航栏和所有页面
        self._init_navigation_fast()

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

    def _on_theme_changed(self) -> None:
        """主题变化时更新窗口样式 - 包括标题栏"""
        q_theme = Theme.DARK if self.theme_manager.is_dark else Theme.LIGHT
        setTheme(q_theme, lazy=False)
        self.apply_theme_stylesheet()

    def _on_page_changed(self, index: int) -> None:
        """记录即将显示的页索引，等待动画结束后再刷新"""
        self._pending_refresh_index = index

    def _on_page_animation_finished(self) -> None:
        """动画完成后刷新当前页面"""
        index = self._pending_refresh_index
        if index is None:
            index = self.stackedWidget.currentIndex()
        try:
            current_widget: Any = self.stackedWidget.widget(index)
            if current_widget and hasattr(current_widget, "refresh"):
                # 动画结束立即刷新，可按需再加微小延迟
                QTimer.singleShot(0, current_widget.refresh)
                logger.debug(f"Page at index {index} refreshed after animation")
        except Exception as e:
            logger.warning(f"Failed to refresh page at index {index}: {e}")
        finally:
            self._pending_refresh_index = None

    def _init_navigation_fast(self) -> None:
        """初始化导航栏"""
        # 创建所有页面
        page_start = time.time()
        self.home_page = HomePage(self.ctx, self.theme_manager)
        logger.debug(f"HomePage initialized in {time.time() - page_start:.2f}s")

        page_start = time.time()
        self.overview_page = OverviewPage(self.ctx, self.theme_manager)
        logger.debug(f"OverviewPage initialized in {time.time() - page_start:.2f}s")

        page_start = time.time()
        self.entry_page = EntryPage(self.ctx, self.theme_manager)
        logger.debug(f"EntryPage initialized in {time.time() - page_start:.2f}s")

        page_start = time.time()
        self.management_page = ManagementPage(self.ctx, self.theme_manager)
        logger.debug(f"ManagementPage initialized in {time.time() - page_start:.2f}s")

        page_start = time.time()
        self.dashboard_page = DashboardPage(self.ctx, self.theme_manager)
        logger.debug(f"DashboardPage initialized in {time.time() - page_start:.2f}s")

        page_start = time.time()
        self.recycle_page = RecyclePage(self.ctx, self.theme_manager)
        logger.debug(f"RecyclePage initialized in {time.time() - page_start:.2f}s")

        page_start = time.time()
        self.about_page = AboutPage(self.ctx, self.theme_manager)
        logger.debug(f"AboutPage initialized in {time.time() - page_start:.2f}s")

        page_start = time.time()
        self.settings_page = SettingsPage(self.ctx, self.theme_manager)
        logger.debug(f"SettingsPage initialized in {time.time() - page_start:.2f}s")

        # 注册所有导航项
        self.route_keys: dict[str, Any] = {}

        # 顶部导航
        top_pages = [
            ("home", self.home_page, FIF.HOME, "首页"),
            ("overview", self.overview_page, FIF.ALIGNMENT, "总览"),
            ("entry", self.entry_page, FIF.ADD, "录入"),
            ("management", self.management_page, FIF.PEOPLE, "成员管理"),
            ("dashboard", self.dashboard_page, FIF.SPEED_HIGH, "仪表盘"),
            ("recycle", self.recycle_page, FIF.DELETE, "附件回收站"),
        ]

        for route, widget, icon, text in top_pages:
            widget.setObjectName(route)
            key = self.addSubInterface(widget, icon, text, position=NavigationItemPosition.TOP)
            self.route_keys[route] = key

        # 底部导航
        bottom_pages = [
            ("about", self.about_page, FIF.INFO, "关于"),
            ("settings", self.settings_page, FIF.SETTING, "系统设置"),
        ]

        for route, widget, icon, text in bottom_pages:
            widget.setObjectName(route)
            key = self.addSubInterface(widget, icon, text, position=NavigationItemPosition.BOTTOM)
            self.route_keys[route] = key

        self.navigate_to("home")

    def navigate_to(self, route: str) -> None:
        """导航到指定页面"""
        if route in self.route_keys:
            self.navigationInterface.setCurrentItem(cast(Any, self.route_keys[route]))

            # 自动刷新该页面 - 获取对应的页面对象并调用 refresh()
            page_map: dict[str, BasePage | None] = {
                "home": self.home_page,
                "overview": self.overview_page,
                "entry": self.entry_page,
                "dashboard": self.dashboard_page,
                "management": self.management_page,
                "recycle": self.recycle_page,
                "settings": self.settings_page,
            }

            page = page_map.get(route)
            if page and hasattr(page, "refresh"):
                try:
                    page.refresh()
                    logger.debug(f"Page '{route}' refreshed")
                except Exception as e:
                    logger.warning(f"Failed to refresh page '{route}': {e}")
