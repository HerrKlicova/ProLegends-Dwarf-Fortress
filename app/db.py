"""Acceso a SQLite.

Una sola base de datos para todos los mundos. El XML se parsea una vez y a
partir de ahi todo son consultas.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from . import config


def connect(path: Optional[Path] = None, readonly: bool = False) -> sqlite3.Connection:
    config.ensure_dirs()
    db_path = Path(path or config.DB_PATH)
    conn = sqlite3.connect(db_path, timeout=30.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA cache_size = -64000")  # 64 MB de cache
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    schema = config.SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(schema)
    conn.execute(
        "INSERT OR REPLACE INTO schema_info(key, value) VALUES ('version', '1')"
    )


@contextmanager
def session(path: Optional[Path] = None) -> Iterator[sqlite3.Connection]:
    conn = connect(path)
    try:
        init_db(conn)
        yield conn
    finally:
        conn.close()


def rows_to_dicts(rows) -> list[dict]:
    return [dict(r) for r in rows]


def one(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> Optional[dict]:
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row is not None else None


def all_(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]
