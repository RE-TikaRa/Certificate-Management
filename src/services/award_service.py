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
        member_names: Sequence[str],
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
            award.members = [self._get_or_create_member(session, name) for name in member_names]
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

    def _get_or_create_tag(self, session, name: str) -> Tag:
        tag = session.scalar(select(Tag).where(Tag.name == name))
        if tag:
            return tag
        tag = Tag(name=name, pinyin=name)
        session.add(tag)
        session.flush()
        return tag
