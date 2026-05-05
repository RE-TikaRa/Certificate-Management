from pathlib import Path

from .config import BASE_DIR


def resolve_app_path(value: str | Path, default: str | Path) -> Path:
    raw = str(value or "").strip() or str(default)
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


def display_app_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(BASE_DIR.resolve()).as_posix()
    except ValueError:
        return str(resolved)
