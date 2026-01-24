import csv
import itertools
import logging
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import date as py_date, datetime as py_datetime
from pathlib import Path
from typing import cast

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import TEMPLATES_DIR
from ..data.database import Database
from ..data.models import Attachment, Award, AwardFlagValue, AwardMember, CustomFlag, ImportJob
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
RELATIVE_ATTACHMENT_HEADER = "附件相对路径"


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
            with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
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

        award_ids = [award.id for award in awards]
        loaded_by_id: dict[int, Award] = {}
        attachment_by_award: dict[int, list[Attachment]] = {}
        if award_ids:
            with self.db.session_scope() as session:
                loaded = session.scalars(
                    select(Award)
                    .where(Award.id.in_(award_ids))
                    .options(selectinload(Award.award_members), selectinload(Award.attachments))
                ).all()
                loaded_by_id = {a.id: a for a in loaded}
                for a in loaded:
                    attachment_by_award[a.id] = [att for att in a.attachments if not att.deleted]

        attachments_root = self.attachments.ensure_root()
        export_path.parent.mkdir(parents=True, exist_ok=True)

        def build_row(src_award: Award) -> dict[str, object]:
            members = ",".join(getattr(src_award, "member_names", []) or [])
            attachment_items = attachment_by_award.get(src_award.id, [])
            attachment_paths = [
                str((attachments_root / att.relative_path).resolve())
                for att in attachment_items
                if isinstance(att.relative_path, str) and att.relative_path
            ]
            relative_paths = [
                str(att.relative_path)
                for att in attachment_items
                if isinstance(att.relative_path, str) and att.relative_path
            ]
            row: dict[str, object] = {
                "比赛名称": src_award.competition_name,
                "获奖日期": src_award.award_date.isoformat(),
                "赛事级别": src_award.level,
                "奖项等级": src_award.rank,
                "证书编号": src_award.certificate_code,
                "备注": src_award.remarks,
                "成员": members,
                "附件路径": ";".join(attachment_paths),
                RELATIVE_ATTACHMENT_HEADER: ";".join(relative_paths),
                "附件数量": len(attachment_paths),
            }
            if flag_defs:
                values = flag_values.get(src_award.id, {})
                for flag in flag_defs:
                    col = f"{flag.label} ({flag.key})"
                    row[col] = int(values.get(flag.key, flag.default_value))
            return row

        if export_path.suffix.lower() == ".csv":
            flag_headers = [f"{flag.label} ({flag.key})" for flag in flag_defs]
            headers = [*TEMPLATE_HEADERS, RELATIVE_ATTACHMENT_HEADER, "附件数量", *flag_headers]
            with export_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
                writer.writeheader()
                for award in awards:
                    src_award = loaded_by_id.get(award.id, award)
                    writer.writerow(build_row(src_award))
        else:
            rows = []
            for award in awards:
                src_award = loaded_by_id.get(award.id, award)
                rows.append(build_row(src_award))
            df = pd.DataFrame(rows)
            df.to_excel(export_path, index=False)
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
        df_iter: Iterable[pd.DataFrame] | None = None
        total = 0
        columns: list[str] = []
        encoding = "utf-8-sig"
        try:
            if file_path.suffix.lower() == ".xlsx":
                df = pd.read_excel(file_path)
                df_iter = (df for _ in range(1))
                total = len(df)
                columns = list(df.columns)
            else:
                try:
                    reader = pd.read_csv(file_path, encoding="utf-8-sig", chunksize=500)
                    first_chunk = next(reader, None)
                    if first_chunk is None:
                        df_iter = None
                    else:
                        df_iter = itertools.chain([first_chunk], reader)
                        columns = list(first_chunk.columns)
                    encoding = "utf-8-sig"
                except Exception:
                    reader = pd.read_csv(file_path, encoding="gbk", chunksize=500)
                    first_chunk = next(reader, None)
                    if first_chunk is None:
                        df_iter = None
                    else:
                        df_iter = itertools.chain([first_chunk], reader)
                        columns = list(first_chunk.columns)
                    encoding = "gbk"
        except Exception as exc:
            return ImportResult(total=0, success=0, failed=0, errors=[str(exc)])
        if not df_iter:
            return ImportResult(total=0, success=0, failed=0, errors=[])

        def count_csv_rows() -> int:
            if file_path.suffix.lower() == ".xlsx":
                return total
            try:
                with file_path.open("r", encoding=encoding, errors="replace", newline="") as f:
                    row_count = max(sum(1 for _ in f) - 1, 0)
            except Exception:
                return total
            return row_count

        required_cols = {"比赛名称", "获奖日期", "赛事级别", "奖项等级"}
        if not required_cols.issubset(columns):
            missing = ", ".join(required_cols - set(columns))
            return ImportResult(total=0, success=0, failed=0, errors=[f"缺少列: {missing}"])

        total = count_csv_rows()
        success = 0
        errors: list[str] = []
        error_rows: list[dict] = []

        import time

        start_time = time.time()

        # flag 列映射：优先匹配 "label (key)"，其次 label
        flag_col_map: dict[str, str] = {}
        for flag in flag_defs:
            preferred = f"{flag.label} ({flag.key})"
            if preferred in columns:
                flag_col_map[flag.key] = preferred
            elif flag.label in columns:
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
            raw_date = row["获奖日期"]
            timestamp: object
            if isinstance(raw_date, pd.Timestamp):
                timestamp = raw_date
            elif isinstance(raw_date, py_datetime):
                timestamp = pd.Timestamp(raw_date)
            elif isinstance(raw_date, py_date):
                timestamp = pd.Timestamp(py_datetime(raw_date.year, raw_date.month, raw_date.day))
            elif isinstance(raw_date, (int, float)) and not pd.isna(raw_date):
                # Excel serial date (days since 1899-12-30 in pandas)
                ts = pd.to_datetime(raw_date, unit="D", origin="1899-12-30")
                if pd.isna(ts):
                    raise ValueError("获奖日期无法解析")
                timestamp = ts
            else:
                ts = pd.to_datetime(clean_cell(raw_date))
                if pd.isna(ts):
                    raise ValueError("获奖日期无法解析")
                timestamp = ts
            if cast(bool, pd.isna(timestamp)):
                raise ValueError("获奖日期无法解析")
            award = Award(
                competition_name=clean_cell(row["比赛名称"]),
                award_date=cast(pd.Timestamp, timestamp).date(),
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
            relative_paths = self._parse_items(clean_cell(row.get(RELATIVE_ATTACHMENT_HEADER, "")), sep=";")
            files = self._resolve_attachment_paths(attachment_paths, relative_paths)
            if files and not dry_run:
                self.attachments.save_attachments(award.id, award.competition_name, files, session=session)

            if not dry_run:
                self.db.refresh_award_fts(award.id, session=session)

            success += 1

        def process_frames(session: Session) -> None:
            row_index = 0
            for frame in df_iter or []:
                for idx, row in frame.iterrows():
                    try:
                        with session.begin_nested():
                            handle_row(session, row_index, row)
                    except Exception as exc:
                        errors.append(f"第 {row_index + 2} 行: {exc}")
                        error_rows.append({"行号": row_index + 2, "索引": idx, "错误": str(exc), **row.to_dict()})

                    row_index += 1
                    if progress_callback and row_index % 10 == 0:
                        elapsed = time.time() - start_time
                        rate = elapsed / max(row_index, 1)
                        remaining = max(total - row_index, 0) * rate
                        progress_callback(row_index, total, float(remaining))

        if dry_run:
            # Strict dry-run: no DB writes, no attachment copy, no ImportJob, no error file.
            with self.db.engine.connect() as connection:
                transaction = connection.begin()
                session = Session(bind=connection, expire_on_commit=False)
                try:
                    process_frames(session)
                finally:
                    session.close()
                    transaction.rollback()
        else:
            with self.db.session_scope() as session:
                process_frames(session)
                status = "success" if not errors else ("failed" if success <= 0 else "partial")
                session.add(
                    ImportJob(
                        filename=file_path.name,
                        status=status,
                        message="\n".join(errors) if errors else None,
                    )
                )

        error_file: Path | None = None
        if error_rows and not dry_run:
            error_file = file_path.parent / f"{file_path.stem}_errors.csv"
            try:
                pd.DataFrame(error_rows).to_csv(error_file, index=False, encoding="utf-8-sig")
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

    def _resolve_attachment_paths(self, absolute_paths: list[str], relative_paths: list[str]) -> list[Path]:
        root = self.attachments.ensure_root()
        resolved: list[Path] = []
        seen: set[str] = set()

        def add_path(path: Path) -> None:
            key = str(path.resolve()).lower() if path.exists() else str(path).lower()
            if key in seen:
                return
            seen.add(key)
            resolved.append(path)

        for raw in absolute_paths:
            if not raw:
                continue
            candidate = Path(raw)
            if candidate.exists():
                add_path(candidate)
                continue
            if not candidate.is_absolute():
                fallback = root / candidate
                if fallback.exists():
                    add_path(fallback)
                    continue
            if candidate.is_absolute():
                rel_candidate = Path(*candidate.parts[1:]) if candidate.drive else Path(str(candidate).lstrip("/\\"))
                fallback = root / rel_candidate
                if fallback.exists():
                    add_path(fallback)

        for raw in relative_paths:
            if not raw:
                continue
            candidate = root / Path(raw)
            if candidate.exists():
                add_path(candidate)

        return resolved

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
