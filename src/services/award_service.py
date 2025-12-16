import logging
from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from ..data.database import Database
from ..data.models import Award, AwardMember, TeamMember
from .attachment_manager import AttachmentManager

logger = logging.getLogger(__name__)


class AwardService:
    def __init__(self, db: Database, attachments: AttachmentManager, flags=None):
        self.db = db
        self.attachments = attachments
        self.flags = flags

    def create_award(
        self,
        *,
        competition_name: str,
        award_date: date,
        level: str,
        rank: str,
        certificate_code: str | None,
        remarks: str | None,
        member_names: Sequence[str] | Sequence[dict],
        attachment_files: Sequence[Path],
        flag_values: dict[str, bool] | None = None,
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
            snapshot_names = self._set_award_members(session, award, member_names)
            session.add(award)
            session.flush()

            if attachment_files:
                self.attachments.save_attachments(
                    award.id,
                    competition_name,
                    attachment_files,
                    session=session,
                )
            if flag_values and self.flags:
                self.flags.set_award_flags(award.id, flag_values)
            self._refresh_award_fts(award, snapshot_names)
            return award

    def list_members(self) -> list[TeamMember]:
        with self.db.session_scope() as session:
            # Eager load award associations to avoid lazy loading
            members = session.scalars(
                select(TeamMember)
                .options(selectinload(TeamMember.award_associations).selectinload(AwardMember.award))
                .order_by(TeamMember.sort_index, TeamMember.name)
            ).all()
            return list(members)

    def add_member(self, name: str) -> TeamMember:
        with self.db.session_scope() as session:
            member = TeamMember(name=name, pinyin=name)
            session.add(member)
            session.flush()
            return member

    def remove_member(self, name: str) -> None:
        with self.db.session_scope() as session:
            member = session.scalar(select(TeamMember).where(TeamMember.name == name))
            if member:
                session.delete(member)

    def _get_or_create_member(self, session, name: str) -> TeamMember:
        member = session.scalar(select(TeamMember).where(TeamMember.name == name))
        if member:
            return member
        member = TeamMember(name=name, pinyin=name)
        session.add(member)
        session.flush()
        self.db.upsert_member_fts(
            member.id,
            name=member.name,
            pinyin=member.pinyin,
            student_id=member.student_id,
            phone=member.phone,
            email=member.email,
            college=member.college,
            major=member.major,
        )
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
            self.db.upsert_member_fts(
                member.id,
                name=member.name,
                pinyin=member.pinyin,
                student_id=member.student_id,
                phone=member.phone,
                email=member.email,
                college=member.college,
                major=member.major,
            )
            return member

        # 创建新成员
        member = TeamMember(name=name, pinyin=name, **{k: v for k, v in member_info.items() if k != "name"})
        session.add(member)
        session.flush()
        self.db.upsert_member_fts(
            member.id,
            name=member.name,
            pinyin=member.pinyin,
            student_id=member.student_id,
            phone=member.phone,
            email=member.email,
            college=member.college,
            major=member.major,
        )
        return member

    def _set_award_members(self, session, award: Award, members: Sequence[str] | Sequence[dict]) -> list[str]:
        """重建 award_members（支持“可选入库”的成员快照）"""
        award.award_members.clear()
        snapshot_names: list[str] = []
        for index, item in enumerate(members):
            if isinstance(item, str):
                name = item.strip()
                if not name:
                    continue
                award.award_members.append(AwardMember(member_name=name, sort_order=index))
                snapshot_names.append(name)
                continue

            name = str(item.get("name", "")).strip()
            if not name:
                continue

            join_library = bool(item.get("join_member_library", False))
            if join_library:
                member_info = {k: v for k, v in item.items() if k not in {"join_member_library"} and v}
                member_info["name"] = name
                member = self._get_or_create_member_with_info(session, member_info)
                award.award_members.append(AwardMember(member=member, member_name=name, sort_order=index))
                snapshot_names.append(name)
            else:
                award.award_members.append(AwardMember(member_name=name, sort_order=index))
                snapshot_names.append(name)
        return snapshot_names

    def list_awards(self) -> list[Award]:
        """获取所有未删除的荣誉记录（按日期降序排列）"""
        with self.db.session_scope() as session:
            stmt = (
                select(Award)
                .where(Award.deleted.is_(False))
                .options(selectinload(Award.award_members).selectinload(AwardMember.member))
                .order_by(Award.award_date.desc())
            )
            try:
                awards = session.scalars(stmt).all()
            except ArgumentError as exc:
                logger.warning("Failed to prefetch award members, fallback to lazy load: %s", exc)
                awards = session.scalars(
                    select(Award).where(Award.deleted.is_(False)).order_by(Award.award_date.desc())
                ).all()
            return list(awards)

    def delete_award(self, award_id: int) -> None:
        """软删除指定 ID 的荣誉（移到回收站）"""
        with self.db.session_scope() as session:
            award = session.get(Award, award_id)
            if award:
                award.deleted = True
                award.deleted_at = datetime.utcnow()
                session.add(award)
                self.db.delete_award_fts(award_id)

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
        flag_values: dict[str, bool] | None = None,
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
            attachment_files: When provided, sync attachments to this list (kept + added; missing ones moved to trash)

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
                snapshot_names = self._set_award_members(session, award, member_names)
                self._refresh_award_fts(award, snapshot_names)
            else:
                self._refresh_award_fts(award, award.member_names)

            session.add(award)
            session.flush()  # Validate before commit

            # Update attachments if provided
            if attachment_files is not None:
                root = self.attachments.ensure_root()
                existing = [a for a in award.attachments if not a.deleted]
                existing_by_path: dict[Path, int] = {}
                for attachment in existing:
                    existing_by_path[(root / attachment.relative_path).resolve()] = attachment.id

                desired_paths: set[Path] = set()
                new_files: list[Path] = []
                for path in attachment_files:
                    resolved = Path(path).resolve()
                    if resolved in existing_by_path:
                        desired_paths.add(resolved)
                    else:
                        new_files.append(resolved)

                delete_ids = [attachment_id for p, attachment_id in existing_by_path.items() if p not in desired_paths]
                if delete_ids:
                    self.attachments.mark_deleted(delete_ids, session=session)
                if new_files:
                    self.attachments.save_attachments(
                        award.id,
                        award.competition_name,
                        new_files,
                        session=session,
                    )
            if flag_values is not None and self.flags:
                self.flags.set_award_flags(award.id, flag_values)

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
            fts_ids: list[int] = []
            if query:
                fts_ids = self.db.search_awards_fts(query, limit)

            q = select(Award).options(selectinload(Award.award_members).selectinload(AwardMember.member))
            conditions: list[ColumnElement[bool]] = [Award.deleted.is_(False)]

            if query:
                if fts_ids:
                    conditions.append(Award.id.in_(fts_ids))
                else:
                    conditions.append(
                        or_(
                            Award.competition_name.ilike(f"%{query}%"),
                            Award.certificate_code.ilike(f"%{query}%"),
                        )
                    )

            if level:
                conditions.append(Award.level == level)
            if rank:
                conditions.append(Award.rank == rank)
            if date_from:
                conditions.append(Award.award_date >= date_from)
            if date_to:
                conditions.append(Award.award_date <= date_to)
            if conditions:
                q = q.where(and_(*conditions))

            q = q.order_by(Award.award_date.desc()).limit(limit)
            results = list(session.scalars(q).all())

            if fts_ids:
                order = {id_: idx for idx, id_ in enumerate(fts_ids)}
                results = sorted(results, key=lambda a: order.get(a.id, len(order)))
            return results

    def _refresh_award_fts(self, award: Award, members: Sequence[str]) -> None:
        member_names = " ".join(members)
        self.db.upsert_award_fts(
            award.id,
            award.competition_name,
            award.certificate_code,
            member_names,
        )

    def batch_delete_awards(self, award_ids: list[int]) -> int:
        """
        Batch soft delete multiple awards.

        Args:
            award_ids: List of award IDs to delete

        Returns:
            Number of awards deleted
        """
        with self.db.session_scope() as session:
            count = (
                session.query(Award)
                .filter(Award.id.in_(award_ids))
                .update({Award.deleted: True, Award.deleted_at: datetime.utcnow()}, synchronize_session=False)
            )
        for award_id in award_ids:
            self.db.delete_award_fts(award_id)
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
            stmt = (
                select(Award)
                .where(Award.deleted.is_(True))
                .options(selectinload(Award.award_members).selectinload(AwardMember.member))
                .order_by(Award.deleted_at.desc())
            )
            try:
                awards = session.scalars(stmt).all()
            except ArgumentError as exc:
                logger.warning("Failed to prefetch deleted award members, fallback to lazy load: %s", exc)
                awards = session.scalars(
                    select(Award).where(Award.deleted.is_(True)).order_by(Award.deleted_at.desc())
                ).all()
            return list(awards)

    def restore_award(self, award_id: int) -> None:
        """从回收站恢复荣誉记录"""
        with self.db.session_scope() as session:
            award = session.scalar(
                select(Award)
                .where(Award.id == award_id)
                .options(selectinload(Award.award_members).selectinload(AwardMember.member))
            )
            if award and award.deleted:
                award.deleted = False
                award.deleted_at = None
                session.add(award)
                self._refresh_award_fts(award, award.member_names)

    def permanently_delete_award(self, award_id: int) -> None:
        """彻底删除荣誉记录（不可恢复）"""
        # 先清理物理文件
        try:
            self.attachments.delete_all_for_award(award_id)
        except Exception as e:
            logger.error(f"Failed to delete attachment files for award {award_id}: {e}")

        self.db.delete_award_fts(award_id)
        with self.db.session_scope() as session:
            award = session.get(Award, award_id)
            if award:
                session.delete(award)
