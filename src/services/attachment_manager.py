from __future__ import annotations

import contextlib
import hashlib
import logging
import shutil
from collections.abc import Iterable, Sequence
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import ATTACHMENTS_DIR
from ..data.database import Database
from ..data.models import Attachment
from .settings_service import SettingsService

logger = logging.getLogger(__name__)


class AttachmentManager:
    def __init__(self, db: Database, settings: SettingsService):
        self.db = db
        self.settings = settings

    @property
    def root(self) -> Path:
        return Path(self.settings.get("attachment_root", str(ATTACHMENTS_DIR)))

    def ensure_root(self) -> Path:
        root = self.root
        root.mkdir(parents=True, exist_ok=True)
        (root / ".trash").mkdir(parents=True, exist_ok=True)
        return root

    def _sanitize_name(self, name: str) -> str:
        keep = [c for c in name if c.isalnum() or c in (" ", "_", "-", ".")]
        safe = "".join(keep).strip().replace(" ", "_")
        return safe or "attachment"

    def _calculate_md5(self, file_path: Path) -> str:
        """计算文件的MD5哈希值"""
        md5_hash = hashlib.md5()
        with file_path.open("rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()

    def _ensure_unique_path(self, folder: Path, filename: str) -> Path:
        dest = folder / filename
        counter = 1
        while dest.exists():
            stem = dest.stem
            suffix = dest.suffix
            dest = folder / f"{stem}_{counter}{suffix}"
            counter += 1
        return dest

    def save_attachments(
        self,
        award_id: int,
        competition_name: str,
        file_paths: Sequence[Path],
        session: Session | None = None,
    ) -> list[Attachment]:
        saved: list[Attachment] = []
        root = self.ensure_root()
        folder = root / f"award_{award_id}"
        folder.mkdir(parents=True, exist_ok=True)

        context = self.db.session_scope() if session is None else contextlib.nullcontext(session)
        with context as active_session:
            for index, src in enumerate(file_paths, start=1):
                if not src.exists():
                    logger.warning("Attachment %s not found, skipped", src)
                    continue

                # 计算MD5和文件大小
                file_md5 = self._calculate_md5(src)
                file_size = src.stat().st_size

                suffix = src.suffix
                safe_name = self._sanitize_name(f"{competition_name}-附件{index:02d}{suffix}")
                dest = self._ensure_unique_path(folder, safe_name)
                shutil.copy2(src, dest)
                rel_path = dest.relative_to(root)

                attachment = Attachment(
                    award_id=award_id,
                    stored_name=safe_name,
                    original_name=src.name,
                    relative_path=str(rel_path),
                    file_md5=file_md5,
                    file_size=file_size,
                )
                active_session.add(attachment)
                saved.append(attachment)
        return saved

    def mark_deleted(self, attachment_ids: Iterable[int]) -> None:
        root = self.ensure_root()
        with self.db.session_scope() as session:
            attachments = session.scalars(select(Attachment).where(Attachment.id.in_(list(attachment_ids)))).all()
            for attachment in attachments:
                if attachment.deleted:
                    continue
                attachment.deleted = True
                attachment.deleted_at = datetime.utcnow()
                src = root / attachment.relative_path
                trash_dir = root / ".trash" / f"award_{attachment.award_id}"
                trash_dir.mkdir(parents=True, exist_ok=True)
                dest = trash_dir / src.name
                if src.exists():
                    shutil.move(src, dest)
                    attachment.relative_path = str(dest.relative_to(root))

    def restore(self, attachment_ids: Iterable[int]) -> None:
        root = self.ensure_root()
        with self.db.session_scope() as session:
            attachments = session.scalars(select(Attachment).where(Attachment.id.in_(list(attachment_ids)))).all()
            for attachment in attachments:
                if not attachment.deleted:
                    continue
                trash_path = root / attachment.relative_path
                original_dir = root / f"award_{attachment.award_id}"
                original_dir.mkdir(parents=True, exist_ok=True)
                dest = original_dir / trash_path.name
                if trash_path.exists():
                    shutil.move(trash_path, dest)
                    attachment.relative_path = str(dest.relative_to(root))
                attachment.deleted = False
                attachment.deleted_at = None

    def purge_deleted(self, ids: Iterable[int] | None = None) -> int:
        root = self.ensure_root()
        removed = 0
        with self.db.session_scope() as session:
            stmt = select(Attachment).where(Attachment.deleted.is_(True))
            if ids:
                stmt = stmt.where(Attachment.id.in_(list(ids)))
            attachments = session.scalars(stmt).all()
            for attachment in attachments:
                file_path = root / attachment.relative_path
                if file_path.exists():
                    file_path.unlink()
                session.delete(attachment)
                removed += 1
        return removed

    def list_deleted(self) -> list[Attachment]:
        with self.db.session_scope() as session:
            deleted = (
                session.scalars(select(Attachment).where(Attachment.deleted.is_(True)).order_by(Attachment.deleted_at))
                .unique()
                .all()
            )
            return list(deleted)
