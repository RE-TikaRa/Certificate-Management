import logging
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session, sessionmaker

from ..config import DB_PATH
from .models import Base


class Database:
    def __init__(self) -> None:
        self.engine = create_engine(
            f"sqlite:///{DB_PATH}",
            echo=False,
            future=True,
            connect_args={"check_same_thread": False, "timeout": 30},
        )
        event.listen(self.engine, "connect", self._on_connect)
        self._session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    @staticmethod
    def _on_connect(dbapi_connection, _connection_record) -> None:
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()
        except Exception:
            logging.getLogger(__name__).warning("Failed to enable SQLite foreign_keys", exc_info=True)

    @staticmethod
    def _get_connection(session: Session) -> Connection:
        return session.connection()

    def initialize(self) -> None:
        Base.metadata.create_all(self.engine)
        self._apply_migrations()
        self._ensure_fts()
        self._rebuild_fts_if_empty()

    def reset(self) -> None:
        """
        清空当前数据库并重建空库。

        说明：
        - Windows 下删除 .db 文件经常因“文件被占用”失败（例如另一个进程仍持有连接）。
        - 这里改为在同一个文件内 DROP 掉所有对象后重新 initialize，避免依赖 unlink。
        """

        def _quote_ident(value: str) -> str:
            return '"' + value.replace('"', '""') + '"'

        self.engine.dispose()
        with self.engine.begin() as connection:
            connection.execute(text("PRAGMA foreign_keys=OFF"))
            rows = connection.execute(
                text(
                    "SELECT name, type FROM sqlite_master "
                    "WHERE name NOT LIKE 'sqlite_%' AND type IN ('trigger','view','table')"
                )
            ).fetchall()
            for kind in ("trigger", "view", "table"):
                for name, obj_type in rows:
                    if obj_type != kind:
                        continue
                    ident = _quote_ident(name)
                    if kind == "trigger":
                        connection.execute(text(f"DROP TRIGGER IF EXISTS {ident}"))
                    elif kind == "view":
                        connection.execute(text(f"DROP VIEW IF EXISTS {ident}"))
                    else:
                        connection.execute(text(f"DROP TABLE IF EXISTS {ident}"))
            connection.execute(text("PRAGMA foreign_keys=ON"))
        self.initialize()

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
            if "award_members" in tables:
                self._migrate_award_members_to_snapshot(connection, inspector)

    def _migrate_award_members_to_snapshot(self, connection, inspector) -> None:
        cols = {c["name"] for c in inspector.get_columns("award_members")}
        if "member_name" in cols and "id" in cols:
            return

        logging.getLogger(__name__).info("Migrating award_members to snapshot schema")
        connection.execute(text("PRAGMA foreign_keys=OFF"))
        try:
            connection.execute(text("DROP TABLE IF EXISTS award_members_new"))
            connection.execute(
                text(
                    """
                    CREATE TABLE award_members_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        award_id INTEGER NOT NULL,
                        member_id INTEGER,
                        member_name TEXT NOT NULL,
                        sort_order INTEGER NOT NULL DEFAULT 0,
                        FOREIGN KEY(award_id) REFERENCES awards(id) ON DELETE CASCADE,
                        FOREIGN KEY(member_id) REFERENCES team_members(id) ON DELETE SET NULL
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO award_members_new (award_id, member_id, member_name, sort_order)
                    SELECT am.award_id,
                           am.member_id,
                           COALESCE(tm.name, '') AS member_name,
                           COALESCE(am.sort_order, 0) AS sort_order
                    FROM award_members am
                    LEFT JOIN team_members tm ON tm.id = am.member_id
                    """
                )
            )
            connection.execute(text("DROP TABLE award_members"))
            connection.execute(text("ALTER TABLE award_members_new RENAME TO award_members"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_award_members_award_id ON award_members (award_id)"))
            connection.execute(
                text("CREATE INDEX IF NOT EXISTS ix_award_members_member_id ON award_members (member_id)")
            )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_award_members_award_sort "
                    "ON award_members (award_id, sort_order)"
                )
            )
        finally:
            connection.execute(text("PRAGMA foreign_keys=ON"))

    def _ensure_fts(self) -> None:
        """创建 FTS5 虚表（如果可用）"""
        try:
            with self.engine.begin() as connection:
                connection.execute(
                    text(
                        "CREATE VIRTUAL TABLE IF NOT EXISTS awards_fts USING fts5("
                        "competition_name, certificate_code, member_names, tokenize='unicode61')"
                    )
                )
                connection.execute(
                    text(
                        "CREATE VIRTUAL TABLE IF NOT EXISTS members_fts USING fts5("
                        "name, pinyin, student_id, phone, email, college, major, tokenize='unicode61')"
                    )
                )
        except Exception as exc:
            logging.getLogger(__name__).warning("FTS unavailable: %s", exc)

    def upsert_award_fts(
        self,
        award_id: int,
        competition_name: str,
        certificate_code: str | None,
        member_names: str,
        session: Session | None = None,
    ) -> None:
        try:

            def _work(connection: Connection) -> None:
                connection.execute(text("DELETE FROM awards_fts WHERE rowid = :id"), {"id": award_id})
                connection.execute(
                    text(
                        "INSERT INTO awards_fts(rowid, competition_name, certificate_code, member_names) "
                        "VALUES (:id, :c, :code, :m)"
                    ),
                    {"id": award_id, "c": competition_name, "code": certificate_code or "", "m": member_names},
                )

            if session is not None:
                _work(self._get_connection(session))
            else:
                with self.engine.begin() as connection:
                    _work(connection)
        except Exception:
            logging.getLogger(__name__).warning("Upsert awards_fts failed for id=%s", award_id, exc_info=True)

    def delete_award_fts(self, award_id: int, session: Session | None = None) -> None:
        try:
            if session is not None:
                self._get_connection(session).execute(
                    text("DELETE FROM awards_fts WHERE rowid = :id"), {"id": award_id}
                )
            else:
                with self.engine.begin() as connection:
                    connection.execute(text("DELETE FROM awards_fts WHERE rowid = :id"), {"id": award_id})
        except Exception:
            logging.getLogger(__name__).warning("Delete awards_fts failed for id=%s", award_id, exc_info=True)

    def search_awards_fts(self, query: str, limit: int = 100) -> list[int]:
        if not query:
            return []
        limit = max(1, min(limit, 500))
        try:
            with self.engine.begin() as connection:
                rows = connection.execute(
                    text("SELECT rowid FROM awards_fts WHERE awards_fts MATCH :q LIMIT :n"),
                    {"q": query, "n": limit},
                ).fetchall()
            return [int(row[0]) for row in rows]
        except Exception:
            logging.getLogger(__name__).warning("FTS search failed for query=%s", query, exc_info=True)
            return []

    def upsert_member_fts(
        self,
        member_id: int,
        *,
        name: str,
        pinyin: str | None = None,
        student_id: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        college: str | None = None,
        major: str | None = None,
        session: Session | None = None,
    ) -> None:
        try:

            def _work(connection: Connection) -> None:
                connection.execute(text("DELETE FROM members_fts WHERE rowid = :id"), {"id": member_id})
                connection.execute(
                    text(
                        "INSERT INTO members_fts(rowid, name, pinyin, student_id, phone, email, college, major) "
                        "VALUES (:id, :name, :pinyin, :sid, :phone, :email, :college, :major)"
                    ),
                    {
                        "id": member_id,
                        "name": name,
                        "pinyin": pinyin or "",
                        "sid": student_id or "",
                        "phone": phone or "",
                        "email": email or "",
                        "college": college or "",
                        "major": major or "",
                    },
                )

            if session is not None:
                _work(self._get_connection(session))
            else:
                with self.engine.begin() as connection:
                    _work(connection)
        except Exception:
            logging.getLogger(__name__).warning("Upsert members_fts failed for id=%s", member_id, exc_info=True)

    def delete_member_fts(self, member_id: int, session: Session | None = None) -> None:
        try:
            if session is not None:
                self._get_connection(session).execute(
                    text("DELETE FROM members_fts WHERE rowid = :id"), {"id": member_id}
                )
            else:
                with self.engine.begin() as connection:
                    connection.execute(text("DELETE FROM members_fts WHERE rowid = :id"), {"id": member_id})
        except Exception:
            logging.getLogger(__name__).warning("Delete members_fts failed for id=%s", member_id, exc_info=True)

    def search_members_fts(self, query: str, limit: int = 100) -> list[int]:
        if not query:
            return []
        limit = max(1, min(limit, 500))
        try:
            with self.engine.begin() as connection:
                rows = connection.execute(
                    text("SELECT rowid FROM members_fts WHERE members_fts MATCH :q LIMIT :n"),
                    {"q": query, "n": limit},
                ).fetchall()
            return [int(row[0]) for row in rows]
        except Exception:
            logging.getLogger(__name__).warning("FTS member search failed for query=%s", query, exc_info=True)
            return []

    def _ensure_column(self, connection, table: str, column: str, ddl: str) -> None:
        if self._column_exists(connection, table, column):
            return
        connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))

    def _rebuild_fts_if_empty(self) -> None:
        """若 FTS 表为空则一次性重建索引，避免升级后无搜索结果。"""
        try:
            with self.engine.begin() as connection:
                awards_count = connection.execute(text("SELECT count(1) FROM awards_fts")).scalar() or 0
                members_count = connection.execute(text("SELECT count(1) FROM members_fts")).scalar() or 0
        except Exception:
            logging.getLogger(__name__).warning("Check FTS table size failed", exc_info=True)
            return

        if awards_count == 0 or members_count == 0:
            try:
                with self.engine.begin() as connection:
                    base_awards = connection.execute(text("SELECT count(1) FROM awards")).scalar() or 0
                    base_members = connection.execute(text("SELECT count(1) FROM team_members")).scalar() or 0
                if base_awards == 0 and base_members == 0:
                    return
            except Exception:
                logging.getLogger(__name__).warning("Check base table size failed", exc_info=True)
            logging.getLogger(__name__).info(
                "Rebuilding FTS indexes (awards=%s, members=%s)", awards_count, members_count
            )
            try:
                with self.engine.begin() as connection:
                    if awards_count == 0:
                        rows = connection.execute(
                            text(
                                "SELECT a.id, a.competition_name, a.certificate_code, "
                                "GROUP_CONCAT(am.member_name, ' ') AS member_names "
                                "FROM awards a "
                                "LEFT JOIN award_members am ON am.award_id = a.id "
                                "GROUP BY a.id"
                            )
                        ).fetchall()
                        for row in rows:
                            connection.execute(
                                text(
                                    "INSERT OR REPLACE INTO awards_fts(rowid, competition_name, certificate_code, member_names) "
                                    "VALUES (:id, :c, :code, :m)"
                                ),
                                {
                                    "id": row.id,
                                    "c": row.competition_name,
                                    "code": row.certificate_code or "",
                                    "m": row.member_names or "",
                                },
                            )

                    if members_count == 0:
                        rows = connection.execute(
                            text(
                                "SELECT id, name, COALESCE(pinyin,''), COALESCE(student_id,''), "
                                "COALESCE(phone,''), COALESCE(email,''), COALESCE(college,''), COALESCE(major,'') "
                                "FROM team_members"
                            )
                        ).fetchall()
                        for row in rows:
                            connection.execute(
                                text(
                                    "INSERT OR REPLACE INTO members_fts(rowid, name, pinyin, student_id, phone, email, college, major) "
                                    "VALUES (:id, :name, :pinyin, :sid, :phone, :email, :college, :major)"
                                ),
                                {
                                    "id": row[0],
                                    "name": row[1],
                                    "pinyin": row[2],
                                    "sid": row[3],
                                    "phone": row[4],
                                    "email": row[5],
                                    "college": row[6],
                                    "major": row[7],
                                },
                            )
            except Exception:
                logging.getLogger(__name__).warning("Rebuild FTS failed", exc_info=True)

    def rebuild_fts(self) -> tuple[int, int]:
        """强制重建全文索引，返回重建后的记录数 (awards, members)。"""
        try:
            with self.engine.begin() as connection:
                connection.execute(text("DELETE FROM awards_fts"))
                connection.execute(text("DELETE FROM members_fts"))
        except Exception:
            logging.getLogger(__name__).warning("Clear FTS tables failed", exc_info=True)
        self._rebuild_fts_if_empty()
        try:
            with self.engine.begin() as connection:
                awards = connection.execute(text("SELECT count(1) FROM awards_fts")).scalar() or 0
                members = connection.execute(text("SELECT count(1) FROM members_fts")).scalar() or 0
            return int(awards), int(members)
        except Exception:
            logging.getLogger(__name__).warning("Read FTS counts failed after rebuild", exc_info=True)
            return 0, 0

    def _column_exists(self, connection, table: str, column: str) -> bool:
        pragma = connection.execute(text(f"PRAGMA table_info({table})")).fetchall()
        return any(row[1] == column for row in pragma)
