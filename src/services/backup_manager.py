from __future__ import annotations

import logging
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler

from ..config import ATTACHMENTS_DIR, BACKUP_DIR, DB_PATH, LOG_DIR
from ..data.database import Database
from ..data.models import BackupRecord
from .settings_service import SettingsService

logger = logging.getLogger(__name__)


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
