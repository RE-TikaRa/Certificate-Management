from datetime import date, datetime
from typing import cast

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
from sqlalchemy.ext.associationproxy import AssociationProxy, association_proxy
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
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AwardMember(Base):
    __tablename__ = "award_members"

    # Exclude Base columns that don't exist in the legacy table
    created_at = cast("Mapped[datetime]", None)
    updated_at = cast("Mapped[datetime]", None)

    award_id: Mapped[int] = mapped_column(ForeignKey("awards.id", ondelete="CASCADE"), index=True)
    member_id: Mapped[int | None] = mapped_column(
        ForeignKey("team_members.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    member_name: Mapped[str] = mapped_column(String(128), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    member: Mapped["TeamMember | None"] = relationship(back_populates="award_associations")
    award: Mapped["Award"] = relationship(back_populates="award_members")


class Award(Base):
    __tablename__ = "awards"

    competition_name: Mapped[str] = mapped_column(String(255), nullable=False)
    award_date: Mapped[date] = mapped_column(Date, nullable=False)
    level: Mapped[str] = mapped_column(String(50), nullable=False)
    rank: Mapped[str] = mapped_column(String(50), nullable=False)
    certificate_code: Mapped[str | None] = mapped_column(String(128))
    remarks: Mapped[str | None] = mapped_column(Text)
    attachment_folder: Mapped[str | None] = mapped_column(String(255))
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)

    award_members: Mapped[list["AwardMember"]] = relationship(
        back_populates="award",
        order_by="AwardMember.sort_order",
        cascade="all, delete-orphan",
    )
    attachments: Mapped[list["Attachment"]] = relationship(back_populates="award", cascade="all, delete-orphan")

    @property
    def member_names(self) -> list[str]:
        return [assoc.member_name for assoc in self.award_members]


class TeamMember(Base):
    __tablename__ = "team_members"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    gender: Mapped[str | None] = mapped_column(String(10))  # 男/女
    id_card: Mapped[str | None] = mapped_column(String(18), unique=True)  # 身份证号
    phone: Mapped[str | None] = mapped_column(String(20))  # 手机号
    student_id: Mapped[str | None] = mapped_column(String(20), unique=True)  # 学号
    email: Mapped[str | None] = mapped_column(String(128))  # 邮箱
    school: Mapped[str | None] = mapped_column(String(128))  # 学校名称
    school_code: Mapped[str | None] = mapped_column(String(32))  # 学校标识码
    major: Mapped[str | None] = mapped_column(String(128))  # 专业
    major_code: Mapped[str | None] = mapped_column(String(32))  # 专业代码
    class_name: Mapped[str | None] = mapped_column(String(128))  # 班级
    college: Mapped[str | None] = mapped_column(String(128))  # 学院
    pinyin: Mapped[str | None] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_index: Mapped[int] = mapped_column(Integer, default=0)

    award_associations: Mapped[list["AwardMember"]] = relationship(back_populates="member")


class Attachment(Base):
    __tablename__ = "attachments"

    award_id: Mapped[int] = mapped_column(ForeignKey("awards.id", ondelete="CASCADE"))
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    relative_path: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    file_md5: Mapped[str | None] = mapped_column(String(32))  # MD5哈希值
    file_size: Mapped[int | None] = mapped_column(Integer)  # 文件大小（字节）
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


class Major(Base):
    """专业名称数据库"""

    __tablename__ = "majors"
    __table_args__ = (
        UniqueConstraint("name", name="uq_majors_name"),
        UniqueConstraint("code", name="uq_majors_code"),
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str | None] = mapped_column(String(32))
    pinyin: Mapped[str | None] = mapped_column(String(255))  # 拼音，用于搜索
    category: Mapped[str | None] = mapped_column(String(64))  # 分类（工学、理学等）
    discipline_code: Mapped[str | None] = mapped_column(String(16))
    discipline_name: Mapped[str | None] = mapped_column(String(128))
    class_code: Mapped[str | None] = mapped_column(String(16))
    class_name: Mapped[str | None] = mapped_column(String(128))


class CustomFlag(Base):
    """自定义布尔开关定义"""

    __tablename__ = "custom_flags"
    __table_args__ = (UniqueConstraint("key", name="uq_custom_flags_key"),)

    key: Mapped[str] = mapped_column(String(64), unique=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    default_value: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class AwardFlagValue(Base):
    """荣誉对应的开关值"""

    __tablename__ = "award_flag_values"
    __table_args__ = (UniqueConstraint("award_id", "flag_key", name="uq_award_flag_values"),)

    award_id: Mapped[int] = mapped_column(ForeignKey("awards.id", ondelete="CASCADE"), nullable=False)
    flag_key: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[bool] = mapped_column(Boolean, default=False)

class School(Base):
    __tablename__ = "schools"
    __table_args__ = (
        UniqueConstraint("name", name="uq_schools_name"),
        UniqueConstraint("code", name="uq_schools_code"),
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str | None] = mapped_column(String(32))
    pinyin: Mapped[str | None] = mapped_column(String(255))
    region: Mapped[str | None] = mapped_column(String(64))


class SchoolMajorMapping(Base):
    __tablename__ = "school_major_mappings"
    __table_args__ = (
        UniqueConstraint("school_code", "major_code", name="uq_school_major_code"),
        UniqueConstraint("school_name", "major_name", name="uq_school_major_name"),
    )

    school_name: Mapped[str] = mapped_column(String(128), nullable=False)
    school_code: Mapped[str | None] = mapped_column(String(32))
    major_name: Mapped[str] = mapped_column(String(128), nullable=False)
    major_code: Mapped[str | None] = mapped_column(String(32))
    college_name: Mapped[str | None] = mapped_column(String(128))
    category: Mapped[str | None] = mapped_column(String(64))
    discipline_code: Mapped[str | None] = mapped_column(String(16))
    discipline_name: Mapped[str | None] = mapped_column(String(128))
