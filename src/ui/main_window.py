from __future__ import annotations

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
        """初始化导航栏和首页"""
        # 立即创建首页
        page_start = time.time()
        home_page = HomePage(self.ctx, self.theme_manager)
        logger.debug(f"HomePage initialized in {time.time() - page_start:.2f}s")

        # 保存页面引用（其他页面为None）
        self.home_page = home_page
        self.entry_page: EntryPage | None = None
        self.dashboard_page: DashboardPage | None = None
        self.management_page: ManagementPage | None = None
        self.overview_page: OverviewPage | None = None
        self.recycle_page: RecyclePage | None = None
        self.settings_page: SettingsPage | None = None

        # 只注册首页到导航栏
        self.route_keys: dict[str, Any] = {}
        key = self.addSubInterface(home_page, FIF.HOME, "首页", position=NavigationItemPosition.TOP)
        self.route_keys["home"] = key
        self.navigate_to("home")

    def _load_remaining_pages(self) -> None:
        """延迟加载其他页面"""
        QTimer.singleShot(100, self._load_fast_pages)
        QTimer.singleShot(500, self._load_normal_pages)
        QTimer.singleShot(1000, self._load_heavy_pages)

    def _load_fast_pages(self) -> None:
        """加载 Overview 和 Entry 页面"""
        page_start = time.time()
        overview_page = OverviewPage(self.ctx, self.theme_manager)
        logger.debug(f"OverviewPage initialized in {time.time() - page_start:.2f}s")

        page_start = time.time()
        entry_page = EntryPage(self.ctx, self.theme_manager)
        logger.debug(f"EntryPage initialized in {time.time() - page_start:.2f}s")

        # 保存页面引用
        self.entry_page = entry_page
        self.overview_page = overview_page

        # 添加页面到导航栏
        pages = [
            (
                "overview",
                overview_page,
                FIF.ALIGNMENT,
                "总览",
                NavigationItemPosition.TOP,
            ),
            ("entry", entry_page, FIF.ADD, "录入", NavigationItemPosition.TOP),
        ]

        for route, widget, icon, text, position in pages:
            widget.setObjectName(route)
            key = self.addSubInterface(widget, icon, text, position=position)
            self.route_keys[route] = key

        logger.debug("Fast pages (Overview, Entry) loaded")

    def _load_normal_pages(self) -> None:
        """加载中等页面（Management, Settings）"""
        page_start = time.time()
        management_page = ManagementPage(self.ctx, self.theme_manager)
        logger.debug(f"ManagementPage initialized in {time.time() - page_start:.2f}s")

        page_start = time.time()
        about_page = AboutPage(self.ctx, self.theme_manager)
        logger.debug(f"AboutPage initialized in {time.time() - page_start:.2f}s")

        page_start = time.time()
        settings_page = SettingsPage(self.ctx, self.theme_manager)
        logger.debug(f"SettingsPage initialized in {time.time() - page_start:.2f}s")

        # 保存页面引用
        self.management_page = management_page
        self.about_page = about_page
        self.settings_page = settings_page

        # 添加页面到导航栏
        pages = [
            (
                "management",
                management_page,
                FIF.PEOPLE,
                "成员管理",
                NavigationItemPosition.TOP,
            ),
            ("about", about_page, FIF.INFO, "关于", NavigationItemPosition.BOTTOM),
            (
                "settings",
                settings_page,
                FIF.SETTING,
                "系统设置",
                NavigationItemPosition.BOTTOM,
            ),
        ]

        for route, widget, icon, text, position in pages:
            widget.setObjectName(route)
            key = self.addSubInterface(widget, icon, text, position=position)
            self.route_keys[route] = key

        logger.debug("Normal pages (Management, About, Settings) loaded")

    def _load_heavy_pages(self) -> None:
        """加载重型页面（Dashboard, Recycle）"""
        page_start = time.time()
        dashboard_page = DashboardPage(self.ctx, self.theme_manager)
        logger.debug(f"DashboardPage initialized in {time.time() - page_start:.2f}s")

        page_start = time.time()
        recycle_page = RecyclePage(self.ctx, self.theme_manager)
        logger.debug(f"RecyclePage initialized in {time.time() - page_start:.2f}s")

        # 保存页面引用
        self.dashboard_page = dashboard_page
        self.recycle_page = recycle_page

        # 添加页面到导航栏
        pages = [
            (
                "dashboard",
                dashboard_page,
                FIF.SPEED_HIGH,
                "仪表盘",
                NavigationItemPosition.TOP,
            ),
            (
                "recycle",
                recycle_page,
                FIF.DELETE,
                "附件回收站",
                NavigationItemPosition.TOP,
            ),
        ]

        for route, widget, icon, text, position in pages:
            widget.setObjectName(route)
            key = self.addSubInterface(widget, icon, text, position=position)
            self.route_keys[route] = key

        logger.debug("Heavy pages (Dashboard, Recycle) loaded")

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
