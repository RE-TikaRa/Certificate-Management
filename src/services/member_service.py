from __future__ import annotations

from sqlalchemy import select

from ..data.database import Database
from ..data.models import TeamMember


class MemberService:
    """成员管理服务"""

    def __init__(self, db: Database | None = None):
        if db is None:
            # 延迟导入以避免循环依赖
            from ..app_context import bootstrap

            ctx = bootstrap()
            db = ctx.db
        self.db = db

    def get_member(self, member_id: int) -> TeamMember:
        """获取单个成员"""
        with self.db.session_scope() as session:
            stmt = select(TeamMember).where(TeamMember.id == member_id)
            return session.execute(stmt).scalar_one_or_none()

    def update_member(self, member: TeamMember) -> TeamMember:
        """更新成员信息"""
        with self.db.session_scope() as session:
            # 合并到 session
            merged = session.merge(member)
            session.add(merged)
            session.flush()
            return merged

    def delete_member(self, member_id: int) -> None:
        """删除成员"""
        with self.db.session_scope() as session:
            member = session.query(TeamMember).filter(TeamMember.id == member_id).first()
            if member:
                session.delete(member)
                session.flush()

    def list_members(self) -> list[TeamMember]:
        """列出所有成员"""
        with self.db.session_scope() as session:
            stmt = select(TeamMember).order_by(TeamMember.id.desc())
            return session.execute(stmt).scalars().all()
