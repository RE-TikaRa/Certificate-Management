from __future__ import annotations

from pathlib import Path
from typing import Final

BASE_DIR: Final[Path] = Path(__file__).resolve().parent.parent
DATA_DIR: Final[Path] = BASE_DIR / "data"
ATTACHMENTS_DIR: Final[Path] = BASE_DIR / "attachments"
BACKUP_DIR: Final[Path] = BASE_DIR / "backups"
LOG_DIR: Final[Path] = BASE_DIR / "logs"
TEMPLATES_DIR: Final[Path] = BASE_DIR / "src" / "resources" / "templates"

DB_PATH: Final[Path] = DATA_DIR / "awards.db"

DEFAULT_SETTINGS: Final[dict[str, str]] = {
    "attachment_root": str(ATTACHMENTS_DIR),
    "backup_root": str(BACKUP_DIR),
    "backup_frequency": "manual",
    "include_attachments": "true",
    "include_logs": "true",
    "auto_backup_mode": "manual",
    "theme": "fluent",
    "theme_mode": "light",
}

for directory in (DATA_DIR, ATTACHMENTS_DIR, BACKUP_DIR, LOG_DIR, TEMPLATES_DIR):
    directory.mkdir(parents=True, exist_ok=True)
