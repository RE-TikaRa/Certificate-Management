from typing import Any

from sqlalchemy import select

from ..config import DEFAULT_SETTINGS
from ..data.database import Database
from ..data.models import Setting


class SettingsService:
    def __init__(self, db: Database):
        self.db = db
        self._cache: dict[str, str] = {}
        self._load_defaults()

    def _load_defaults(self) -> None:
        with self.db.session_scope() as session:
            stored = {row.key: row.value for row in session.scalars(select(Setting)).all()}
            to_insert = []
            for key, value in DEFAULT_SETTINGS.items():
                if key not in stored:
                    to_insert.append(Setting(key=key, value=value))
            if to_insert:
                session.add_all(to_insert)
            self._cache = {**DEFAULT_SETTINGS, **stored}

    def get(self, key: str, default: str | None = None) -> str:
        if key not in self._cache:
            value = DEFAULT_SETTINGS.get(key, default)
            if value is None:
                raise KeyError(key)
            self._cache[key] = value
        return self._cache[key]

    def set(self, key: str, value: Any) -> None:
        string_value = str(value)
        with self.db.session_scope() as session:
            setting = session.scalar(select(Setting).where(Setting.key == key))
            if setting:
                setting.value = string_value
            else:
                session.add(Setting(key=key, value=string_value))
        self._cache[key] = string_value

    def bulk_update(self, updates: dict[str, Any]) -> None:
        with self.db.session_scope() as session:
            for key, value in updates.items():
                string_value = str(value)
                setting = session.scalar(select(Setting).where(Setting.key == key))
                if setting:
                    setting.value = string_value
                else:
                    session.add(Setting(key=key, value=string_value))
                self._cache[key] = string_value
