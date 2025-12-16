"""
专业管理服务：提供全国专业目录、学校-专业映射及搜索功能。
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from pypinyin import lazy_pinyin
from sqlalchemy import and_, func, or_, select, text, tuple_

from src.data.database import Database
from src.data.models import Major, SchoolMajorMapping, TeamMember
from src.services.academic_types import MajorCatalogInput, SchoolMajorMappingInput


@dataclass(frozen=True)
class MajorSearchResult:
    name: str
    code: str | None
    college: str | None
    school_name: str | None
    school_code: str | None


class MajorService:
    """专业管理服务"""

    def __init__(self, db: Database):
        self.db = db

    def get_all_majors(self) -> list[Major]:
        """获取所有专业"""
        with self.db.session_scope() as session:
            majors = session.query(Major).order_by(Major.name).all()
            return [self._clone_major(m) for m in majors]

    def search_majors(
        self,
        query: str,
        *,
        limit: int = 10,
        school_code: str | None = None,
        school_name: str | None = None,
    ) -> list[MajorSearchResult]:
        """模糊搜索专业名称或代码"""
        if not query:
            return []
        text = query.strip()
        if not text:
            return []

        pattern = f"%{text}%"
        code_pattern = f"%{text.upper()}%"
        results: list[MajorSearchResult] = []
        seen: set[tuple[str, str | None, str | None]] = set()

        with self.db.session_scope() as session:
            if school_code or school_name:
                # 若学校代码缺失，则回退使用学校名称匹配，避免学院信息丢失
                school_filters = []
                if school_code:
                    school_filters.append(SchoolMajorMapping.school_code == school_code)
                if school_name:
                    school_filters.append(SchoolMajorMapping.school_name == school_name)
                name_filters = [
                    SchoolMajorMapping.major_name.like(pattern),
                    SchoolMajorMapping.major_code.like(code_pattern),
                ]
                stmt = (
                    select(SchoolMajorMapping)
                    .where(and_(or_(*school_filters), or_(*name_filters)))
                    .order_by(SchoolMajorMapping.major_name.asc())
                    .limit(limit)
                )
                for mapping in session.scalars(stmt):
                    key = (mapping.major_name, mapping.major_code, mapping.school_code)
                    if key in seen:
                        continue
                    seen.add(key)
                    results.append(
                        MajorSearchResult(
                            name=mapping.major_name,
                            code=mapping.major_code,
                            college=mapping.college_name,
                            school_name=mapping.school_name,
                            school_code=mapping.school_code,
                        )
                    )
                    if len(results) >= limit:
                        return results

            remaining = limit - len(results)
            if remaining <= 0:
                return results

            major_conditions = [Major.name.like(pattern)]
            major_conditions.append(Major.code.like(code_pattern))
            if text.isalpha():
                major_conditions.append(Major.pinyin.like(f"%{text.lower()}%"))
            stmt = select(Major).where(or_(*major_conditions)).order_by(Major.name.asc()).limit(remaining)
            for major in session.scalars(stmt):
                key = (major.name, major.code, None)
                if key in seen:
                    continue
                seen.add(key)
                results.append(
                    MajorSearchResult(
                        name=major.name,
                        code=major.code,
                        college=None,
                        school_name=None,
                        school_code=None,
                    )
                )
        return results

    def find_major_match(
        self,
        *,
        school_code: str | None = None,
        major_code: str | None = None,
        major_name: str | None = None,
    ) -> MajorSearchResult | None:
        """获取精确匹配的专业数据"""
        if not major_code and not major_name:
            return None
        with self.db.session_scope() as session:
            if school_code:
                query = session.query(SchoolMajorMapping).filter(SchoolMajorMapping.school_code == school_code)
                if major_code:
                    query = query.filter(SchoolMajorMapping.major_code == major_code)
                if major_name:
                    query = query.filter(SchoolMajorMapping.major_name == major_name)
                mapping = query.first()
                if mapping:
                    return MajorSearchResult(
                        name=mapping.major_name,
                        code=mapping.major_code,
                        college=mapping.college_name,
                        school_name=mapping.school_name,
                        school_code=mapping.school_code,
                    )

            query = session.query(Major)
            if major_code:
                query = query.filter(Major.code == major_code)
            elif major_name:
                query = query.filter(Major.name == major_name)
            else:
                return None
            major = query.first()
            if major:
                return MajorSearchResult(
                    name=major.name,
                    code=major.code,
                    college=None,
                    school_name=None,
                    school_code=None,
                )
        return None

    def add_major(
        self,
        name: str,
        category: str | None = None,
        *,
        code: str | None = None,
        discipline_code: str | None = None,
        discipline_name: str | None = None,
        class_code: str | None = None,
        class_name: str | None = None,
    ) -> Major:
        """添加新专业"""
        data = MajorCatalogInput(
            major_name=name,
            major_code=code,
            discipline_code=discipline_code,
            discipline_name=discipline_name,
            class_code=class_code,
            class_name=class_name,
            category=category,
        )
        normalized = self._normalize_catalog_input(data)
        with self.db.session_scope() as session:
            major = Major(
                name=normalized.major_name,
                code=normalized.major_code,
                pinyin=self._to_pinyin(normalized.major_name),
                category=normalized.category,
                discipline_code=normalized.discipline_code,
                discipline_name=normalized.discipline_name,
                class_code=normalized.class_code,
                class_name=normalized.class_name,
            )
            session.add(major)
            session.flush()
            return self._clone_major(major)

    def replace_all_majors(
        self,
        majors: Sequence[str | MajorCatalogInput],
        *,
        progress_callback: Callable[[int], None] | None = None,
    ) -> int:
        """清空并重新导入所有专业"""
        iterable = (self._to_catalog_input(value) for value in majors)
        return self.replace_all_majors_stream(iterable, progress_callback=progress_callback)

    def replace_all_majors_stream(
        self,
        majors: Iterable[str | MajorCatalogInput],
        *,
        batch_size: int = 400,
        progress_callback: Callable[[int], None] | None = None,
    ) -> int:
        """流式导入专业目录，支持进度回调"""
        seen_keys: set[str] = set()
        chunk: list[MajorCatalogInput] = []
        processed = 0

        def flush(session) -> None:
            nonlocal processed
            if not chunk:
                return
            for record in chunk:
                session.add(
                    Major(
                        name=record.major_name,
                        code=record.major_code,
                        pinyin=self._to_pinyin(record.major_name),
                        category=record.category,
                        discipline_code=record.discipline_code,
                        discipline_name=record.discipline_name,
                        class_code=record.class_code,
                        class_name=record.class_name,
                    )
                )
            session.flush()
            session.commit()
            processed += len(chunk)
            if progress_callback:
                progress_callback(processed)
            chunk.clear()

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
                session.query(Major).delete()
                for value in majors:
                    record = self._normalize_catalog_input(self._to_catalog_input(value))
                    key = record.major_code or record.major_name
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    chunk.append(record)
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
        return processed

    def batch_add_majors(self, major_names: list[str]) -> int:
        """批量添加专业（兼容旧接口）"""
        catalog_inputs = [MajorCatalogInput(major_name=name) for name in major_names]
        inserted = 0
        with self.db.session_scope() as session:
            existing_names = {row[0] for row in session.query(Major.name).filter(Major.name.in_(major_names)).all()}
            for record in catalog_inputs:
                norm = self._normalize_catalog_input(record)
                if norm.major_name in existing_names:
                    continue
                major = Major(
                    name=norm.major_name,
                    code=norm.major_code,
                    pinyin=self._to_pinyin(norm.major_name),
                    category=norm.category,
                    discipline_code=norm.discipline_code,
                    discipline_name=norm.discipline_name,
                    class_code=norm.class_code,
                    class_name=norm.class_name,
                )
                session.add(major)
                inserted += 1
        return inserted

    def clear_all_majors(self) -> int:
        with self.db.session_scope() as session:
            count = session.query(Major).count()
            session.query(Major).delete()
            return count

    def upsert_school_major_mappings(
        self,
        records: Iterable[SchoolMajorMappingInput],
        *,
        batch_size: int = 500,
        progress_callback: Callable[[int], None] | None = None,
    ) -> tuple[int, int]:
        """插入或更新学校-专业映射"""
        cleaned = [self._normalize_mapping_input(item) for item in records if item.school_name and item.major_name]
        if not cleaned:
            return 0, 0
        inserted = 0
        updated = 0
        processed = 0

        def emit_progress(force: bool = False) -> None:
            if progress_callback and (force or processed % batch_size == 0):
                progress_callback(processed)

        with self.db.session_scope() as session:
            code_keys = {
                (record.school_code, record.major_code)
                for record in cleaned
                if record.school_code and record.major_code
            }
            name_keys = {
                (record.school_name, record.major_name)
                for record in cleaned
                if not (record.school_code and record.major_code)
            }

            existing_by_code: dict[tuple[str | None, str | None], SchoolMajorMapping] = {}
            if code_keys:
                rows = (
                    session.query(SchoolMajorMapping)
                    .filter(tuple_(SchoolMajorMapping.school_code, SchoolMajorMapping.major_code).in_(list(code_keys)))
                    .all()
                )
                existing_by_code = {(row.school_code, row.major_code): row for row in rows}

            existing_by_name: dict[tuple[str | None, str | None], SchoolMajorMapping] = {}
            if name_keys:
                rows = (
                    session.query(SchoolMajorMapping)
                    .filter(tuple_(SchoolMajorMapping.school_name, SchoolMajorMapping.major_name).in_(list(name_keys)))
                    .all()
                )
                existing_by_name = {(row.school_name, row.major_name): row for row in rows}

            pending_flush = 0
            for record in cleaned:
                if record.school_code and record.major_code:
                    key = (record.school_code, record.major_code)
                    existing = existing_by_code.get(key)
                else:
                    key = (record.school_name, record.major_name)
                    existing = existing_by_name.get(key)

                if existing:
                    existing.school_name = record.school_name
                    existing.school_code = record.school_code
                    existing.major_name = record.major_name
                    existing.major_code = record.major_code
                    existing.college_name = record.college_name
                    existing.category = record.category
                    existing.discipline_code = record.discipline_code
                    existing.discipline_name = record.discipline_name
                    updated += 1
                else:
                    existing = SchoolMajorMapping(
                        school_name=record.school_name,
                        school_code=record.school_code,
                        major_name=record.major_name,
                        major_code=record.major_code,
                        college_name=record.college_name,
                        category=record.category,
                        discipline_code=record.discipline_code,
                        discipline_name=record.discipline_name,
                    )
                    session.add(existing)
                    pending_flush += 1
                    inserted += 1
                    if record.school_code and record.major_code:
                        existing_by_code[(record.school_code, record.major_code)] = existing
                    else:
                        existing_by_name[(record.school_name, record.major_name)] = existing

                processed += 1
                if pending_flush >= batch_size:
                    session.flush()
                    pending_flush = 0
                    emit_progress()

            session.flush()
            emit_progress(force=True)
        return inserted, updated

    def get_school_major_list(
        self,
        *,
        school_code: str | None = None,
        school_name: str | None = None,
        limit: int | None = None,
    ) -> list[SchoolMajorMapping]:
        with self.db.session_scope() as session:

            def fetch(by_code: bool) -> list[SchoolMajorMapping]:
                query = session.query(SchoolMajorMapping)
                if by_code and school_code:
                    query = query.filter(SchoolMajorMapping.school_code == school_code)
                elif school_name:
                    query = query.filter(SchoolMajorMapping.school_name == school_name)
                query = query.order_by(SchoolMajorMapping.major_name.asc())
                if limit:
                    query = query.limit(limit)
                return list(query.all())

            records = fetch(by_code=True)
            if not records and school_code and school_name:
                records = fetch(by_code=False)
            return records

    def get_statistics(self) -> dict[str, float | int | list[tuple[str, int]]]:
        """统计专业库与映射覆盖情况"""
        with self.db.session_scope() as session:
            clean_major = func.trim(TeamMember.major)
            valid_condition = and_(TeamMember.major.isnot(None), func.length(clean_major) > 0)

            library_total = session.scalar(select(func.count(Major.id))) or 0
            member_records_with_major = session.scalar(select(func.count(TeamMember.id)).where(valid_condition)) or 0
            member_major_count = (
                session.scalar(select(func.count(func.distinct(clean_major))).where(valid_condition)) or 0
            )
            covered_major_count = (
                session.scalar(
                    select(func.count(func.distinct(Major.name)))
                    .select_from(TeamMember)
                    .join(Major, clean_major == Major.name)
                    .where(valid_condition)
                )
                or 0
            )
            unmatched_major_count = max(member_major_count - covered_major_count, 0)
            coverage_percent = (covered_major_count / member_major_count * 100) if member_major_count else 0.0

            top_rows = session.execute(
                select(clean_major.label("major"), func.count(TeamMember.id).label("member_total"))
                .where(valid_condition)
                .group_by(clean_major)
                .order_by(func.count(TeamMember.id).desc())
                .limit(5)
            ).all()
            top_majors: list[tuple[str, int]] = []
            for row in top_rows:
                major_name = row.major
                count_value = getattr(row, "member_total", None)
                if major_name:
                    top_majors.append((str(major_name), int(count_value or 0)))

            mapping_total = session.scalar(select(func.count(SchoolMajorMapping.id))) or 0
            school_count = (
                session.scalar(
                    select(func.count(func.distinct(SchoolMajorMapping.school_code))).where(
                        SchoolMajorMapping.school_code.isnot(None)
                    )
                )
                or 0
            )
            college_count = (
                session.scalar(
                    select(func.count(func.distinct(SchoolMajorMapping.college_name))).where(
                        SchoolMajorMapping.college_name.isnot(None),
                        func.length(func.trim(SchoolMajorMapping.college_name)) > 0,
                    )
                )
                or 0
            )

        return {
            "library_total": library_total,
            "member_records_with_major": member_records_with_major,
            "member_major_count": member_major_count,
            "covered_major_count": covered_major_count,
            "unmatched_major_count": unmatched_major_count,
            "coverage_percent": coverage_percent,
            "top_majors": top_majors,
            "school_mapping_total": mapping_total,
            "school_count": school_count,
            "college_count": college_count,
        }

    def _clone_major(self, major: Major) -> Major:
        return Major(
            id=major.id,
            name=major.name,
            code=major.code,
            pinyin=major.pinyin,
            category=major.category,
            discipline_code=major.discipline_code,
            discipline_name=major.discipline_name,
            class_code=major.class_code,
            class_name=major.class_name,
        )

    def _to_catalog_input(self, value: str | MajorCatalogInput) -> MajorCatalogInput:
        if isinstance(value, MajorCatalogInput):
            return value
        return MajorCatalogInput(major_name=value)

    def _normalize_catalog_input(self, record: MajorCatalogInput) -> MajorCatalogInput:
        return MajorCatalogInput(
            major_name=record.major_name.strip(),
            major_code=(record.major_code or "").strip() or None,
            discipline_code=(record.discipline_code or "").strip() or None,
            discipline_name=(record.discipline_name or "").strip() or None,
            class_code=(record.class_code or "").strip() or None,
            class_name=(record.class_name or "").strip() or None,
            category=(record.category or "").strip() or None,
        )

    def _normalize_mapping_input(self, record: SchoolMajorMappingInput) -> SchoolMajorMappingInput:
        return SchoolMajorMappingInput(
            school_name=record.school_name.strip(),
            major_name=record.major_name.strip(),
            major_code=(record.major_code or "").strip() or None,
            school_code=(record.school_code or "").strip() or None,
            college_name=(record.college_name or "").strip() or None,
            category=(record.category or "").strip() or None,
            discipline_code=(record.discipline_code or "").strip() or None,
            discipline_name=(record.discipline_name or "").strip() or None,
        )

    @staticmethod
    def _to_pinyin(text: str) -> str:
        return "".join(lazy_pinyin(text)) if text else ""
