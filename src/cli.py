from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from .app_context import bootstrap
from .config import DB_PATH
from .data.models import Award, TeamMember
from .services.github_backup_service import init_github_backup_repo, push_github_backup
from .version import get_app_version


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    handler: Callable[[argparse.Namespace], int] = args.handler
    return handler(args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="certificate-cli", description="荣誉证书管理系统命令行工具")
    parser.add_argument("-d", "--debug", action="store_true", help="启用调试日志")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    parser.set_defaults(handler=_cmd_help)

    subparsers = parser.add_subparsers(dest="command")

    sub = subparsers.add_parser("version", help="显示版本信息")
    sub.set_defaults(handler=_cmd_version)

    sub = subparsers.add_parser("status", help="显示数据库与数据概览")
    sub.set_defaults(handler=_cmd_status)

    backup = subparsers.add_parser("backup", help="备份相关命令")
    backup_sub = backup.add_subparsers(dest="backup_command")
    backup.set_defaults(handler=_cmd_help)

    sub = backup_sub.add_parser("create", help="创建本地 zip 备份")
    sub.add_argument("--no-attachments", action="store_true", help="不包含附件")
    sub.add_argument("--no-logs", action="store_true", help="不包含日志")
    sub.set_defaults(handler=_cmd_backup_create)

    sub = backup_sub.add_parser("list", help="列出本地备份")
    sub.set_defaults(handler=_cmd_backup_list)

    sub = backup_sub.add_parser("verify", help="验证备份文件")
    sub.add_argument("path", type=Path, help="备份 zip 路径")
    sub.set_defaults(handler=_cmd_backup_verify)

    sub = backup_sub.add_parser("restore", help="恢复备份文件")
    sub.add_argument("path", type=Path, help="备份 zip 路径")
    sub.add_argument("--no-attachments", action="store_true", help="不恢复附件")
    sub.add_argument("--no-logs", action="store_true", help="不恢复日志")
    sub.add_argument("--no-safety", action="store_true", help="恢复前不创建安全备份")
    sub.set_defaults(handler=_cmd_backup_restore)

    export = subparsers.add_parser("export", help="导出数据")
    export_sub = export.add_subparsers(dest="export_command")
    export.set_defaults(handler=_cmd_help)

    sub = export_sub.add_parser("awards", help="导出荣誉记录 CSV/XLSX")
    sub.add_argument("path", type=Path, help="导出路径，后缀建议为 .xlsx 或 .csv")
    sub.set_defaults(handler=_cmd_export_awards)

    github = subparsers.add_parser("github-backup", help="把本地备份同步到 GitHub 私有仓库")
    github_sub = github.add_subparsers(dest="github_command")
    github.set_defaults(handler=_cmd_help)

    sub = github_sub.add_parser("init", help="初始化一个本地 GitHub 备份仓库")
    sub.add_argument("repo", type=Path, help="本地备份仓库目录")
    sub.add_argument("--remote", help="GitHub 私有仓库地址，例如 git@github.com:user/repo.git")
    sub.set_defaults(handler=_cmd_github_init)

    sub = github_sub.add_parser("push", help="创建备份并推送到 GitHub 远端")
    sub.add_argument("repo", type=Path, help="本地备份仓库目录")
    sub.add_argument("--message", "-m", help="提交信息")
    sub.add_argument("--no-attachments", action="store_true", help="备份不包含附件")
    sub.add_argument("--no-logs", action="store_true", help="备份不包含日志")
    sub.set_defaults(handler=_cmd_github_push)

    return parser


def _cmd_help(args: argparse.Namespace) -> int:
    parser = _build_parser()
    if getattr(args, "command", None):
        parser.parse_args([args.command, "--help"])
    else:
        parser.print_help()
    return 0


def _cmd_version(args: argparse.Namespace) -> int:
    payload = {"version": get_app_version()}
    _emit(args, payload, f"Commit {payload['version']}")
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    ctx = bootstrap(debug=args.debug, start_scheduler=False)
    try:
        with ctx.db.session_scope() as session:
            awards = session.scalar(select(func.count(Award.id)).where(Award.deleted.is_(False))) or 0
            deleted_awards = session.scalar(select(func.count(Award.id)).where(Award.deleted.is_(True))) or 0
            members = session.scalar(select(func.count(TeamMember.id))) or 0
        latest = ctx.backup.get_latest_valid_backup()
        payload = {
            "database": str(DB_PATH),
            "database_exists": DB_PATH.exists(),
            "awards": int(awards),
            "deleted_awards": int(deleted_awards),
            "members": int(members),
            "backup_root": str(ctx.backup.backup_root),
            "latest_backup": str(latest.path) if latest else None,
        }
        lines = [
            f"数据库：{payload['database']}",
            f"数据库存在：{'是' if payload['database_exists'] else '否'}",
            f"荣誉：{payload['awards']} 条",
            f"回收站：{payload['deleted_awards']} 条",
            f"成员：{payload['members']} 位",
            f"备份目录：{payload['backup_root']}",
            f"最近有效备份：{payload['latest_backup'] or '无'}",
        ]
        _emit(args, payload, "\n".join(lines))
        return 0
    finally:
        ctx.backup.shutdown()


