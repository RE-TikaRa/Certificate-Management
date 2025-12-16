import logging
import time
from typing import Any, cast

from PySide6.QtCore import (
    QEasingCurve,
    QTimer,
)
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QLineEdit, QPlainTextEdit, QTextEdit, QWidget
from qfluentwidgets import (
    FluentIcon as FIF,
    FluentWindow,
    NavigationItemPosition,
    Theme,
    setTheme,
)

from ..app_context import AppContext
from ..version import get_app_version
from .pages.about_page import AboutPage
from .pages.dashboard_page import DashboardPage
from .pages.entry_page import EntryPage
from .pages.home_page import HomePage
from .pages.lazy_page import LazyPage
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
        self.setWindowTitle(f"证书管理系统 v{get_app_version()}")
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

    def switchTo(self, interface: QWidget) -> None:
        """页面切换动画"""
        view = self.stackedWidget.view
        current_index = view.currentIndex()
        next_index = view.indexOf(interface)

        if current_index == next_index:
            return

        view.setCurrentWidget(
            interface,
            needPopOut=False,
            showNextWidgetDirectly=True,
            duration=400,
            easingCurve=QEasingCurve.Type.OutQuint,
        )
        if not (hasattr(self.stackedWidget, "view") and hasattr(self.stackedWidget.view, "aniFinished")):
            QTimer.singleShot(0, self._on_page_animation_finished)

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
                def _safe_refresh() -> None:
                    try:
                        current_widget.refresh()
                    except Exception as exc:
                        logger.warning("Failed to refresh page at index %s: %s", index, exc, exc_info=True)

                QTimer.singleShot(0, _safe_refresh)
                logger.debug(f"Page at index {index} refreshed after animation")
        except Exception as e:
            logger.warning(f"Failed to refresh page at index {index}: {e}")
        finally:
            self._pending_refresh_index = None

    def _init_navigation_fast(self) -> None:
        """初始化导航栏"""
        # 创建首页，其余页面延迟构建，减少启动卡顿
        page_start = time.time()
        self.home_page = HomePage(self.ctx, self.theme_manager)
        logger.debug(f"HomePage initialized in {time.time() - page_start:.2f}s")

        self.overview_page = LazyPage(lambda: OverviewPage(self.ctx, self.theme_manager))
        self.entry_page = LazyPage(lambda: EntryPage(self.ctx, self.theme_manager))
        self.management_page = LazyPage(lambda: ManagementPage(self.ctx, self.theme_manager))
        self.dashboard_page = LazyPage(lambda: DashboardPage(self.ctx, self.theme_manager))
        self.recycle_page = LazyPage(lambda: RecyclePage(self.ctx, self.theme_manager))
        self.about_page = LazyPage(lambda: AboutPage(self.ctx, self.theme_manager))
        self.settings_page = LazyPage(lambda: SettingsPage(self.ctx, self.theme_manager))

        # 注册所有导航项
        self.route_keys: dict[str, Any] = {}

        # 顶部导航
        top_pages = [
            ("home", self.home_page, FIF.HOME, "首页"),
            ("dashboard", self.dashboard_page, FIF.SPEED_HIGH, "仪表盘"),
            ("overview", self.overview_page, FIF.ALIGNMENT, "总览"),
            ("entry", self.entry_page, FIF.ADD, "录入"),
            ("management", self.management_page, FIF.PEOPLE, "成员管理"),
            ("recycle", self.recycle_page, FIF.DELETE, "回收站"),
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

        # 优化页面切换动画
        view = self.stackedWidget.view
        for ani_info in view.aniInfos:
            ani_info.deltaY = 100

        self.navigate_to("home")
        self._warm_up_lazy_pages()
        self._register_shortcuts()

    def _warm_up_lazy_pages(self) -> None:
        """启动后后台预热懒加载页面，减少首次进入的等待。"""
        pages: list[QWidget] = [
            self.dashboard_page,
            self.overview_page,
            self.entry_page,
            self.management_page,
            self.recycle_page,
            self.settings_page,
            self.about_page,
        ]

        def _load_one(index: int) -> None:
            if index >= len(pages):
                return
            page = pages[index]
            if isinstance(page, LazyPage):
                try:
                    page.load()
                except Exception as exc:
                    logger.debug("LazyPage warmup failed: %s", exc, exc_info=True)
            QTimer.singleShot(120, lambda: _load_one(index + 1))

        QTimer.singleShot(1500, lambda: _load_one(0))

    def _register_shortcuts(self) -> None:
        """绑定快捷键导航，避免在输入框时误触"""

        def can_navigate() -> bool:
            focus = QApplication.focusWidget()
            return not isinstance(focus, (QLineEdit, QTextEdit, QPlainTextEdit))

        shortcuts = [
            ("Alt+1", "home"),
            ("Alt+2", "dashboard"),
            ("Alt+3", "overview"),
            ("Alt+4", "entry"),
            ("Alt+5", "management"),
            ("Alt+6", "recycle"),
            ("Alt+7", "about"),
            ("Alt+8", "settings"),
        ]

        for seq, route in shortcuts:
            shortcut = QShortcut(QKeySequence(seq), self)
            shortcut.activated.connect(lambda r=route: self.navigate_to(r) if can_navigate() else None)

    def navigate_to(self, route: str) -> None:
        """导航到指定页面"""
        if route in self.route_keys:
            self.navigationInterface.setCurrentItem(cast(Any, self.route_keys[route]))
