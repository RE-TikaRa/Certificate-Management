import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

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


def configure_logging(debug_enabled: bool = False) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if debug_enabled else logging.INFO)
    root_logger.handlers.clear()

    app_handler = _build_handler("app.log", logging.INFO)
    error_handler = _build_handler("error.log", logging.ERROR)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if debug_enabled else logging.INFO)
    console_handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))

    root_logger.addHandler(app_handler)
    root_logger.addHandler(error_handler)
    root_logger.addHandler(console_handler)

    if debug_enabled:
        debug_handler = _build_handler("debug.log", logging.DEBUG)
        root_logger.addHandler(debug_handler)
