from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from ..config import DB_PATH
from .models import Base


class Database:
    def __init__(self) -> None:
        self.engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)
        self._session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    def initialize(self) -> None:
        Base.metadata.create_all(self.engine)
        self._apply_migrations()

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _apply_migrations(self) -> None:
        with self.engine.begin() as connection:
            inspector = inspect(connection)
            tables = set(inspector.get_table_names())
            if "team_members" in tables:
                self._ensure_column(connection, "team_members", "school", "TEXT")
                self._ensure_column(connection, "team_members", "school_code", "TEXT")
                self._ensure_column(connection, "team_members", "major_code", "TEXT")
            if "majors" in tables:
                self._ensure_column(connection, "majors", "code", "TEXT")
                self._ensure_column(connection, "majors", "discipline_code", "TEXT")
                self._ensure_column(connection, "majors", "discipline_name", "TEXT")
                self._ensure_column(connection, "majors", "class_code", "TEXT")
                self._ensure_column(connection, "majors", "class_name", "TEXT")
            if "schools" in tables:
                self._ensure_column(connection, "schools", "region", "TEXT")

    def _ensure_column(self, connection, table: str, column: str, ddl: str) -> None:
        if self._column_exists(connection, table, column):
            return
        connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))

    def _column_exists(self, connection, table: str, column: str) -> bool:
        pragma = connection.execute(text(f"PRAGMA table_info({table})")).fetchall()
        return any(row[1] == column for row in pragma)
