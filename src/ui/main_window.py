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
        
        # ✅ 连接主题变化信号以更新标题栏颜色
        self.theme_manager.themeChanged.connect(self._on_theme_changed)
        
        # ✅ 连接堆栈切换信号以自动刷新页面
        self.stackedWidget.currentChanged.connect(self._on_page_changed)
        
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

    def _on_theme_changed(self) -> None:
        """主题变化时更新窗口样式 - 包括标题栏"""
        q_theme = Theme.DARK if self.theme_manager.is_dark else Theme.LIGHT
        setTheme(q_theme, lazy=False)
        self.apply_theme_stylesheet()
    
    def _on_page_changed(self, index: int) -> None:
        """页面切换时自动刷新对应页面"""
        try:
            current_widget = self.stackedWidget.widget(index)
            if current_widget and hasattr(current_widget, 'refresh'):
                # 延迟刷新，确保页面完全显示
                QTimer.singleShot(50, current_widget.refresh)
                logger.debug(f"Page at index {index} will be refreshed")
        except Exception as e:
            logger.warning(f"Failed to refresh page at index {index}: {e}")

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
        """在后台加载其他页面 - 分阶段优化
        
        ✅ 优化：按优先级分三个阶段加载
        - 阶段 1（100ms）：快速页面（Overview, Entry）
        - 阶段 2（500ms）：中等页面（Management, Settings）
        - 阶段 3（1000ms）：重型页面（Dashboard, Recycle）
        """
        # 阶段 1：快速加载用户常用页面
        QTimer.singleShot(100, self._load_fast_pages)
        
        # 阶段 2：次要页面
        QTimer.singleShot(500, self._load_normal_pages)
        
        # 阶段 3：重型页面
        QTimer.singleShot(1000, self._load_heavy_pages)

    def _load_fast_pages(self) -> None:
        """加载快速页面（Overview, Entry）"""
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
            ("overview", overview_page, FIF.ALIGNMENT, "总览", NavigationItemPosition.TOP),
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
        settings_page = SettingsPage(self.ctx, self.theme_manager)
        logger.debug(f"SettingsPage initialized in {time.time() - page_start:.2f}s")
        
        # 保存页面引用
        self.management_page = management_page
        self.settings_page = settings_page
        
        # 添加页面到导航栏
        pages = [
            ("management", management_page, FIF.PEOPLE, "成员管理", NavigationItemPosition.TOP),
            ("settings", settings_page, FIF.SETTING, "系统设置", NavigationItemPosition.BOTTOM),
        ]
        
        for route, widget, icon, text, position in pages:
            widget.setObjectName(route)
            key = self.addSubInterface(widget, icon, text, position=position)
            self.route_keys[route] = key
        
        logger.debug("Normal pages (Management, Settings) loaded")

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
            ("dashboard", dashboard_page, FIF.SPEED_HIGH, "仪表盘", NavigationItemPosition.TOP),
            ("recycle", recycle_page, FIF.DELETE, "附件回收站", NavigationItemPosition.TOP),
        ]
        
        for route, widget, icon, text, position in pages:
            widget.setObjectName(route)
            key = self.addSubInterface(widget, icon, text, position=position)
            self.route_keys[route] = key
        
        logger.debug("Heavy pages (Dashboard, Recycle) loaded")


    def navigate(self, route: str) -> None:
        """导航到指定页面，并自动刷新该页面的数据
        
        ✅ 优化：点击任何页面标签时，该页面会自动刷新数据
        """
        if route in self.route_keys:
            self.navigationInterface.setCurrentItem(self.route_keys[route])
            
            # ✅ 自动刷新该页面 - 获取对应的页面对象并调用 refresh()
            page_map = {
                "home": self.home_page if hasattr(self, 'home_page') else None,
                "overview": self.overview_page,
                "entry": self.entry_page,
                "dashboard": self.dashboard_page,
                "management": self.management_page,
                "recycle": self.recycle_page,
                "settings": self.settings_page,
            }
            
            page = page_map.get(route)
            if page and hasattr(page, 'refresh'):
                try:
                    page.refresh()
                    logger.debug(f"Page '{route}' refreshed")
                except Exception as e:
                    logger.warning(f"Failed to refresh page '{route}': {e}")
