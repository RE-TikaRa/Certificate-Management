"""
专业管理服务
提供专业名称的搜索、匹配和管理功能
"""

from typing import Any

from pypinyin import lazy_pinyin
from sqlalchemy import and_, func, or_, select

from src.data.database import Database
from src.data.models import Major, TeamMember


class MajorService:
    """专业管理服务"""

    def __init__(self, db: Database):
        self.db = db

    def get_all_majors(self) -> list[Major]:
        """获取所有专业"""
        with self.db.session_scope() as session:
            majors = session.query(Major).order_by(Major.name).all()
            return [Major(id=m.id, name=m.name, pinyin=m.pinyin, category=m.category) for m in majors]

    def search_majors(self, query: str, limit: int = 10) -> list[Major]:
        """
        模糊搜索专业名称

        Args:
            query: 搜索关键词
            limit: 返回结果数量限制

        Returns:
            匹配的专业列表
        """
        if not query:
            return []

        query = query.strip()

        with self.db.session_scope() as session:
            # 搜索：专业名称包含关键词 或 拼音包含关键词
            conditions = [Major.name.like(f"%{query}%")]
            if query.isalpha():
                conditions.append(Major.pinyin.like(f"%{query}%"))

            majors = session.query(Major).filter(or_(*conditions)).limit(limit).all()

            return [Major(id=m.id, name=m.name, pinyin=m.pinyin, category=m.category) for m in majors]

    def add_major(self, name: str, category: str | None = None) -> Major:
        """
        添加新专业

        Args:
            name: 专业名称
            category: 分类

        Returns:
            创建的专业对象
        """
        # 生成拼音
        pinyin = "".join(lazy_pinyin(name))

        with self.db.session_scope() as session:
            major = Major(name=name, pinyin=pinyin, category=category)
            session.add(major)
            session.flush()

            return Major(id=major.id, name=major.name, pinyin=major.pinyin, category=major.category)

    def major_exists(self, name: str) -> bool:
        """检查专业是否存在"""
        with self.db.session_scope() as session:
            return session.query(Major).filter(Major.name == name).count() > 0

    def batch_add_majors(self, major_names: list[str]) -> int:
        """
        批量添加专业

        Args:
            major_names: 专业名称列表

        Returns:
            成功添加的数量
        """
        count = 0
        with self.db.session_scope() as session:
            for name in major_names:
                # 检查是否已存在
                exists = session.query(Major).filter(Major.name == name).count() > 0
                if not exists:
                    pinyin = "".join(lazy_pinyin(name))
                    major = Major(name=name, pinyin=pinyin)
                    session.add(major)
                    count += 1

        return count

    def clear_all_majors(self) -> int:
        """
        清空所有专业数据

        Returns:
            删除的数量
        """
        with self.db.session_scope() as session:
            count = session.query(Major).count()
            session.query(Major).delete()
            return count

    def replace_all_majors(self, major_names: list[str]) -> int:
        """
        清空并重新导入所有专业

        Args:
            major_names: 专业名称列表

        Returns:
            导入的数量
        """
        with self.db.session_scope() as session:
            # 清空现有数据
            session.query(Major).delete()

            # 导入新数据
            for name in major_names:
                pinyin = "".join(lazy_pinyin(name))
                major = Major(name=name, pinyin=pinyin)
                session.add(major)

        return len(major_names)

    def get_statistics(self) -> dict[str, float | int | list[tuple[str, int]]]:
        """统计专业库与成员专业的使用情况"""
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
                select(clean_major.label("major"), func.count(TeamMember.id).label("count"))
                .where(valid_condition)
                .group_by(clean_major)
                .order_by(func.count(TeamMember.id).desc())
                .limit(5)
            ).all()
            top_majors: list[tuple[str, int]] = []
            for row in top_rows:
                major_name: Any = row.major
                count_value: Any = row.count
                if major_name:
                    top_majors.append((str(major_name), int(count_value or 0)))

        return {
            "library_total": library_total,
            "member_records_with_major": member_records_with_major,
            "member_major_count": member_major_count,
            "covered_major_count": covered_major_count,
            "unmatched_major_count": unmatched_major_count,
            "coverage_percent": coverage_percent,
            "top_majors": top_majors,
        }
