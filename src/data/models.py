from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)


class Base(DeclarativeBase):
    metadata = metadata
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Award(Base):
    __tablename__ = "awards"

    competition_name: Mapped[str] = mapped_column(String(255), nullable=False)
    award_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    level: Mapped[str] = mapped_column(String(50), nullable=False)
    rank: Mapped[str] = mapped_column(String(50), nullable=False)
    certificate_code: Mapped[str | None] = mapped_column(String(128))
    remarks: Mapped[str | None] = mapped_column(Text)
    attachment_folder: Mapped[str | None] = mapped_column(String(255))

    members: Mapped[list["TeamMember"]] = relationship(
        secondary=lambda: award_members_table, back_populates="awards", lazy="joined"
    )
    tags: Mapped[list["Tag"]] = relationship(
        secondary=lambda: award_tags_table, back_populates="awards", lazy="joined"
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="award", cascade="all, delete-orphan"
    )


class TeamMember(Base):
    __tablename__ = "team_members"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    gender: Mapped[str | None] = mapped_column(String(10))  # 男/女
    age: Mapped[int | None] = mapped_column(Integer)
    id_card: Mapped[str | None] = mapped_column(String(18), unique=True)  # 身份证号
    phone: Mapped[str | None] = mapped_column(String(20))  # 手机号
    student_id: Mapped[str | None] = mapped_column(String(20), unique=True)  # 学号
    contact_phone: Mapped[str | None] = mapped_column(String(20))  # 联系电话
    email: Mapped[str | None] = mapped_column(String(128))  # 邮箱
    major: Mapped[str | None] = mapped_column(String(128))  # 专业
    class_name: Mapped[str | None] = mapped_column(String(128))  # 班级
    college: Mapped[str | None] = mapped_column(String(128))  # 学院
    pinyin: Mapped[str | None] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_index: Mapped[int] = mapped_column(Integer, default=0)

    awards: Mapped[list[Award]] = relationship(
        secondary=lambda: award_members_table, back_populates="members"
    )


class Tag(Base):
    __tablename__ = "tags"

    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    pinyin: Mapped[str | None] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_index: Mapped[int] = mapped_column(Integer, default=0)

    awards: Mapped[list[Award]] = relationship(
        secondary=lambda: award_tags_table, back_populates="tags"
    )


award_members_table = Table(
    "award_members",
    Base.metadata,
    Column("award_id", ForeignKey("awards.id", ondelete="CASCADE"), primary_key=True),
    Column("member_id", ForeignKey("team_members.id", ondelete="CASCADE"), primary_key=True),
)

award_tags_table = Table(
    "award_tags",
    Base.metadata,
    Column("award_id", ForeignKey("awards.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Attachment(Base):
    __tablename__ = "attachments"

    award_id: Mapped[int] = mapped_column(ForeignKey("awards.id", ondelete="CASCADE"))
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    relative_path: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)

    award: Mapped[Award] = relationship(back_populates="attachments")


class Setting(Base):
    __tablename__ = "settings"
    __table_args__ = (UniqueConstraint("key", name="uq_settings_key"),)

    key: Mapped[str] = mapped_column(String(128), unique=True)
    value: Mapped[str] = mapped_column(String(512))


class BackupRecord(Base):
    __tablename__ = "backups"

    path: Mapped[str] = mapped_column(String(255))
    include_attachments: Mapped[bool] = mapped_column(Boolean, default=True)
    include_logs: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    message: Mapped[str | None] = mapped_column(Text)


class ImportJob(Base):
    __tablename__ = "imports"

    filename: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    message: Mapped[str | None] = mapped_column(Text)
