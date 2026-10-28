"""SQLite storage. One connection per request; the schema is created on first use."""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS boards (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    parent_id   INTEGER REFERENCES boards(id) ON DELETE CASCADE,  -- NULL = top-level board
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS boards_parent ON boards(parent_id);

CREATE TABLE IF NOT EXISTS saves (
    board_id  INTEGER NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
    item_id   TEXT NOT NULL,
    saved_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (board_id, item_id)
);
CREATE INDEX IF NOT EXISTS saves_item ON saves(item_id);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def get_db_path() -> Path:
    from app.config import get_settings

    return get_settings().data_dir / "moodboards.db"


def get_db() -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: a connection that commits on success and rolls back on error."""
    conn = connect(get_db_path())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
