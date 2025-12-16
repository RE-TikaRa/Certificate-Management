import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import ClassVar

from .config import LOG_DIR


def _build_handler(filename: str, level: int, max_bytes: int = 5 * 1024 * 1024, backup_count: int = 10):
    handler = RotatingFileHandler(
        Path(LOG_DIR) / filename,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    return handler


class _ConsoleFormatter(logging.Formatter):
    _COLORS: ClassVar[dict[str, str]] = {
        "DEBUG": "\x1b[90m",
        "INFO": "\x1b[36m",
        "WARNING": "\x1b[33m",
        "ERROR": "\x1b[31m",
        "CRITICAL": "\x1b[41m\x1b[97m",
    }
    _RESET: ClassVar[str] = "\x1b[0m"

    def __init__(self, *, debug_enabled: bool) -> None:
        super().__init__(datefmt="%H:%M:%S")
        self._debug_enabled = debug_enabled

    def format(self, record: logging.LogRecord) -> str:
        time_part = self.formatTime(record, self.datefmt)
        level = record.levelname
        msg = record.getMessage()
        if self._debug_enabled:
            msg = f"{record.name} - {msg}"

        stream = getattr(record, "_console_stream", None)
        use_color = (
            stream is not None
            and getattr(stream, "isatty", lambda: False)()
            and "NO_COLOR" not in os.environ
            and os.environ.get("TERM", "") != "dumb"
        )
        if use_color:
            color = self._COLORS.get(level, "")
            level = f"{color}{level}{self._RESET}"
        return f"{time_part} {level:<8} {msg}"


def configure_logging(debug_enabled: bool = False) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if debug_enabled else logging.INFO)
    root_logger.handlers.clear()

    app_handler = _build_handler("app.log", logging.INFO)
    error_handler = _build_handler("error.log", logging.ERROR)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if debug_enabled else logging.INFO)
    console_handler.setFormatter(_ConsoleFormatter(debug_enabled=debug_enabled))
    # 给 formatter 提供 stream 判断是否支持颜色
    console_handler.addFilter(lambda r: setattr(r, "_console_stream", console_handler.stream) or True)

    root_logger.addHandler(app_handler)
    root_logger.addHandler(error_handler)
    root_logger.addHandler(console_handler)

    if debug_enabled:
        debug_handler = _build_handler("debug.log", logging.DEBUG)
        root_logger.addHandler(debug_handler)
