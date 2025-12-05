"""
专业管理服务
提供专业名称的搜索、匹配和管理功能
"""

from typing import List
from pypinyin import lazy_pinyin
from sqlalchemy import or_
from src.data.database import Database
from src.data.models import Major


class MajorService:
    """专业管理服务"""

    def __init__(self, db: Database):
        self.db = db

    def get_all_majors(self) -> List[Major]:
        """获取所有专业"""
        with self.db.session_scope() as session:
            majors = session.query(Major).order_by(Major.name).all()
            return [Major(id=m.id, name=m.name, pinyin=m.pinyin, category=m.category) for m in majors]

    def search_majors(self, query: str, limit: int = 10) -> List[Major]:
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

    def batch_add_majors(self, major_names: List[str]) -> int:
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

    def replace_all_majors(self, major_names: List[str]) -> int:
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
