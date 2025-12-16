import logging
import signal
import sys
import time

from PySide6.QtCore import QLibraryInfo, QLocale, QTimer, QTranslator
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from .app_context import bootstrap
from .mcp.helpers import safe_int
from .mcp.runtime import get_mcp_runtime
from .ui.main_window import MainWindow
from .ui.styled_theme import ThemeManager

logger = logging.getLogger(__name__)


def main(debug: bool = False) -> None:
    # 启动时间统计
    start_time = time.time()

    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, lambda *_: app.quit())
    keep_alive_timer = QTimer(parent=app)
    keep_alive_timer.timeout.connect(lambda: None)
    keep_alive_timer.start(200)

    # 设置全局字体为含 pointSize 的字体，避免 Qt 在复制像素字体时落入 -1 警告
    default_font = QFont("Segoe UI", 12)
    app.setFont(default_font)

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

    runtime = get_mcp_runtime(ctx)
    app.aboutToQuit.connect(runtime.shutdown)
    if ctx.settings.get("mcp_auto_start", "false") == "true":
        max_bytes = safe_int(ctx.settings.get("mcp_max_bytes", "1048576"), 1_048_576, min_value=1024)
        port = safe_int(ctx.settings.get("mcp_port", "8000"), 8000, min_value=1, max_value=65535)
        allow_write = ctx.settings.get("mcp_allow_write", "false") == "true"
        runtime.start_mcp_sse(port=port, allow_write=allow_write, max_bytes=max_bytes)
    if ctx.settings.get("mcp_web_auto_start", "false") == "true":
        host = ctx.settings.get("mcp_web_host", "127.0.0.1")
        port = safe_int(ctx.settings.get("mcp_web_port", "7860"), 7860, min_value=1, max_value=65535)
        runtime.start_web(host=host, port=port)

    window.show()
    logger.info(f"Total startup time: {time.time() - start_time:.2f}s")
    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        logger.info("收到中断信号，应用已退出")
        sys.exit(0)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="荣誉证书管理系统")
    parser.add_argument("-d", "--debug", action="store_true", help="启用调试模式")
    args = parser.parse_args()
    main(debug=args.debug)
