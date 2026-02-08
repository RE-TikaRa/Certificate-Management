from sqlalchemy import or_, select

from ..data.database import Database
from ..data.models import AwardMember, TeamMember
from .audit_logger import EntityType, OperationType, get_audit_logger
from .pinyin_utils import build_pinyin
from .settings_service import SettingsService


class MemberService:
    """成员管理服务"""

    def __init__(self, db: Database | None = None, settings: SettingsService | None = None):
        if db is None:
            # 延迟导入以避免循环依赖
            from ..app_context import bootstrap

            ctx = bootstrap()
            db = ctx.db
            settings = ctx.settings
        self.db = db
        self.settings = settings or SettingsService(db)

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
        merged_ids: list[int] = []
        with self.db.session_scope() as session:
            pattern = f"%{query}%"
            fallback_stmt = (
                select(TeamMember.id)
                .where(
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
                .limit(limit)
            )
            fallback_ids = [int(row[0]) for row in session.execute(fallback_stmt).all()]
            seen: set[int] = set()
            for member_id in [*fts_ids, *fallback_ids]:
                if member_id in seen:
                    continue
                seen.add(member_id)
                merged_ids.append(int(member_id))
                if len(merged_ids) >= max(1, limit):
                    break

            stmt = select(TeamMember)
            if merged_ids:
                stmt = stmt.where(TeamMember.id.in_(merged_ids))
            stmt = stmt.limit(limit)
            results = list(session.scalars(stmt).all())
            if merged_ids:
                order = {mid: idx for idx, mid in enumerate(merged_ids)}
                results.sort(key=lambda m: order.get(m.id, len(order)))
            return results

    def update_member(self, member: TeamMember) -> TeamMember:
        """更新成员信息"""
        award_ids: list[int] = []
        update_snapshot = self._should_update_snapshot()
        with self.db.session_scope() as session:
            # 合并到 session
            merged = session.merge(member)
            if not (merged.pinyin or "").strip():
                merged.pinyin = build_pinyin(merged.name)
            session.add(merged)
            session.flush()
            if update_snapshot:
                session.query(AwardMember).filter(AwardMember.member_id == merged.id).update(
                    {AwardMember.member_name: merged.name},
                    synchronize_session=False,
                )
                award_ids = list(
                    session.scalars(select(AwardMember.award_id).where(AwardMember.member_id == merged.id)).all()
                )
            self.db.upsert_member_fts(
                merged.id,
                name=merged.name,
                pinyin=merged.pinyin,
                student_id=merged.student_id,
                phone=merged.phone,
                email=merged.email,
                college=merged.college,
                major=merged.major,
                session=session,
            )
        self._reindex_awards(award_ids)
        audit = get_audit_logger()
        audit.log_operation(OperationType.UPDATE, EntityType.MEMBER, merged.id)
        return merged

    def delete_member(self, member_id: int) -> None:
        """删除成员"""
        award_ids: list[int] = []
        with self.db.session_scope() as session:
            award_ids = list(
                session.scalars(select(AwardMember.award_id).where(AwardMember.member_id == member_id)).all()
            )
            session.query(AwardMember).filter(AwardMember.member_id == member_id).update(
                {AwardMember.member_id: None},
                synchronize_session=False,
            )
            member = session.query(TeamMember).filter(TeamMember.id == member_id).first()
            if member:
                session.delete(member)
                session.flush()
                self.db.delete_member_fts(member_id, session=session)
        self._reindex_awards(award_ids)
        audit = get_audit_logger()
        audit.log_operation(OperationType.DELETE, EntityType.MEMBER, member_id)

    def delete_members(self, member_ids: list[int]) -> int:
        """批量删除成员"""
        award_ids: list[int] = []
        with self.db.session_scope() as session:
            award_ids = list(
                session.scalars(select(AwardMember.award_id).where(AwardMember.member_id.in_(member_ids))).all()
            )
            session.query(AwardMember).filter(AwardMember.member_id.in_(member_ids)).update(
                {AwardMember.member_id: None},
                synchronize_session=False,
            )
            stmt = select(TeamMember).where(TeamMember.id.in_(member_ids))
            members = session.execute(stmt).scalars().all()
            count = len(members)
            for member in members:
                session.delete(member)
            session.flush()
        for member_id in member_ids:
            self.db.delete_member_fts(member_id)
        self._reindex_awards(award_ids)
        audit = get_audit_logger()
        audit.log_bulk_operation(OperationType.DELETE, EntityType.MEMBER, count)
        return count

    def list_members(self) -> list[TeamMember]:
        """列出所有成员"""
        with self.db.session_scope() as session:
            stmt = select(TeamMember).order_by(TeamMember.id.desc())
            return list(session.execute(stmt).scalars().all())

    def _reindex_awards(self, award_ids: list[int]) -> None:
        if not award_ids:
            return
        self.db.refresh_awards_fts(award_ids)

    def _should_update_snapshot(self) -> bool:
        value = self.settings.get("member_snapshot_update_on_profile_change", "false")
        return value.lower() in {"1", "true", "yes", "on"}
