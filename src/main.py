from __future__ import annotations

import sys
import time
import logging

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTranslator, QLocale, QLibraryInfo

from .app_context import bootstrap
from .ui.main_window import MainWindow
from .ui.styled_theme import ThemeManager

logger = logging.getLogger(__name__)


def main(debug: bool = False) -> None:
    # 启动时间统计
    start_time = time.time()
    
    app = QApplication(sys.argv)
    
    # 加载Qt中文翻译
    translator = QTranslator()
    translations_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if translator.load(QLocale.system(), "qtbase", "_", translations_path):
        app.installTranslator(translator)
        logger.info("Qt中文翻译加载成功")
    else:
        logger.warning("Qt中文翻译加载失败")
    
    ctx = bootstrap(debug=debug)
    logger.info(f"Bootstrap completed in {time.time() - start_time:.2f}s")
    
    theme_manager = ThemeManager(app)
    ThemeManager.set_instance(theme_manager)  # 设置单例
    
    # Load and apply saved theme
    theme_mode_text = ctx.settings.get("theme_mode", "light")
    theme_mode = theme_manager.get_theme_from_text(theme_mode_text)
    theme_manager.set_theme(theme_mode)
    
    window_start = time.time()
    window = MainWindow(ctx, theme_manager)
    logger.info(f"MainWindow initialized in {time.time() - window_start:.2f}s")
    
    window.show()
    logger.info(f"Total startup time: {time.time() - start_time:.2f}s")
    sys.exit(app.exec())


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="荣誉证书管理系统")
    parser.add_argument("-d", "--debug", action="store_true", help="启用调试模式")
    args = parser.parse_args()
    main(debug=args.debug)
