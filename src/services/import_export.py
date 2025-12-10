import csv
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pandas as pd
from sqlalchemy import select

from ..config import TEMPLATES_DIR
from ..data.database import Database
from ..data.models import Award, AwardMember, ImportJob, TeamMember
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
    "附件路径",
]


@dataclass
class ImportResult:
    total: int
    success: int
    failed: int
    errors: list[str]
    error_file: Path | None = None


class ImportExportService:
    def __init__(self, db: Database, attachments: AttachmentManager):
        self.db = db
        self.attachments = attachments
        self._ensure_template()
        self._member_cache: dict[str, TeamMember] = {}

    def _ensure_template(self) -> None:
        csv_path = TEMPLATES_DIR / "awards_template.csv"
        if not csv_path.exists():
            with csv_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(TEMPLATE_HEADERS)
        xlsx_path = TEMPLATES_DIR / "awards_template.xlsx"
        if not xlsx_path.exists():
            df = pd.DataFrame(columns=pd.Index(TEMPLATE_HEADERS))
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

    def import_from_file(
        self,
        file_path: Path,
        *,
        progress_callback: Callable[[int, int, float], None] | None = None,
        dry_run: bool = False,
    ) -> ImportResult:
        try:
            df = pd.read_excel(file_path) if file_path.suffix.lower() == ".xlsx" else pd.read_csv(file_path)
        except Exception as exc:
            return ImportResult(total=0, success=0, failed=0, errors=[str(exc)])

        required_cols = {"比赛名称", "获奖日期", "赛事级别", "奖项等级"}
        if not required_cols.issubset(df.columns):
            missing = ", ".join(required_cols - set(df.columns))
            return ImportResult(total=0, success=0, failed=0, errors=[f"缺少列: {missing}"])

        total = len(df)
        success = 0
        errors: list[str] = []
        error_rows: list[dict] = []

        import time

        start_time = time.time()

        with self.db.session_scope() as session:
            for idx, row in df.iterrows():
                row_index = int(idx) if isinstance(idx, (int, float, str)) else 0
                try:
                    timestamp = cast(pd.Timestamp, pd.to_datetime(row["获奖日期"]))
                    award = Award(
                        competition_name=str(row["比赛名称"]).strip(),
                        award_date=timestamp.date(),
                        level=str(row["赛事级别"]).strip(),
                        rank=str(row["奖项等级"]).strip(),
                        certificate_code=str(row.get("证书编号", "") or "").strip() or None,
                        remarks=str(row.get("备注", "") or "").strip() or None,
                    )
                    session.add(award)
                    session.flush()

                    members = self._parse_items(str(row.get("成员", "")))
                    member_objs = [self._get_or_create_member(session, name) for name in members]
                    award.award_members = [
                        AwardMember(member=member, sort_order=index) for index, member in enumerate(member_objs)
                    ]

                    attachment_paths = self._parse_items(str(row.get("附件路径", "")), sep=";")
                    files = [Path(path) for path in attachment_paths if path]
                    if files:
                        self.attachments.save_attachments(award.id, award.competition_name, files, session=session)
                    success += 1
                    if dry_run:
                        session.rollback()
                except Exception as exc:
                    errors.append(f"第 {row_index + 2} 行: {exc}")
                    error_rows.append({"行号": row_index + 2, "错误": str(exc), **row.to_dict()})

                # 进度与 ETA
                processed = int(row_index) + 1
                if progress_callback and processed % 10 == 0:
                    elapsed = time.time() - start_time
                    rate = elapsed / max(processed, 1)
                    remaining = max(total - processed, 0) * rate
                    progress_callback(processed, total, float(remaining))
            session.add(
                ImportJob(
                    filename=file_path.name,
                    status="success" if not errors else "partial",
                    message="\n".join(errors) if errors else None,
                )
            )

        error_file: Path | None = None
        if error_rows:
            error_file = file_path.parent / f"{file_path.stem}_errors.csv"
            try:
                pd.DataFrame(error_rows).to_csv(error_file, index=False)
            except Exception:
                error_file = None

        return ImportResult(total=total, success=success, failed=total - success, errors=errors, error_file=error_file)

    def _parse_items(self, value: str, sep: str = ",") -> list[str]:
        unique: list[str] = []
        seen: set[str] = set()
        for item in value.split(sep):
            cleaned = item.strip()
            if cleaned and cleaned.lower() not in seen:
                seen.add(cleaned.lower())
                unique.append(cleaned)
        return unique

    def list_jobs(self, limit: int = 20) -> list[ImportJob]:
        with self.db.session_scope() as session:
            q = select(ImportJob).order_by(ImportJob.created_at.desc()).limit(max(1, limit))
            return list(session.scalars(q).all())

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
