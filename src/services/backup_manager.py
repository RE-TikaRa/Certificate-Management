from __future__ import annotations

import logging
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass

from apscheduler.schedulers.background import BackgroundScheduler

from ..config import ATTACHMENTS_DIR, BACKUP_DIR, DB_PATH, LOG_DIR
from ..data.database import Database
from ..data.models import BackupRecord
from .settings_service import SettingsService

logger = logging.getLogger(__name__)


@dataclass
class BackupInfo:
    """Information about a backup file."""
    path: Path
    size: int  # bytes
    created_time: datetime
    is_valid: bool = True
    error_msg: str = ""
    
    @property
    def size_mb(self) -> float:
        """Return size in megabytes."""
        return self.size / (1024 * 1024)


class BackupManager:
    def __init__(self, db: Database, settings: SettingsService):
        self.db = db
        self.settings = settings
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()

    @property
    def backup_root(self) -> Path:
        root = Path(self.settings.get("backup_root", str(BACKUP_DIR)))
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _build_archive_name(self) -> Path:
        prefix = self.settings.get("backup_prefix", "awards")
        timestamp = datetime.now().strftime("%Y%m%d-%H%M")
        return self.backup_root / f"{prefix}-backup-{timestamp}.zip"

    def perform_backup(self, include_attachments: bool | None = None, include_logs: bool | None = None) -> Path:
        include_attachments = (
            include_attachments if include_attachments is not None else self._as_bool("include_attachments")
        )
        include_logs = include_logs if include_logs is not None else self._as_bool("include_logs")

        archive_path = self._build_archive_name()
        tmp_dir = Path(tempfile.mkdtemp(prefix="backup-"))

        try:
            db_copy = tmp_dir / "data"
            db_copy.mkdir(parents=True, exist_ok=True)
            shutil.copy2(DB_PATH, db_copy / DB_PATH.name)

            if include_attachments:
                attachments_root = Path(self.settings.get("attachment_root", str(ATTACHMENTS_DIR)))
                if attachments_root.exists():
                    shutil.copytree(attachments_root, tmp_dir / "attachments", dirs_exist_ok=True)
            if include_logs and LOG_DIR.exists():
                shutil.copytree(LOG_DIR, tmp_dir / "logs", dirs_exist_ok=True)

            archive_file = Path(shutil.make_archive(str(archive_path.with_suffix("")), "zip", root_dir=tmp_dir))
            archive_path = archive_file

            with self.db.session_scope() as session:
                session.add(
                    BackupRecord(
                        path=str(archive_path),
                        include_attachments=include_attachments,
                        include_logs=include_logs,
                        status="success",
                    )
                )
            logger.info("Backup created at %s", archive_path)
            self.settings.set("last_backup_time", datetime.utcnow().isoformat())
            self._cleanup_old_archives()
            return archive_path
        except Exception as exc:  # noqa: BLE001
            logger.exception("Backup failed: %s", exc)
            with self.db.session_scope() as session:
                session.add(
                    BackupRecord(
                        path=str(archive_path),
                        include_attachments=include_attachments,
                        include_logs=include_logs,
                        status="failed",
                        message=str(exc),
                    )
                )
            raise
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def schedule_jobs(self) -> None:
        self.scheduler.remove_all_jobs()
        frequency = self.settings.get("backup_frequency", "manual")
        if frequency == "manual":
            return
        if frequency == "startup":
            self._schedule_startup_backup()
        elif frequency == "daily":
            self.scheduler.add_job(self.perform_backup, "interval", days=1, id="daily-backup")
        elif frequency == "weekly":
            self.scheduler.add_job(self.perform_backup, "interval", weeks=1, id="weekly-backup")

    def _schedule_startup_backup(self) -> None:
        last_time = self.settings.get("last_backup_time", "")
        if not last_time:
            self.perform_backup()
            return
        last_dt = datetime.fromisoformat(last_time)
        if datetime.utcnow() - last_dt > timedelta(hours=24):
            self.perform_backup()

    def _as_bool(self, key: str) -> bool:
        value = self.settings.get(key, "false")
        return value.lower() in {"1", "true", "yes", "on"}

    def _cleanup_old_archives(self) -> None:
        try:
            retention = int(self.settings.get("backup_retention", "5"))
        except ValueError:
            retention = 5
        archives = sorted(self.backup_root.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
        for extra in archives[retention:]:
            try:
                extra.unlink()
                logger.info("Removed old backup %s", extra)
            except Exception:  # noqa: BLE001
                logger.warning("Failed to remove old backup %s", extra)

    def verify_backup(self, backup_path: Path) -> tuple[bool, str]:
        """
        Verify backup file integrity by checking SQLite database within.
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            (is_valid, error_message)
        """
        if not backup_path.exists():
            return False, "备份文件不存在"
        
        if not backup_path.suffix.lower() == '.zip':
            return False, "备份文件格式不正确"
        
        try:
            import zipfile
            with zipfile.ZipFile(backup_path, 'r') as zip_ref:
                # Check if database exists in backup
                if 'data/awards.db' not in zip_ref.namelist():
                    return False, "备份中不包含数据库文件"
                
                # Verify SQLite database integrity
                with zip_ref.open('data/awards.db') as db_file:
                    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
                        tmp.write(db_file.read())
                        tmp_path = tmp.name
                
                try:
                    conn = sqlite3.connect(tmp_path)
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA integrity_check;")
                    result = cursor.fetchone()
                    conn.close()
                    
                    if result[0] != 'ok':
                        return False, f"数据库完整性检查失败: {result[0]}"
                    
                    return True, ""
                finally:
                    Path(tmp_path).unlink(missing_ok=True)
        
        except Exception as exc:
            return False, f"验证失败: {str(exc)}"

    def list_backups(self) -> list[BackupInfo]:
        """
        List all backups with their information.
        
        Returns:
            List of BackupInfo objects sorted by creation time (newest first)
        """
        backups: list[BackupInfo] = []
        
        for backup_file in sorted(self.backup_root.glob('*.zip'), reverse=True):
            try:
                stat = backup_file.stat()
                created_time = datetime.fromtimestamp(stat.st_mtime)
                
                # Quick validation
                is_valid, error_msg = self.verify_backup(backup_file)
                
                backups.append(
                    BackupInfo(
                        path=backup_file,
                        size=stat.st_size,
                        created_time=created_time,
                        is_valid=is_valid,
                        error_msg=error_msg,
                    )
                )
            except Exception as exc:
                logger.warning("Failed to read backup %s: %s", backup_file, exc)
                backups.append(
                    BackupInfo(
                        path=backup_file,
                        size=0,
                        created_time=datetime.now(),
                        is_valid=False,
                        error_msg=str(exc),
                    )
                )
        
        return backups

    def get_latest_valid_backup(self) -> BackupInfo | None:
        """
        Get the latest valid backup.
        
        Returns:
            BackupInfo of the latest valid backup, or None if no valid backups exist
        """
        for backup in self.list_backups():
            if backup.is_valid:
                return backup
        return None

