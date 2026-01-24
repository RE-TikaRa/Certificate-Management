from __future__ import annotations

from pathlib import Path

from .config import BASE_DIR


def _resolve_git_dir(base_dir: Path) -> Path | None:
    git_dir = base_dir / ".git"
    if git_dir.is_dir():
        return git_dir
    if git_dir.is_file():
        try:
            content = git_dir.read_text(encoding="utf-8").strip()
        except Exception:
            return None
        if content.startswith("gitdir:"):
            return (base_dir / content.removeprefix("gitdir:").strip()).resolve()
    return None


def get_app_version() -> str:
    git_dir = _resolve_git_dir(BASE_DIR)
    if not git_dir:
        return "unknown"

    head_path = git_dir / "HEAD"
    try:
        head = head_path.read_text(encoding="utf-8").strip()
    except Exception:
        return "unknown"

    if head.startswith("ref:"):
        ref_path = git_dir / head.split(" ", 1)[1].strip()
        try:
            sha = ref_path.read_text(encoding="utf-8").strip()
        except Exception:
            return "unknown"
    else:
        sha = head

    if sha:
        return sha[:8]
    return "unknown"
