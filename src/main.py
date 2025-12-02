from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .app_context import bootstrap
from .ui.main_window import MainWindow
from .ui.styled_theme import ThemeManager


def main(debug: bool = False) -> None:
    app = QApplication(sys.argv)
    ctx = bootstrap(debug=debug)
    theme_manager = ThemeManager(app)
    
    # Load and apply saved theme
    theme_mode_text = ctx.settings.get("theme_mode", "light")
    theme_mode = theme_manager.get_theme_from_text(theme_mode_text)
    theme_manager.set_theme(theme_mode)
    
    window = MainWindow(ctx, theme_manager)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
