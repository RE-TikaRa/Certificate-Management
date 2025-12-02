from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd
from sqlalchemy import select

from ..config import TEMPLATES_DIR
from ..data.database import Database
from ..data.models import Award, ImportJob, Tag, TeamMember
from .attachment_manager import AttachmentManager

logger = logging.getLogger(__name__)

TEMPLATE_HEADERS = [
    "比赛名称",
    "获奖日期",
    "赛事级别",
    "奖项等级",
    "证书编号",
    "备注",
    "成员",
    "标签",
    "附件路径",
]


@dataclass
class ImportResult:
    total: int
    success: int
    failed: int
    errors: list[str]


class ImportExportService:
    def __init__(self, db: Database, attachments: AttachmentManager):
        self.db = db
        self.attachments = attachments
        self._ensure_template()
        self._member_cache: dict[str, TeamMember] = {}
        self._tag_cache: dict[str, Tag] = {}

    def _ensure_template(self) -> None:
        csv_path = TEMPLATES_DIR / "awards_template.csv"
        if not csv_path.exists():
            with csv_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(TEMPLATE_HEADERS)
        xlsx_path = TEMPLATES_DIR / "awards_template.xlsx"
        if not xlsx_path.exists():
            df = pd.DataFrame(columns=TEMPLATE_HEADERS)
            df.to_excel(xlsx_path, index=False)

    def export_awards(self, export_path: Path, awards: Sequence[Award]) -> Path:
        df = pd.DataFrame(
            [
                {
                    "比赛名称": award.competition_name,
                    "获奖日期": award.award_date.isoformat(),
                    "赛事级别": award.level,
                    "奖项等级": award.rank,
                    "证书编号": award.certificate_code,
                    "备注": award.remarks,
                    "成员": ",".join(member.name for member in award.members),
                    "标签": ",".join(tag.name for tag in award.tags),
                    "附件数量": len(award.attachments),
                }
                for award in awards
            ]
        )
        export_path.parent.mkdir(parents=True, exist_ok=True)
        if export_path.suffix == ".xlsx":
            df.to_excel(export_path, index=False)
        else:
            df.to_csv(export_path, index=False)
        logger.info("Exported %s awards to %s", len(awards), export_path)
        return export_path

    def import_from_file(self, file_path: Path) -> ImportResult:
        try:
            if file_path.suffix.lower() == ".xlsx":
                df = pd.read_excel(file_path)
            else:
                df = pd.read_csv(file_path)
        except Exception as exc:
            return ImportResult(total=0, success=0, failed=0, errors=[str(exc)])

        required_cols = {"比赛名称", "获奖日期", "赛事级别", "奖项等级"}
        if not required_cols.issubset(df.columns):
            missing = ", ".join(required_cols - set(df.columns))
            return ImportResult(total=0, success=0, failed=0, errors=[f"缺少列: {missing}"])

        total = len(df)
        success = 0
        errors: list[str] = []

        with self.db.session_scope() as session:
            for idx, row in df.iterrows():
                try:
                    award = Award(
                        competition_name=str(row["比赛名称"]).strip(),
                        award_date=pd.to_datetime(row["获奖日期"]).date(),
                        level=str(row["赛事级别"]).strip(),
                        rank=str(row["奖项等级"]).strip(),
                        certificate_code=str(row.get("证书编号", "") or "").strip() or None,
                        remarks=str(row.get("备注", "") or "").strip() or None,
                    )
                    session.add(award)
                    session.flush()

                    members = self._parse_items(str(row.get("成员", "")))
                    tags = self._parse_items(str(row.get("标签", "")))
                    award.members = [self._get_or_create_member(session, name) for name in members]
                    award.tags = [self._get_or_create_tag(session, name) for name in tags]

                    attachment_paths = self._parse_items(str(row.get("附件路径", "")), sep=";")
                    files = [Path(path) for path in attachment_paths if path]
                    if files:
                        self.attachments.save_attachments(award.id, award.competition_name, files, session=session)
                    success += 1
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"第 {idx + 2} 行: {exc}")
            session.add(
                ImportJob(
                    filename=file_path.name,
                    status="success" if not errors else "partial",
                    message="\n".join(errors) if errors else None,
                )
            )

        return ImportResult(total=total, success=success, failed=total - success, errors=errors)

    def _parse_items(self, value: str, sep: str = ",") -> list[str]:
        unique: list[str] = []
        seen: set[str] = set()
        for item in value.split(sep):
            cleaned = item.strip()
            if cleaned and cleaned.lower() not in seen:
                seen.add(cleaned.lower())
                unique.append(cleaned)
        return unique

    def _get_or_create_member(self, session, name: str) -> TeamMember:
        if name in self._member_cache:
            return self._member_cache[name]
        member = session.scalar(select(TeamMember).where(TeamMember.name == name))
        if member:
            self._member_cache[name] = member
            return member
        member = TeamMember(name=name, pinyin=name)
        session.add(member)
        session.flush()
        self._member_cache[name] = member
        return member

    def _get_or_create_tag(self, session, name: str) -> Tag:
        if name in self._tag_cache:
            return self._tag_cache[name]
        tag = session.scalar(select(Tag).where(Tag.name == name))
        if tag:
            self._tag_cache[name] = tag
            return tag
        tag = Tag(name=name, pinyin=name)
        session.add(tag)
        session.flush()
        self._tag_cache[name] = tag
        return tag
