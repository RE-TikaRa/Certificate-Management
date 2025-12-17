import csv
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import TEMPLATES_DIR
from ..data.database import Database
from ..data.models import Award, AwardFlagValue, AwardMember, CustomFlag, ImportJob
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
    def __init__(self, db: Database, attachments: AttachmentManager, flags=None):
        self.db = db
        self.attachments = attachments
        self.flags = flags
        self._ensure_template()

    def get_awards_template_path(self, fmt: str = "xlsx") -> Path:
        """返回荣誉导入模板路径（csv/xlsx）。"""
        self._ensure_template()
        suffix = fmt.lower().lstrip(".")
        filename = "awards_template.xlsx" if suffix == "xlsx" else "awards_template.csv"
        return TEMPLATES_DIR / filename

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
        flag_defs: list[CustomFlag] = []
        flag_values: dict[int, dict[str, bool]] = {}
        if self.flags:
            flag_defs = self.flags.list_flags(enabled_only=True)
            flag_values = self.flags.get_flags_for_awards([award.id for award in awards])

        rows = []
        for award in awards:
            row = {
                "比赛名称": award.competition_name,
                "获奖日期": award.award_date.isoformat(),
                "赛事级别": award.level,
                "奖项等级": award.rank,
                "证书编号": award.certificate_code,
                "备注": award.remarks,
                "成员": ",".join(award.member_names),
                "附件数量": len(award.attachments),
            }
            if flag_defs:
                values = flag_values.get(award.id, {})
                for flag in flag_defs:
                    col = f"{flag.label} ({flag.key})"
                    row[col] = int(values.get(flag.key, flag.default_value))
            rows.append(row)

        df = pd.DataFrame(rows)
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
        flag_defs: list[CustomFlag] = self.flags.list_flags(enabled_only=True) if self.flags else []
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

        # flag 列映射：优先匹配 "label (key)"，其次 label
        flag_col_map: dict[str, str] = {}
        for flag in flag_defs:
            preferred = f"{flag.label} ({flag.key})"
            if preferred in df.columns:
                flag_col_map[flag.key] = preferred
            elif flag.label in df.columns:
                flag_col_map[flag.key] = flag.label
            else:
                flag_col_map[flag.key] = ""  # 缺失列，用默认值

        def clean_cell(value) -> str:
            if value is None:
                return ""
            if isinstance(value, float) and pd.isna(value):
                return ""
            if pd.isna(value):
                return ""
            text = str(value).strip()
            return "" if text.lower() == "nan" else text

        def handle_row(session: Session, row_index: int, row) -> None:
            nonlocal success
            timestamp = cast(pd.Timestamp, pd.to_datetime(clean_cell(row["获奖日期"])))
            award = Award(
                competition_name=clean_cell(row["比赛名称"]),
                award_date=timestamp.date(),
                level=clean_cell(row["赛事级别"]),
                rank=clean_cell(row["奖项等级"]),
                certificate_code=clean_cell(row.get("证书编号", "")) or None,
                remarks=clean_cell(row.get("备注", "")) or None,
            )
            session.add(award)
            session.flush()

            members = self._parse_items(clean_cell(row.get("成员", "")))
            award.award_members = [
                AwardMember(member_name=name, sort_order=index) for index, name in enumerate(members)
            ]
            session.flush()

            if flag_defs and not dry_run:
                values: list[AwardFlagValue] = []
                for flag in flag_defs:
                    col = flag_col_map.get(flag.key, "")
                    raw = row.get(col, None) if col else None
                    value = self._parse_flag_value(raw, default=flag.default_value)
                    values.append(AwardFlagValue(award_id=award.id, flag_key=flag.key, value=value))
                session.add_all(values)

            attachment_paths = self._parse_items(clean_cell(row.get("附件路径", "")), sep=";")
            files = [Path(path) for path in attachment_paths if path]
            if files and not dry_run:
                self.attachments.save_attachments(award.id, award.competition_name, files, session=session)

            if not dry_run:
                member_names = " ".join(members)
                self.db.upsert_award_fts(
                    award.id,
                    award.competition_name,
                    award.certificate_code,
                    member_names,
                    session=session,
                )

            success += 1

        def process_rows(session: Session) -> None:
            for idx, row in df.iterrows():
                row_index = int(idx) if isinstance(idx, (int, float, str)) else 0
                try:
                    with session.begin_nested():
                        handle_row(session, row_index, row)
                except Exception as exc:
                    errors.append(f"第 {row_index + 2} 行: {exc}")
                    error_rows.append({"行号": row_index + 2, "错误": str(exc), **row.to_dict()})

                processed = row_index + 1
                if progress_callback and processed % 10 == 0:
                    elapsed = time.time() - start_time
                    rate = elapsed / max(processed, 1)
                    remaining = max(total - processed, 0) * rate
                    progress_callback(processed, total, float(remaining))

        if dry_run:
            # Strict dry-run: no DB writes, no attachment copy, no ImportJob, no error file.
            with self.db.engine.connect() as connection:
                transaction = connection.begin()
                session = Session(bind=connection, expire_on_commit=False)
                try:
                    process_rows(session)
                finally:
                    session.close()
                    transaction.rollback()
        else:
            with self.db.session_scope() as session:
                process_rows(session)
                session.add(
                    ImportJob(
                        filename=file_path.name,
                        status="success" if not errors else "partial",
                        message="\n".join(errors) if errors else None,
                    )
                )

        error_file: Path | None = None
        if error_rows and not dry_run:
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

    def _parse_flag_value(self, value, default: bool) -> bool:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return bool(default)
        if isinstance(value, (int, bool)):
            return bool(value)
        text = str(value).strip().lower()
        if text in {"1", "true", "t", "yes", "y", "是", "对", "勾", "勾选"}:
            return True
        if text in {"0", "false", "f", "no", "n", "否", "不", "未"}:
            return False
        return bool(default)

    def list_jobs(self, limit: int = 20) -> list[ImportJob]:
        with self.db.session_scope() as session:
            q = select(ImportJob).order_by(ImportJob.created_at.desc()).limit(max(1, limit))
            return list(session.scalars(q).all())
