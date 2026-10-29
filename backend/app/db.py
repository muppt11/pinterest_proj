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

-- Lightweight identity: no passwords. The cookie holds a random token; only its SHA-256 is stored.
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    token_sha256  TEXT NOT NULL UNIQUE,
    display_name  TEXT NOT NULL,
    prefs_json    TEXT NOT NULL DEFAULT '{}',
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- Group trips (feature 9)
CREATE TABLE IF NOT EXISTS trips (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    place_name    TEXT NOT NULL,
    latitude      REAL NOT NULL,
    longitude     REAL NOT NULL,
    start_date    TEXT NOT NULL,
    end_date      TEXT NOT NULL,
    coordinate    INTEGER NOT NULL DEFAULT 0,      -- "coordinate for photos" palette mode
    public_slug   TEXT UNIQUE,                     -- set while published; NULL = not public
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE TABLE IF NOT EXISTS trip_members (
    trip_id  INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role     TEXT NOT NULL CHECK (role IN ('owner', 'editor', 'viewer')),
    PRIMARY KEY (trip_id, user_id)
);
CREATE TABLE IF NOT EXISTS trip_invites (
    id            INTEGER PRIMARY KEY,
    trip_id       INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    token_sha256  TEXT NOT NULL UNIQUE,            -- only the hash is stored
    role          TEXT NOT NULL CHECK (role IN ('editor', 'viewer')),
    expires_at    TEXT NOT NULL,
    revoked       INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS trip_slots (
    id       INTEGER PRIMARY KEY,
    trip_id  INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    day      TEXT NOT NULL,                        -- ISO date within the trip
    label    TEXT NOT NULL                         -- e.g. "beach dinner"
);
CREATE TABLE IF NOT EXISTS trip_inspiration (
    id         INTEGER PRIMARY KEY,
    trip_id    INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    vector     BLOB NOT NULL,                      -- FashionCLIP embedding (float32)
    colors     TEXT NOT NULL,                      -- dominant colors JSON
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE TABLE IF NOT EXISTS trip_votes (
    slot_id  INTEGER NOT NULL REFERENCES trip_slots(id) ON DELETE CASCADE,
    item_id  TEXT NOT NULL,
    user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    value    INTEGER NOT NULL CHECK (value IN (-1, 1)),
    PRIMARY KEY (slot_id, item_id, user_id)
);
CREATE TABLE IF NOT EXISTS trip_notes (
    id             INTEGER PRIMARY KEY,
    trip_id        INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    user_id        INTEGER REFERENCES users(id) ON DELETE SET NULL,
    day            TEXT NOT NULL,
    text           TEXT NOT NULL,
    ai_suggestion  INTEGER NOT NULL DEFAULT 0,     -- drafted by the assistant; always labeled
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE TABLE IF NOT EXISTS trip_activity (
    id          INTEGER PRIMARY KEY,
    trip_id     INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    actor       TEXT NOT NULL,                     -- display name at the time
    text        TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
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
