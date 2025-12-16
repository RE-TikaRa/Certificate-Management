from enum import Enum
from typing import Self, cast

from PySide6.QtCore import QCoreApplication, QObject, Signal
from PySide6.QtGui import QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication
from qfluentwidgets import Theme, setTheme
from qfluentwidgets.common.config import qconfig

from ..config import BASE_DIR

STYLE_DIR = BASE_DIR / "src" / "resources" / "styles"


class ThemeMode(Enum):
    """Theme mode: light, dark, or auto (follow system)"""

    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"


def _is_system_dark() -> bool:
    """Check if the system is using dark mode."""
    palette = QGuiApplication.palette()
    window_color = palette.color(QPalette.ColorRole.Window)
    # If background is dark (luminance < 128), it's dark mode
    luminance = (window_color.red() * 299 + window_color.green() * 587 + window_color.blue() * 114) / 1000
    return luminance < 128


def _load_qss(is_dark: bool) -> str:
    """Load qss file based on actual theme (dark or light)."""
    filename = "styled_dark.qss" if is_dark else "styled_light.qss"
    target = STYLE_DIR / filename
    if not target.exists():
        return ""
    return target.read_text(encoding="utf-8")


class ThemeManager(QObject):
    """Theme manager supporting light, dark, and auto modes"""

    themeChanged = Signal()  # 主题变化信号
    _instance = None

    def __init__(self, app: QApplication | QCoreApplication | None):
        super().__init__()
        if app is None:
            raise RuntimeError("QApplication instance is required to manage theme.")
        self.app = cast(QApplication, app)
        self._mode = ThemeMode.LIGHT
        self._is_dark = False

    @classmethod
    def instance(cls) -> Self:
        """Get singleton instance"""
        if cls._instance is None:
            from PySide6.QtWidgets import QApplication

            cls._instance = cls(QApplication.instance())
        return cls._instance

    @classmethod
    def set_instance(cls, instance: Self) -> None:
        """Set singleton instance"""
        cls._instance = instance

    @property
    def current_theme(self) -> str:
        """Get current theme as string: 'dark' or 'light'"""
        return "dark" if self._is_dark else "light"

    @property
    def mode(self) -> ThemeMode:
        """Get the current theme mode setting."""
        return self._mode

    @property
    def is_dark(self) -> bool:
        """Get whether the current actual theme is dark."""
        return self._is_dark

    def set_theme(self, mode: ThemeMode) -> None:
        """Set theme mode and update qfluentwidgets theme.
        Note: Does NOT apply stylesheets - that's handled by MainWindow.
        """
        self._mode = mode

        # Determine actual dark/light based on mode
        if mode == ThemeMode.AUTO:
            self._is_dark = _is_system_dark()
        else:
            self._is_dark = mode == ThemeMode.DARK

        # Apply qfluentwidgets theme only
        q_theme = Theme.DARK if self._is_dark else Theme.LIGHT
        setTheme(q_theme, lazy=True)
        qconfig.themeMode.value = q_theme

        # 发出主题变化信号
        self.themeChanged.emit()

    def get_window_stylesheet(self) -> str:
        """Get complete stylesheet for MainWindow including background color.
        This combines FluentWindow background override with page styles.
        """
        # Window background color
        bg_color = "#1c1f2e" if self._is_dark else "#f4f6fb"
        window_style = f"FluentWindow, AcrylicWindow {{ background-color: {bg_color}; }}\n\n"

        # Page styles from QSS file
        page_styles = _load_qss(self._is_dark)

        return window_style + page_styles

    def get_theme_from_text(self, text: str) -> ThemeMode:
        """Get ThemeMode from text."""
        text = text.lower().strip()
        for mode in ThemeMode:
            if mode.value == text:
                return mode
        return ThemeMode.LIGHT
