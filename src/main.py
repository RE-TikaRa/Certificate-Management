from __future__ import annotations

import contextlib
import logging
import signal
import sys
import time
from collections.abc import Iterator
from typing import IO

from PySide6.QtCore import QLibraryInfo, QLocale, QTimer, QTranslator
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from .app_context import bootstrap
from .mcp.helpers import safe_int
from .mcp.runtime import get_mcp_runtime

logger = logging.getLogger(__name__)


class _FilteredStream:
    def __init__(self, stream: IO[str], *, drop_substring: str) -> None:
        self._stream = stream
        self._drop = drop_substring
        self._buf = ""

    @property
    def encoding(self) -> str | None:  # pragma: no cover
        return getattr(self._stream, "encoding", None)

    def isatty(self) -> bool:  # pragma: no cover
        return bool(getattr(self._stream, "isatty", lambda: False)())

    def write(self, s: str) -> int:
        self._buf += s
        written = 0
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if self._drop not in line:
                written += self._stream.write(line + "\n")
        return written

    def flush(self) -> None:
        if self._buf and self._drop not in self._buf:
            self._stream.write(self._buf)
        self._buf = ""
        self._stream.flush()


@contextlib.contextmanager
def _filter_third_party_tips() -> Iterator[None]:
    needle = "QFluentWidgets Pro is now released"
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = _FilteredStream(old_out, drop_substring=needle)
    sys.stderr = _FilteredStream(old_err, drop_substring=needle)
    try:
        yield
    finally:
        with contextlib.suppress(Exception):
            sys.stdout.flush()
        with contextlib.suppress(Exception):
            sys.stderr.flush()
        sys.stdout, sys.stderr = old_out, old_err


def main(debug: bool = False) -> None:
    # 启动时间统计
    start_time = time.time()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
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

    try:
        ctx = bootstrap(debug=debug)
    except Exception:
        logger.exception("Bootstrap failed")
        with contextlib.suppress(Exception):
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(None, "启动失败", "启动时发生错误，详情请查看 logs/error.log")
        raise
    logger.info(f"Bootstrap completed in {time.time() - start_time:.2f}s")

    with _filter_third_party_tips():
        from .ui.main_window import MainWindow
        from .ui.styled_theme import ThemeManager

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
    app.lastWindowClosed.connect(runtime.shutdown)
    app.aboutToQuit.connect(ctx.backup.shutdown)
    app.lastWindowClosed.connect(ctx.backup.shutdown)
    if ctx.settings.get("mcp_auto_start", "false") == "true":
        max_bytes = safe_int(ctx.settings.get("mcp_max_bytes", "1048576"), 1_048_576, min_value=1024)
        host = ctx.settings.get("mcp_host", "127.0.0.1")
        port = safe_int(ctx.settings.get("mcp_port", "8000"), 8000, min_value=1, max_value=65535)
        allow_write = ctx.settings.get("mcp_allow_write", "false") == "true"
        try:
            runtime.start_mcp_sse(host=host, port=port, allow_write=allow_write, max_bytes=max_bytes)
        except Exception:
            logger.exception("Auto start MCP SSE failed")
    if ctx.settings.get("mcp_web_auto_start", "false") == "true":
        host = ctx.settings.get("mcp_web_host", "127.0.0.1")
        port = safe_int(ctx.settings.get("mcp_web_port", "7860"), 7860, min_value=1, max_value=65535)
        try:
            runtime.start_web(host=host, port=port)
        except Exception:
            logger.exception("Auto start MCP Web failed")

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
