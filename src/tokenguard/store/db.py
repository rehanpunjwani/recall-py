from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

CURRENT_SCHEMA_VERSION = 3


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def get_schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_meta'"
    ).fetchone()
    if row is None:
        return 0
    v = conn.execute("SELECT value FROM schema_meta WHERE key = 'version'").fetchone()
    if v is None:
        return 0
    try:
        return int(v[0])
    except (TypeError, ValueError):
        return 0


def _set_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT)"
    )
    conn.execute(
        "INSERT INTO schema_meta(key, value) VALUES('version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(version),),
    )


def migrate(conn: sqlite3.Connection) -> None:
    version = get_schema_version(conn)
    if version < 1:
        _migrate_v1(conn)
        version = 1
        _set_version(conn, version)
        conn.commit()
    if version < 2:
        _migrate_v2(conn)
        version = 2
        _set_version(conn, version)
        conn.commit()
    if version < 3:
        _migrate_v3(conn)
        version = 3
        _set_version(conn, version)
        conn.commit()
    if get_schema_version(conn) != CURRENT_SCHEMA_VERSION:
        raise RuntimeError(
            f"Unexpected schema version after migrate: expected {CURRENT_SCHEMA_VERSION}"
        )


def _migrate_v1(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS threads (
            id TEXT PRIMARY KEY,
            title TEXT,
            workspace_fingerprint TEXT NOT NULL DEFAULT '',
            provider TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            thread_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            provider TEXT NOT NULL DEFAULT '',
            model TEXT NOT NULL DEFAULT '',
            tokens_in INTEGER,
            tokens_out INTEGER,
            parent_id TEXT,
            raw_refs TEXT,
            created_at REAL NOT NULL,
            FOREIGN KEY(thread_id) REFERENCES threads(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id);

        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY,
            message_id TEXT NOT NULL,
            thread_id TEXT NOT NULL,
            text TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            embedding BLOB,
            embedding_dim INTEGER,
            created_at REAL NOT NULL,
            FOREIGN KEY(message_id) REFERENCES messages(id) ON DELETE CASCADE,
            FOREIGN KEY(thread_id) REFERENCES threads(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_chunks_thread ON chunks(thread_id);
        CREATE INDEX IF NOT EXISTS idx_chunks_message ON chunks(message_id);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_chunks_msg_hash ON chunks(message_id, content_hash);
        """
    )
    conn.commit()


def _migrate_v2(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS proxy_cache (
            request_hash TEXT PRIMARY KEY,
            response_json TEXT NOT NULL,
            created_at REAL NOT NULL
        );
        """
    )
    conn.commit()


def _migrate_v3(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS usage_events (
            id TEXT PRIMARY KEY,
            thread_id TEXT,
            event_type TEXT NOT NULL,
            provider TEXT NOT NULL DEFAULT '',
            tokens_local_in INTEGER NOT NULL DEFAULT 0,
            tokens_local_out INTEGER NOT NULL DEFAULT 0,
            tokens_cloud_estimated INTEGER NOT NULL DEFAULT 0,
            tokens_saved INTEGER NOT NULL DEFAULT 0,
            metadata_json TEXT,
            created_at REAL NOT NULL,
            FOREIGN KEY(thread_id) REFERENCES threads(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_usage_events_thread ON usage_events(thread_id);
        CREATE INDEX IF NOT EXISTS idx_usage_events_type ON usage_events(event_type);
        CREATE INDEX IF NOT EXISTS idx_usage_events_created ON usage_events(created_at);
        """
    )
    conn.commit()


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {k: row[k] for k in row.keys()}