def _cmd_backup_create(args: argparse.Namespace) -> int:
    ctx = bootstrap(debug=args.debug, start_scheduler=False)
    try:
        path = ctx.backup.perform_backup(
            include_attachments=not args.no_attachments,
            include_logs=not args.no_logs,
        )
        payload = {"path": str(path), "size": path.stat().st_size}
        _emit(args, payload, f"备份已创建：{path}")
        return 0
    finally:
        ctx.backup.shutdown()


def _cmd_backup_list(args: argparse.Namespace) -> int:
    ctx = bootstrap(debug=args.debug, start_scheduler=False)
    try:
        backups = [
            {
                "path": str(item.path),
                "size": item.size,
                "size_mb": round(item.size_mb, 2),
                "created_time": item.created_time.isoformat(timespec="seconds"),
                "is_valid": item.is_valid,
                "error": item.error_msg,
            }
            for item in ctx.backup.list_backups()
        ]
        text = "\n".join(
            f"{item['created_time']}  {item['size_mb']:.2f} MB  {'OK' if item['is_valid'] else 'BAD'}  {item['path']}"
            for item in backups
        )
        _emit(args, backups, text or "暂无备份")
        return 0
    finally:
        ctx.backup.shutdown()


def _cmd_backup_verify(args: argparse.Namespace) -> int:
    ctx = bootstrap(debug=args.debug, start_scheduler=False)
    try:
        ok, message = ctx.backup.verify_backup(args.path)
        payload = {"path": str(args.path), "valid": ok, "message": message}
        _emit(args, payload, "备份有效" if ok else f"备份无效：{message}")
        return 0 if ok else 1
    finally:
        ctx.backup.shutdown()


def _cmd_backup_restore(args: argparse.Namespace) -> int:
    ctx = bootstrap(debug=args.debug, start_scheduler=False)
    try:
        ctx.backup.restore_backup(
            args.path,
            restore_attachments=not args.no_attachments,
            restore_logs=not args.no_logs,
            safety_backup=not args.no_safety,
            require_safety=not args.no_safety,
        )
        _emit(args, {"path": str(args.path)}, f"已恢复备份：{args.path}")
        return 0
    finally:
        ctx.backup.shutdown()


def _cmd_export_awards(args: argparse.Namespace) -> int:
    ctx = bootstrap(debug=args.debug, start_scheduler=False)
    try:
        path = ctx.importer.export_awards(args.path, ctx.awards.list_awards())
        payload = {"path": str(path), "size": path.stat().st_size}
        _emit(args, payload, f"荣誉已导出：{path}")
        return 0
    finally:
        ctx.backup.shutdown()


def _cmd_github_init(args: argparse.Namespace) -> int:
    repo = args.repo.resolve()
    init_github_backup_repo(repo, args.remote or "")
    _emit(args, {"repo": str(repo), "remote": args.remote}, f"GitHub 备份仓库已初始化：{repo}")
    return 0


def _cmd_github_push(args: argparse.Namespace) -> int:
    repo = args.repo.resolve()
    if not (repo / ".git").exists():
        raise SystemExit(f"不是 Git 仓库：{repo}")

    ctx = bootstrap(debug=args.debug, start_scheduler=False)
    try:
        result = push_github_backup(
            ctx.backup,
            repo,
            message=args.message or "",
            include_attachments=not args.no_attachments,
            include_logs=not args.no_logs,
        )
        payload = {"repo": str(result.repo_path), "backup": str(result.copied_path), "pushed": result.pushed}
        text = f"已推送备份：{result.copied_path}" if result.pushed else "没有新的备份需要提交"
        _emit(args, payload, text)
        return 0
    finally:
        ctx.backup.shutdown()


def _emit(args: argparse.Namespace, payload: Any, text: str) -> None:
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(text)


if __name__ == "__main__":
    sys.exit(main())
