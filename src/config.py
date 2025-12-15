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
    "theme_mode": "light",
    "backup_retention": "5",
    "email_suffix": "@st.gsau.edu.cn",  # 默认邮箱后缀
    "mcp_allow_write": "false",
    "mcp_max_bytes": "1048576",  # 1MB 默认附件读取上限
    "mcp_redact_pii": "true",
    "mcp_auto_start": "false",
    "mcp_web_auto_start": "false",
    "mcp_host": "127.0.0.1",
    "mcp_port": "8000",
    "mcp_web_host": "127.0.0.1",
    "mcp_web_port": "7860",
    "mcp_web_token": "",
    "mcp_web_username": "local",
}

for directory in (DATA_DIR, ATTACHMENTS_DIR, BACKUP_DIR, LOG_DIR, TEMPLATES_DIR):
    directory.mkdir(parents=True, exist_ok=True)
