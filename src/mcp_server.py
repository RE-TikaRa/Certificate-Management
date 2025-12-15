"""Model Context Protocol server for the Certificate Management app.

默认只读；通过环境变量 CERT_MCP_ALLOW_WRITE=1 可在后续扩展写能力。
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any, Literal, cast

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from .app_context import AppContext, bootstrap
from .config import ATTACHMENTS_DIR, BASE_DIR, DB_PATH, TEMPLATES_DIR
from .data.models import Attachment, Award, AwardMember, Base, Major, School, TeamMember


def _to_bool(value: str | bool | None, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return value.lower() in {"1", "true", "yes", "on"}


DEBUG = _to_bool(os.getenv("CERT_MCP_DEBUG"), False)
app: AppContext = bootstrap(debug=DEBUG)

ALLOW_WRITE = _to_bool(
    os.getenv("CERT_MCP_ALLOW_WRITE"),
    _to_bool(app.settings.get("mcp_allow_write", "false")),
)

def _parse_max_bytes(raw: str | None, fallback: int) -> int:
    if raw is None:
        return fallback
    try:
        return max(1024, int(raw))  # 至少 1KB，防止 0/负值
    except Exception:
        return fallback


MAX_BYTES = _parse_max_bytes(
    os.getenv("CERT_MCP_MAX_BYTES"),
    _parse_max_bytes(app.settings.get("mcp_max_bytes", "1048576"), 1_048_576),
)

Transport = Literal["stdio", "sse", "streamable-http"]
_transport_raw = os.getenv("CERT_MCP_TRANSPORT", "stdio")
if _transport_raw not in ("stdio", "sse", "streamable-http"):
    _transport_raw = "stdio"
TRANSPORT: Transport = cast(Transport, _transport_raw)
MCP_HOST = os.getenv("CERT_MCP_HOST") or app.settings.get("mcp_host", "127.0.0.1")
try:
    MCP_PORT = int(os.getenv("CERT_MCP_PORT") or app.settings.get("mcp_port", "8000"))
except Exception:
    MCP_PORT = 8000

if TRANSPORT != "stdio" and MCP_HOST not in {"127.0.0.1", "localhost", "::1"}:
    raise ValueError("MCP is local-only; host must be 127.0.0.1/localhost/::1")

if MCP_HOST == "localhost":
    MCP_HOST = "127.0.0.1"

mcp = FastMCP("certificate-management", host=MCP_HOST, port=MCP_PORT)


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def _error(code: str, message: str, detail: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": code, "message": message}
    if detail:
        payload["detail"] = detail
    return {"error": payload}


def _handle_tool_error(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, PermissionError):
        return _error("forbidden", str(exc))
    if isinstance(exc, ValueError):
        msg = str(exc)
        if "not found" in msg:
            return _error("not_found", msg)
        return _error("validation_error", msg)
    return _error("internal_error", "internal error", detail=str(exc) if DEBUG else None)


def _serialize_member(member: TeamMember) -> dict[str, Any]:
    return {
        "id": member.id,
        "name": member.name,
        "gender": member.gender,
        "id_card": member.id_card,
        "phone": member.phone,
        "student_id": member.student_id,
        "email": member.email,
        "school": member.school,
        "school_code": member.school_code,
        "major": member.major,
        "major_code": member.major_code,
        "class_name": member.class_name,
        "college": member.college,
        "pinyin": member.pinyin,
        "active": member.active,
        "sort_index": member.sort_index,
        "created_at": _iso(member.created_at),
        "updated_at": _iso(member.updated_at),
    }


def _serialize_attachment(att: Attachment) -> dict[str, Any]:
    return {
        "id": att.id,
        "award_id": att.award_id,
        "stored_name": att.stored_name,
        "original_name": att.original_name,
        "relative_path": att.relative_path,
        "file_md5": att.file_md5,
        "file_size": att.file_size,
        "deleted": att.deleted,
        "deleted_at": _iso(att.deleted_at),
        "created_at": _iso(att.created_at),
        "updated_at": _iso(att.updated_at),
    }


def _serialize_award(award: Award, *, with_members: bool = True, with_attachments: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": award.id,
        "competition_name": award.competition_name,
        "award_date": _iso(award.award_date),
        "level": award.level,
        "rank": award.rank,
        "certificate_code": award.certificate_code,
        "remarks": award.remarks,
        "attachment_folder": award.attachment_folder,
        "deleted": award.deleted,
        "deleted_at": _iso(award.deleted_at),
        "created_at": _iso(award.created_at),
        "updated_at": _iso(award.updated_at),
    }
    if with_members:
        payload["members"] = [_serialize_member(am.member) for am in award.award_members]
    if with_attachments:
        payload["attachments"] = [_serialize_attachment(att) for att in award.attachments]
    return payload


def _safe_attachment_path(relative_path: str) -> Path:
    base = ATTACHMENTS_DIR.resolve()
    target = (base / relative_path).resolve()
    if base not in target.parents and target != base:
        raise ValueError("attachment path is outside attachments directory")
    return target


@mcp.resource("docs://readme")
def read_readme() -> str:
    path = BASE_DIR / "README.md"
    return path.read_text(encoding="utf-8")


@mcp.resource("docs://agents")
def read_agents() -> str:
    path = BASE_DIR / "AGENTS.md"
    return path.read_text(encoding="utf-8")

@mcp.resource("schema://models")
def schema_models() -> str:
    """返回 SQLAlchemy 模型字段摘要（JSON）。"""
    models: dict[str, Any] = {}
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        table = mapper.local_table
        table_name = getattr(table, "name", None) or str(table)
        cols = []
        for col in table.columns:
            cols.append(
                {
                    "name": col.name,
                    "type": str(col.type),
                    "nullable": bool(col.nullable),
                    "primary_key": bool(col.primary_key),
                    "unique": bool(col.unique),
                    "default": str(col.default.arg) if col.default is not None else None,
                }
            )
        models[cls.__name__] = {"table": table_name, "columns": cols}
    return json.dumps(models, ensure_ascii=False, indent=2)


@mcp.resource("templates://awards_csv")
def template_awards_csv() -> str:
    """返回导入模板 CSV 内容。"""
    path = TEMPLATES_DIR / "awards_template.csv"
    return path.read_text(encoding="utf-8")


@mcp.tool()
def list_awards(
    limit: int = 50,
    offset: int = 0,
    include_deleted: bool = False,
    level: str | None = None,
    rank: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    order_by: str = "award_date_desc",
) -> dict[str, Any]:
    """分页列出荣誉记录（默认排除回收站）。"""
    try:
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        start: date | None = date.fromisoformat(start_date) if start_date else None
        end: date | None = date.fromisoformat(end_date) if end_date else None
        with app.db.session_scope() as session:
            stmt = select(Award)
            if not include_deleted:
                stmt = stmt.where(Award.deleted.is_(False))
            if level:
                stmt = stmt.where(Award.level == level)
            if rank:
                stmt = stmt.where(Award.rank == rank)
            if start:
                stmt = stmt.where(Award.award_date >= start)
            if end:
                stmt = stmt.where(Award.award_date <= end)

            if order_by == "award_date_asc":
                stmt = stmt.order_by(Award.award_date.asc(), Award.id.asc())
            elif order_by == "award_date_desc":
                stmt = stmt.order_by(Award.award_date.desc(), Award.id.desc())
            elif order_by == "competition_name_asc":
                stmt = stmt.order_by(Award.competition_name.asc(), Award.id.desc())
            elif order_by == "competition_name_desc":
                stmt = stmt.order_by(Award.competition_name.desc(), Award.id.desc())
            else:
                raise ValueError("invalid order_by")

            stmt = stmt.options(
                selectinload(Award.award_members).selectinload(AwardMember.member),
            ).offset(offset).limit(limit)
            items = session.scalars(stmt).all()
            return {"items": [_serialize_award(a) for a in items], "count": len(items)}
    except Exception as exc:
        return _handle_tool_error(exc)


@mcp.tool()
def get_award(award_id: int, include_deleted: bool = False) -> dict[str, Any]:
    """获取指定荣誉详情，含成员与附件元数据。"""
    try:
        with app.db.session_scope() as session:
            award = session.get(
                Award,
                award_id,
                options=[
                    selectinload(Award.award_members).selectinload(AwardMember.member),
                    selectinload(Award.attachments),
                ],
            )
            if not award or (award.deleted and not include_deleted):
                raise ValueError(f"award {award_id} not found")
            return _serialize_award(award, with_attachments=True)
    except Exception as exc:
        return _handle_tool_error(exc)


@mcp.tool()
def search_awards(
    query: str,
    limit: int = 50,
    include_deleted: bool = False,
    level: str | None = None,
    rank: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """使用 FTS5 搜索比赛名/证书号/成员姓名。"""
    try:
        if not query.strip():
            return {"items": [], "count": 0}
        limit = max(1, min(limit, 200))
        start: date | None = date.fromisoformat(start_date) if start_date else None
        end: date | None = date.fromisoformat(end_date) if end_date else None
        ids = app.db.search_awards_fts(query, limit=limit)
        if not ids:
            return {"items": [], "count": 0}
        id_rank = {award_id: idx for idx, award_id in enumerate(ids)}
        with app.db.session_scope() as session:
            stmt = select(Award).where(Award.id.in_(ids)).options(
                selectinload(Award.award_members).selectinload(AwardMember.member),
            )
            if not include_deleted:
                stmt = stmt.where(Award.deleted.is_(False))
            if level:
                stmt = stmt.where(Award.level == level)
            if rank:
                stmt = stmt.where(Award.rank == rank)
            if start:
                stmt = stmt.where(Award.award_date >= start)
            if end:
                stmt = stmt.where(Award.award_date <= end)
            awards = session.scalars(stmt).all()
            ordered = sorted(awards, key=lambda a: id_rank.get(a.id, 10**9))
            return {"items": [_serialize_award(a) for a in ordered], "count": len(ordered)}
    except Exception as exc:
        return _handle_tool_error(exc)


@mcp.tool()
def list_members(limit: int = 50, offset: int = 0, active_only: bool = True) -> dict[str, Any]:
    """成员列表。"""
    try:
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        with app.db.session_scope() as session:
            stmt = select(TeamMember).order_by(TeamMember.sort_index, TeamMember.name)
            if active_only:
                stmt = stmt.where(TeamMember.active.is_(True))
            members = session.scalars(stmt.offset(offset).limit(limit)).all()
            return {"items": [_serialize_member(m) for m in members], "count": len(members)}
    except Exception as exc:
        return _handle_tool_error(exc)


@mcp.tool()
def get_member(member_id: int) -> dict[str, Any]:
    """成员详情。"""
    try:
        with app.db.session_scope() as session:
            member = session.get(TeamMember, member_id)
            if not member:
                raise ValueError(f"member {member_id} not found")
            return _serialize_member(member)
    except Exception as exc:
        return _handle_tool_error(exc)


@mcp.tool()
def list_majors(limit: int = 50, offset: int = 0, keyword: str | None = None) -> dict[str, Any]:
    """专业列表，支持简单关键词过滤（名称/代码/拼音）。"""
    from sqlalchemy import or_

    try:
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        with app.db.session_scope() as session:
            stmt = select(Major).order_by(Major.code, Major.name)
            if keyword:
                pattern = f"%{keyword}%"
                stmt = stmt.where(
                    or_(
                        Major.name.like(pattern),
                        Major.code.like(pattern),
                        Major.pinyin.like(pattern),
                    )
                )
            majors = session.scalars(stmt.offset(offset).limit(limit)).all()
            items = [
                {
                    "id": m.id,
                    "name": m.name,
                    "code": m.code,
                    "pinyin": m.pinyin,
                    "category": m.category,
                    "discipline_code": m.discipline_code,
                    "discipline_name": m.discipline_name,
                    "class_code": m.class_code,
                    "class_name": m.class_name,
                }
                for m in majors
            ]
            return {"items": items, "count": len(items)}
    except Exception as exc:
        return _handle_tool_error(exc)


@mcp.tool()
def list_schools(limit: int = 50, offset: int = 0, keyword: str | None = None) -> dict[str, Any]:
    """学校列表，支持名称/代码模糊。"""
    from sqlalchemy import or_

    try:
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        with app.db.session_scope() as session:
            stmt = select(School).order_by(School.code, School.name)
            if keyword:
                pattern = f"%{keyword}%"
                stmt = stmt.where(or_(School.name.like(pattern), School.code.like(pattern)))
            schools = session.scalars(stmt.offset(offset).limit(limit)).all()
            items = [
                {
                    "id": s.id,
                    "name": s.name,
                    "code": s.code,
                    "pinyin": s.pinyin,
                    "region": s.region,
                }
                for s in schools
            ]
            return {"items": items, "count": len(items)}
    except Exception as exc:
        return _handle_tool_error(exc)


@mcp.tool()
def stats_summary() -> dict[str, Any]:
    """汇总统计与最近荣誉（最多 10 条）。"""
    try:
        summary = app.statistics.get_overview()
        latest = [_serialize_award(a) for a in summary.pop("latest_awards", [])]
        return {**summary, "latest_awards": latest}
    except Exception as exc:
        return _handle_tool_error(exc)


@mcp.tool()
def read_attachment(relative_path: str, offset: int = 0, length: int = MAX_BYTES) -> dict[str, Any]:
    """读取附件内容（Base64），默认最多 1MB。"""
    try:
        if not relative_path:
            raise ValueError("relative_path required")
        offset = max(0, offset)
        length = max(1, min(length, MAX_BYTES))
        path = _safe_attachment_path(relative_path)
        if not path.is_file():
            raise ValueError("attachment not found")
        file_size = path.stat().st_size
        if offset >= file_size:
            raise ValueError("offset out of range")
        with path.open("rb") as f:
            f.seek(offset)
            slice_ = f.read(length)
        mime_type, _encoding = mimetypes.guess_type(path.name)
        return {
            "path": str(path.relative_to(BASE_DIR)),
            "file_size": file_size,
            "mime_type": mime_type,
            "offset": offset,
            "length": len(slice_),
            "truncated": offset + length < file_size,
            "content_base64": base64.b64encode(slice_).decode(),
        }
    except Exception as exc:
        return _handle_tool_error(exc)


@mcp.tool()
def rebuild_fts() -> dict[str, int]:
    """重建全文索引（只读模式下返回 forbidden）。"""
    try:
        if not ALLOW_WRITE:
            raise PermissionError("write operations are disabled; set CERT_MCP_ALLOW_WRITE=1 to enable")
        awards, members = app.db.rebuild_fts()
        return {"awards": awards, "members": members}
    except Exception as exc:
        return _handle_tool_error(exc)


@mcp.tool()
def health() -> dict[str, Any]:
    """返回 MCP 运行状态与关键配置。"""
    try:
        fts_available = False
        fts_error: str | None = None
        try:
            with app.db.engine.begin() as connection:
                connection.execute(text("SELECT 1"))
                connection.execute(text("SELECT count(1) FROM awards_fts")).scalar()
            fts_available = True
        except Exception as exc:
            fts_error = str(exc)

        return {
            "name": "certificate-management",
            "base_dir": str(BASE_DIR),
            "db_path": str(DB_PATH),
            "attachments_dir": str(ATTACHMENTS_DIR),
            "read_only": not ALLOW_WRITE,
            "max_bytes": MAX_BYTES,
            "debug": DEBUG,
            "python": sys.version.split()[0],
            "fts": {"available": fts_available, "error": fts_error},
        }
    except Exception as exc:
        return _handle_tool_error(exc)


def main() -> None:
    mcp.run(transport=TRANSPORT)


if __name__ == "__main__":
    main()
