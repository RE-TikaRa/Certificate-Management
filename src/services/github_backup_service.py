from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .backup_manager import BackupManager


@dataclass(frozen=True)
class GitHubBackupResult:
    archive_path: Path
    repo_path: Path
    copied_path: Path
    pushed: bool


def init_github_backup_repo(repo: Path, remote: str = "") -> None:
    repo = repo.resolve()
    repo.mkdir(parents=True, exist_ok=True)
    _run_git(["init"], cwd=repo)
    (repo / "backups").mkdir(exist_ok=True)

    readme = repo / "README.md"
    if not readme.exists():
        readme.write_text("# Certificate Management Backup\n\nPrivate backup repository.\n", encoding="utf-8")

    gitignore = repo / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*.tmp\n.DS_Store\nThumbs.db\n", encoding="utf-8")

    if remote.strip():
        remotes = _git_output(["remote"], cwd=repo).splitlines()
        if "origin" in remotes:
            _run_git(["remote", "set-url", "origin", remote], cwd=repo)
        else:
            _run_git(["remote", "add", "origin", remote], cwd=repo)


def push_github_backup(
    backup: BackupManager,
    repo: Path,
    *,
    message: str = "",
    include_attachments: bool | None = None,
    include_logs: bool | None = None,
) -> GitHubBackupResult:
    repo = repo.resolve()
    if not (repo / ".git").exists():
        raise RuntimeError(f"不是 Git 仓库：{repo}")

    archive = backup.perform_backup(include_attachments=include_attachments, include_logs=include_logs)
    dest_dir = repo / "backups"
    dest_dir.mkdir(exist_ok=True)
    dest = dest_dir / archive.name
    shutil.copy2(archive, dest)

    add_paths = ["backups"]
    for name in ("README.md", ".gitignore"):
        if (repo / name).exists():
            add_paths.append(name)
    _run_git(["add", *add_paths], cwd=repo)

    pushed = False
    if _has_staged_changes(repo):
        commit_message = message.strip() or f"backup: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        _run_git(["commit", "-m", commit_message], cwd=repo)
        _run_git(["push"], cwd=repo)
        pushed = True

    return GitHubBackupResult(archive_path=archive, repo_path=repo, copied_path=dest, pushed=pushed)


def _run_git(args: list[str], *, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True)


def _git_output(args: list[str], *, cwd: Path) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _has_staged_changes(repo: Path) -> bool:
    result = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=repo)
    return result.returncode != 0
