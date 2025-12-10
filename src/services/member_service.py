from sqlalchemy import or_, select

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

    def get_member(self, member_id: int) -> TeamMember | None:
        """获取单个成员"""
        with self.db.session_scope() as session:
            stmt = select(TeamMember).where(TeamMember.id == member_id)
            return session.execute(stmt).scalar_one_or_none()

    def search_members(self, query: str, limit: int = 50) -> list[TeamMember]:
        """FTS 优先的成员搜索"""
        if not query:
            return self.list_members()

        fts_ids = self.db.search_members_fts(query, limit)
        with self.db.session_scope() as session:
            stmt = select(TeamMember)
            if fts_ids:
                stmt = stmt.where(TeamMember.id.in_(fts_ids))
            else:
                pattern = f"%{query}%"
                stmt = stmt.where(
                    or_(
                        TeamMember.name.like(pattern),
                        TeamMember.pinyin.like(pattern.lower()),
                        TeamMember.student_id.like(pattern),
                        TeamMember.phone.like(pattern),
                        TeamMember.email.like(pattern),
                        TeamMember.college.like(pattern),
                        TeamMember.major.like(pattern),
                    )
                )
            stmt = stmt.limit(limit)
            results = list(session.scalars(stmt).all())
            if fts_ids:
                order = {mid: idx for idx, mid in enumerate(fts_ids)}
                results.sort(key=lambda m: order.get(m.id, len(order)))
            return results

    def update_member(self, member: TeamMember) -> TeamMember:
        """更新成员信息"""
        with self.db.session_scope() as session:
            # 合并到 session
            merged = session.merge(member)
            session.add(merged)
            session.flush()
            self.db.upsert_member_fts(
                merged.id,
                name=merged.name,
                pinyin=merged.pinyin,
                student_id=merged.student_id,
                phone=merged.phone,
                email=merged.email,
                college=merged.college,
                major=merged.major,
            )
            return merged

    def delete_member(self, member_id: int) -> None:
        """删除成员"""
        with self.db.session_scope() as session:
            member = session.query(TeamMember).filter(TeamMember.id == member_id).first()
            if member:
                session.delete(member)
                session.flush()
                self.db.delete_member_fts(member_id)

    def delete_members(self, member_ids: list[int]) -> int:
        """批量删除成员"""
        with self.db.session_scope() as session:
            stmt = select(TeamMember).where(TeamMember.id.in_(member_ids))
            members = session.execute(stmt).scalars().all()
            count = len(members)
            for member in members:
                session.delete(member)
            session.flush()
            return count

    def list_members(self) -> list[TeamMember]:
        """列出所有成员"""
        with self.db.session_scope() as session:
            stmt = select(TeamMember).order_by(TeamMember.id.desc())
            return list(session.execute(stmt).scalars().all())
