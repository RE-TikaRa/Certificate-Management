"""
学校数据管理服务。
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from pypinyin import lazy_pinyin
from sqlalchemy import func, or_, select, text

from ..data.database import Database
from ..data.models import School
from .academic_types import SchoolInput


class SchoolService:
    """学校列表服务"""

    def __init__(self, db: Database):
        self.db = db

    def replace_all(
        self,
        schools: Iterable[SchoolInput],
        *,
        batch_size: int = 500,
        progress_callback: Callable[[int], None] | None = None,
    ) -> int:
        """替换学校列表"""
        cleaned = (self._normalize_input(item) for item in schools if item.name)
        deduped: dict[tuple[str, str | None], SchoolInput] = {}
        for item in cleaned:
            deduped[(item.name, item.code)] = item
        if not deduped:
            return 0

        count = 0
        chunk: list[School] = []

        def flush(session) -> None:
            nonlocal count
            if not chunk:
                return
            session.bulk_save_objects(chunk)
            session.flush()
            session.commit()
            count += len(chunk)
            chunk.clear()
            if progress_callback:
                progress_callback(count)

        with self.db.session_scope() as session:
            old_journal = None
            old_sync = None
            try:
                old_journal = session.execute(text("PRAGMA journal_mode")).scalar()
                old_sync = session.execute(text("PRAGMA synchronous")).scalar()
                session.execute(text("PRAGMA journal_mode = WAL"))
                session.execute(text("PRAGMA synchronous = OFF"))
            except Exception:
                pass

            try:
                session.query(School).delete()
                for school in deduped.values():
                    chunk.append(
                        School(
                            name=school.name,
                            code=school.code,
                            pinyin=self._to_pinyin(school.name),
                            region=school.region,
                        )
                    )
                    if len(chunk) >= batch_size:
                        flush(session)
                flush(session)
            finally:
                try:
                    if old_sync is not None:
                        session.execute(text(f"PRAGMA synchronous = {int(old_sync)}"))
                    if old_journal:
                        session.execute(text(f"PRAGMA journal_mode = {str(old_journal).upper()}"))
                except Exception:
                    pass
        return count

    def upsert(self, schools: Iterable[SchoolInput]) -> int:
        """增量更新学校列表"""
        cleaned = [self._normalize_input(item) for item in schools if item.name]
        if not cleaned:
            return 0

        inserted = 0
        with self.db.session_scope() as session:
            for data in cleaned:
                query = session.query(School).filter(School.name == data.name)
                if data.code:
                    query = query.filter(School.code == data.code)
                existing = query.first()
                if existing:
                    existing.code = data.code
                    existing.pinyin = self._to_pinyin(data.name)
                    existing.region = data.region
                else:
                    session.add(
                        School(
                            name=data.name,
                            code=data.code,
                            pinyin=self._to_pinyin(data.name),
                            region=data.region,
                        )
                    )
                    inserted += 1
        return inserted

    def search(self, query: str, limit: int = 8, *, region: str | None = None) -> list[School]:
        """模糊搜索学校"""
        if not query:
            return []
        text = query.strip()
        with self.db.session_scope() as session:
            stmt = (
                select(School)
                .where(
                    or_(
                        School.name.like(f"%{text}%"),
                        School.code.like(f"%{text}%"),
                        School.pinyin.like(f"%{text.lower()}%"),
                    )
                )
                .order_by(School.name.asc())
                .limit(limit)
            )
            if region:
                stmt = stmt.where(School.region == region)
            return list(session.scalars(stmt))

    def get_statistics(self) -> dict[str, int]:
        with self.db.session_scope() as session:
            total = session.scalar(select(func.count(School.id))) or 0
            with_code = (
                session.scalar(
                    select(func.count(School.id)).where(School.code.isnot(None), func.length(School.code) > 0)
                )
                or 0
            )
        return {"total": total, "with_code": with_code}

    def get_all(self) -> list[School]:
        with self.db.session_scope() as session:
            stmt = select(School).order_by(School.name.asc())
            return list(session.scalars(stmt))

    def get_regions(self) -> list[str]:
        with self.db.session_scope() as session:
            stmt = select(func.distinct(School.region)).where(School.region.isnot(None)).order_by(School.region.asc())
            return [str(value) for value in session.scalars(stmt) if value]

    def list_by_region(self, region: str | None) -> list[School]:
        with self.db.session_scope() as session:
            query = session.query(School)
            if region:
                query = query.filter(School.region == region)
            return list(query.order_by(School.name.asc()).all())

    def get_by_code(self, code: str) -> School | None:
        if not code:
            return None
        with self.db.session_scope() as session:
            return session.query(School).filter(School.code == code).first()

    def get_by_name(self, name: str) -> School | None:
        if not name:
            return None
        clean = name.strip()
        with self.db.session_scope() as session:
            return session.query(School).filter(School.name == clean).first()

    @staticmethod
    def _to_pinyin(text: str) -> str:
        return "".join(lazy_pinyin(text)) if text else ""

    def _normalize_input(self, value: SchoolInput) -> SchoolInput:
        return SchoolInput(
            name=value.name.strip(),
            code=(value.code or "").strip() or None,
            region=(value.region or "").strip() or None,
        )
