from __future__ import annotations

import tomllib

from .config import BASE_DIR


def get_app_version() -> str:
    pyproject_path = BASE_DIR / "pyproject.toml"
    try:
        data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except Exception:
        return "unknown"

    version = data.get("project", {}).get("version")
    if isinstance(version, str) and version.strip():
        return version.strip()
    return "unknown"
