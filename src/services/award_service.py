from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import selectinload

from ..data.database import Database
from ..data.models import Award, TeamMember
from .attachment_manager import AttachmentManager


class AwardService:
    def __init__(self, db: Database, attachments: AttachmentManager):
        self.db = db
        self.attachments = attachments

    def create_award(
        self,
        *,
        competition_name: str,
        award_date: date,
        level: str,
        rank: str,
        certificate_code: str,
        remarks: str,
        member_names: Sequence[str] | Sequence[dict],
        attachment_files: Sequence[Path],
    ) -> Award:
        with self.db.session_scope() as session:
            award = Award(
                competition_name=competition_name,
                award_date=award_date,
                level=level,
                rank=rank,
                certificate_code=certificate_code,
                remarks=remarks,
            )
            # 处理成员信息（可能是字符串或字典）
            award.members = [self._get_or_create_member_with_info(session, item) for item in member_names]
            session.add(award)
            session.flush()

            if attachment_files:
                self.attachments.save_attachments(
                    award.id,
                    competition_name,
                    attachment_files,
                    session=session,
                )
            return award

    def list_members(self) -> list[TeamMember]:
        with self.db.session_scope() as session:
            # Eager load the awards relationship to avoid lazy loading errors
            members = session.scalars(
                select(TeamMember)
                .options(selectinload(TeamMember.awards))
                .order_by(TeamMember.sort_index, TeamMember.name)
            ).all()
            # Convert to dict to preserve data after session closes
            return members

    def list_tags(self) -> list[Tag]:
        with self.db.session_scope() as session:
            return session.scalars(select(Tag).order_by(Tag.sort_index, Tag.name)).all()

    def add_member(self, name: str) -> TeamMember:
        with self.db.session_scope() as session:
            member = TeamMember(name=name, pinyin=name)
            session.add(member)
            session.flush()
            return member

    def add_tag(self, name: str) -> Tag:
        with self.db.session_scope() as session:
            tag = Tag(name=name, pinyin=name)
            session.add(tag)
            session.flush()
            return tag

    def remove_member(self, name: str) -> None:
        with self.db.session_scope() as session:
            member = session.scalar(select(TeamMember).where(TeamMember.name == name))
            if member:
                session.delete(member)

    def remove_tag(self, name: str) -> None:
        with self.db.session_scope() as session:
            tag = session.scalar(select(Tag).where(Tag.name == name))
            if tag:
                session.delete(tag)

    def _get_or_create_member(self, session, name: str) -> TeamMember:
        member = session.scalar(select(TeamMember).where(TeamMember.name == name))
        if member:
            return member
        member = TeamMember(name=name, pinyin=name)
        session.add(member)
        session.flush()
        return member

    def _get_or_create_member_with_info(self, session, member_info: str | dict) -> TeamMember:
        """获取或创建成员，支持字符串（姓名）或字典（完整信息）"""
        if isinstance(member_info, str):
            # 如果是字符串，使用原来的逻辑
            return self._get_or_create_member(session, member_info)

        # 如果是字典，提取姓名并查询现有成员
        name = member_info.get("name", "")
        if not name:
            raise ValueError("成员信息必须包含 'name' 字段")

        member = session.scalar(select(TeamMember).where(TeamMember.name == name))
        if member:
            # 成员已存在，更新其信息
            for key, value in member_info.items():
                if key != "name" and value:
                    setattr(member, key, value)
            session.flush()
            return member

        # 创建新成员
        member = TeamMember(name=name, pinyin=name, **{k: v for k, v in member_info.items() if k != "name"})
        session.add(member)
        session.flush()
        return member

    def list_awards(self) -> list[Award]:
        """获取所有未删除的荣誉记录（按日期降序排列）"""
        with self.db.session_scope() as session:
            # Eager load members to avoid lazy loading
            awards = session.scalars(
                select(Award)
                .where(Award.deleted == False)
                .options(selectinload(Award.members))
                .order_by(Award.award_date.desc())
            ).all()
            return awards

    def delete_award(self, award_id: int) -> None:
        """软删除指定 ID 的荣誉（移到回收站）"""
        with self.db.session_scope() as session:
            award = session.get(Award, award_id)
            if award:
                award.deleted = True
                award.deleted_at = datetime.utcnow()
                session.add(award)

    def update_award(
        self,
        award_id: int,
        *,
        competition_name: str | None = None,
        award_date: date | None = None,
        level: str | None = None,
        rank: str | None = None,
        certificate_code: str | None = None,
        remarks: str | None = None,
        member_names: Sequence[str] | Sequence[dict] | None = None,
        attachment_files: Sequence[Path] | None = None,
    ) -> Award:
        """
        Update an existing award with transaction support.
        Only updates fields that are provided (not None).

        Args:
            award_id: ID of award to update
            competition_name: New competition name
            award_date: New award date
            level: New award level
            rank: New award rank
            certificate_code: New certificate code
            remarks: New remarks
            member_names: New member list (replaces existing)
            attachment_files: New attachment files (replaces existing)

        Returns:
            Updated Award object

        Raises:
            ValueError: If award not found
        """
        with self.db.session_scope() as session:
            award = session.get(Award, award_id)
            if not award:
                raise ValueError(f"Award {award_id} not found")

            # Update scalar fields
            if competition_name is not None:
                award.competition_name = competition_name
            if award_date is not None:
                award.award_date = award_date
            if level is not None:
                award.level = level
            if rank is not None:
                award.rank = rank
            if certificate_code is not None:
                award.certificate_code = certificate_code
            if remarks is not None:
                award.remarks = remarks

            # Update member associations
            if member_names is not None:
                award.members.clear()
                award.members = [self._get_or_create_member_with_info(session, item) for item in member_names]

            session.add(award)
            session.flush()  # Validate before commit

            # Update attachments if provided
            if attachment_files is not None:
                self.attachments.save_attachments(
                    award.id,
                    award.competition_name,
                    attachment_files,
                    session=session,
                )

            return award

    def get_award_by_id(self, award_id: int) -> Award | None:
        """根据 ID 获取荣誉"""
        with self.db.session_scope() as session:
            return session.get(Award, award_id)

    def search_awards(
        self,
        query: str = "",
        level: str | None = None,
        rank: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 100,
    ) -> list[Award]:
        """
        Search and filter awards by multiple criteria.

        Args:
            query: Search text (matches competition_name or certificate_code)
            level: Filter by level (国家级/省级/校级)
            rank: Filter by rank (一等奖/二等奖/三等奖/优秀奖)
            date_from: Start date for award_date range
            date_to: End date for award_date range
            limit: Maximum number of results to return

        Returns:
            List of matching Award objects
        """
        with self.db.session_scope() as session:
            q = select(Award)
            conditions = []

            # Text search
            if query:
                conditions.append(
                    or_(
                        Award.competition_name.ilike(f"%{query}%"),
                        Award.certificate_code.ilike(f"%{query}%"),
                    )
                )

            # Level filter
            if level:
                conditions.append(Award.level == level)

            # Rank filter
            if rank:
                conditions.append(Award.rank == rank)

            # Date range filter
            if date_from:
                conditions.append(Award.award_date >= date_from)
            if date_to:
                conditions.append(Award.award_date <= date_to)

            # Apply all conditions
            if conditions:
                q = q.where(and_(*conditions))

            # Order by date (newest first) and apply limit
            q = q.order_by(Award.award_date.desc()).limit(limit)

            return session.scalars(q).all()

    def batch_delete_awards(self, award_ids: list[int]) -> int:
        """
        Delete multiple awards in a single transaction.

        Args:
            award_ids: List of award IDs to delete

        Returns:
            Number of awards deleted
        """
        with self.db.session_scope() as session:
            count = session.query(Award).filter(Award.id.in_(award_ids)).delete()
            return count

    def batch_update_level(self, award_ids: list[int], new_level: str) -> int:
        """
        Batch update award level for multiple records.

        Args:
            award_ids: List of award IDs to update
            new_level: New level value (国家级/省级/校级)

        Returns:
            Number of awards updated
        """
        with self.db.session_scope() as session:
            count = session.query(Award).filter(Award.id.in_(award_ids)).update({Award.level: new_level})
            return count

    def batch_update_rank(self, award_ids: list[int], new_rank: str) -> int:
        """
        Batch update award rank for multiple records.

        Args:
            award_ids: List of award IDs to update
            new_rank: New rank value (一等奖/二等奖/三等奖/优秀奖)

        Returns:
            Number of awards updated
        """
        with self.db.session_scope() as session:
            count = session.query(Award).filter(Award.id.in_(award_ids)).update({Award.rank: new_rank})
            return count

    def list_deleted_awards(self) -> list[Award]:
        """获取所有已删除的荣誉记录（回收站）"""
        with self.db.session_scope() as session:
            awards = session.scalars(
                select(Award)
                .where(Award.deleted == True)
                .options(selectinload(Award.members))
                .order_by(Award.deleted_at.desc())
            ).all()
            return list(awards)

    def restore_award(self, award_id: int) -> None:
        """从回收站恢复荣誉记录"""
        with self.db.session_scope() as session:
            award = session.get(Award, award_id)
            if award and award.deleted:
                award.deleted = False
                award.deleted_at = None
                session.add(award)

    def permanently_delete_award(self, award_id: int) -> None:
        """彻底删除荣誉记录（不可恢复）"""
        with self.db.session_scope() as session:
            award = session.get(Award, award_id)
            if award:
                session.delete(award)
