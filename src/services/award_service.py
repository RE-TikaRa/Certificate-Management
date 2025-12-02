from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Iterable, Sequence

from sqlalchemy import select

from ..data.database import Database
from ..data.models import Award, Tag, TeamMember
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
        certificate_code: str | None,
        remarks: str | None,
        member_names: Sequence[str] | Sequence[dict],
        tag_names: Sequence[str],
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
            award.tags = [self._get_or_create_tag(session, name) for name in tag_names]
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
            return session.scalars(select(TeamMember).order_by(TeamMember.sort_index, TeamMember.name)).all()

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
        name = member_info.get('name', '')
        if not name:
            raise ValueError("成员信息必须包含 'name' 字段")
        
        member = session.scalar(select(TeamMember).where(TeamMember.name == name))
        if member:
            # 成员已存在，更新其信息
            for key, value in member_info.items():
                if key != 'name' and value:
                    setattr(member, key, value)
            session.flush()
            return member
        
        # 创建新成员
        member = TeamMember(name=name, pinyin=name, **{k: v for k, v in member_info.items() if k != 'name'})
        session.add(member)
        session.flush()
        return member

    def _get_or_create_tag(self, session, name: str) -> Tag:
        tag = session.scalar(select(Tag).where(Tag.name == name))
        if tag:
            return tag
        tag = Tag(name=name, pinyin=name)
        session.add(tag)
        session.flush()
        return tag

    def delete_award(self, award_id: int) -> None:
        """删除指定 ID 的荣誉"""
        with self.db.session_scope() as session:
            award = session.get(Award, award_id)
            if award:
                session.delete(award)

    def get_award_by_id(self, award_id: int) -> Award | None:
        """根据 ID 获取荣誉"""
        with self.db.session_scope() as session:
            return session.get(Award, award_id)
