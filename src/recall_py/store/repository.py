from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from typing import Any

from recall_py.store.db import row_to_dict


def ensure_thread(
    conn: sqlite3.Connection,
    *,
    thread_id: str | None,
    title: str,
    workspace_fingerprint: str,
    provider: str,
) -> str:
    tid = thread_id or str(uuid.uuid4())
    now = time.time()
    conn.execute(
        """
        INSERT INTO threads (id, title, workspace_fingerprint, provider, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title = COALESCE(excluded.title, threads.title),
            workspace_fingerprint = COALESCE(NULLIF(excluded.workspace_fingerprint, ''), threads.workspace_fingerprint),
            provider = COALESCE(NULLIF(excluded.provider, ''), threads.provider)
        """,
        (tid, title or "", workspace_fingerprint, provider, now),
    )
    conn.commit()
    return tid


def insert_message(
    conn: sqlite3.Connection,
    *,
    thread_id: str,
    role: str,
    content: str,
    provider: str = "",
    model: str = "",
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    parent_id: str | None = None,
    raw_refs: dict[str, Any] | None = None,
    message_id: str | None = None,
) -> str:
    mid = message_id or str(uuid.uuid4())
    now = time.time()
    raw = json.dumps(raw_refs) if raw_refs is not None else None
    conn.execute(
        """
        INSERT INTO messages (
            id, thread_id, role, content, provider, model,
            tokens_in, tokens_out, parent_id, raw_refs, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            mid,
            thread_id,
            role,
            content,
            provider,
            model,
            tokens_in,
            tokens_out,
            parent_id,
            raw,
            now,
        ),
    )
    conn.commit()
    return mid


def insert_chunk(
    conn: sqlite3.Connection,
    *,
    message_id: str,
    thread_id: str,
    text: str,
    embedding: bytes | None,
    embedding_dim: int | None,
) -> str:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    cid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{message_id}:{h}"))
    now = time.time()
    try:
        conn.execute(
            """
            INSERT INTO chunks (
                id, message_id, thread_id, text, content_hash, embedding, embedding_dim, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (cid, message_id, thread_id, text, h, embedding, embedding_dim, now),
        )
        conn.commit()
        return cid
    except sqlite3.IntegrityError:
        conn.rollback()
        row = conn.execute(
            "SELECT id FROM chunks WHERE message_id = ? AND content_hash = ?",
            (message_id, h),
        ).fetchone()
        if row is None:
            raise
        return str(row[0])


def list_recent_messages(conn: sqlite3.Connection, thread_id: str, limit: int = 20) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM messages WHERE thread_id = ?
        ORDER BY created_at DESC LIMIT ?
        """,
        (thread_id, limit),
    ).fetchall()
    return [row_to_dict(r) for r in reversed(rows)]


def iter_chunks_with_embeddings(
    conn: sqlite3.Connection,
    *,
    thread_id: str | None = None,
) -> list[sqlite3.Row]:
    if thread_id:
        return conn.execute(
            """
            SELECT * FROM chunks
            WHERE thread_id = ? AND embedding IS NOT NULL
            """,
            (thread_id,),
        ).fetchall()
    return conn.execute("SELECT * FROM chunks WHERE embedding IS NOT NULL").fetchall()


def update_chunk_embedding(
    conn: sqlite3.Connection,
    chunk_id: str,
    embedding: bytes,
    dim: int,
) -> None:
    conn.execute(
        "UPDATE chunks SET embedding = ?, embedding_dim = ? WHERE id = ?",
        (embedding, dim, chunk_id),
    )
    conn.commit()


def proxy_cache_get(
    conn: sqlite3.Connection,
    request_hash: str,
    ttl_seconds: int = 86400,
) -> str | None:
    row = conn.execute(
        "SELECT response_json, created_at FROM proxy_cache WHERE request_hash = ?",
        (request_hash,),
    ).fetchone()
    if row is None:
        return None
    age = time.time() - float(row["created_at"])
    if age > ttl_seconds:
        conn.execute("DELETE FROM proxy_cache WHERE request_hash = ?", (request_hash,))
        conn.commit()
        return None
    return str(row["response_json"])


def proxy_cache_put(
    conn: sqlite3.Connection,
    request_hash: str,
    response_json: str,
    max_entries: int = 10000,
) -> None:
    now = time.time()
    conn.execute(
        """
        INSERT INTO proxy_cache(request_hash, response_json, created_at)
        VALUES (?, ?, ?)
        ON CONFLICT(request_hash) DO UPDATE SET
            response_json = excluded.response_json,
            created_at = excluded.created_at
        """,
        (request_hash, response_json, now),
    )
    conn.execute(
        """
        DELETE FROM proxy_cache WHERE request_hash IN (
            SELECT request_hash FROM proxy_cache
            ORDER BY created_at ASC
            LIMIT MAX(0, (SELECT COUNT(*) FROM proxy_cache) - ?)
        )
        """,
        (max_entries,),
    )
    conn.commit()


def insert_usage_event(
    conn: sqlite3.Connection,
    *,
    thread_id: str | None,
    event_type: str,
    provider: str = "",
    tokens_local_in: int = 0,
    tokens_local_out: int = 0,
    tokens_cloud_estimated: int = 0,
    tokens_saved: int = 0,
    metadata: dict[str, Any] | None = None,
    event_id: str | None = None,
) -> str:
    eid = event_id or str(uuid.uuid4())
    now = time.time()
    meta = json.dumps(metadata) if metadata is not None else None
    conn.execute(
        """
        INSERT INTO usage_events (
            id, thread_id, event_type, provider,
            tokens_local_in, tokens_local_out,
            tokens_cloud_estimated, tokens_saved,
            metadata_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            eid,
            thread_id,
            event_type,
            provider,
            tokens_local_in,
            tokens_local_out,
            tokens_cloud_estimated,
            tokens_saved,
            meta,
            now,
        ),
    )
    conn.commit()
    return eid


def usage_totals(conn: sqlite3.Connection, *, thread_id: str | None = None) -> dict[str, int]:
    if thread_id:
        row = conn.execute(
            """
            SELECT
                COALESCE(SUM(tokens_local_in), 0),
                COALESCE(SUM(tokens_local_out), 0),
                COALESCE(SUM(tokens_cloud_estimated), 0),
                COALESCE(SUM(tokens_saved), 0),
                COUNT(*)
            FROM usage_events WHERE thread_id = ?
            """,
            (thread_id,),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT
                COALESCE(SUM(tokens_local_in), 0),
                COALESCE(SUM(tokens_local_out), 0),
                COALESCE(SUM(tokens_cloud_estimated), 0),
                COALESCE(SUM(tokens_saved), 0),
                COUNT(*)
            FROM usage_events
            """
        ).fetchone()
    assert row is not None
    return {
        "tokens_local_in": int(row[0]),
        "tokens_local_out": int(row[1]),
        "tokens_cloud_estimated": int(row[2]),
        "tokens_saved": int(row[3]),
        "event_count": int(row[4]),
    }


def usage_by_event_type(
    conn: sqlite3.Connection,
    *,
    thread_id: str | None = None,
) -> list[dict[str, Any]]:
    if thread_id:
        rows = conn.execute(
            """
            SELECT
                event_type,
                COUNT(*) AS n,
                COALESCE(SUM(tokens_saved), 0) AS saved,
                COALESCE(SUM(tokens_local_in), 0) AS local_in,
                COALESCE(SUM(tokens_local_out), 0) AS local_out
            FROM usage_events
            WHERE thread_id = ?
            GROUP BY event_type
            ORDER BY saved DESC, n DESC
            """,
            (thread_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT
                event_type,
                COUNT(*) AS n,
                COALESCE(SUM(tokens_saved), 0) AS saved,
                COALESCE(SUM(tokens_local_in), 0) AS local_in,
                COALESCE(SUM(tokens_local_out), 0) AS local_out
            FROM usage_events
            GROUP BY event_type
            ORDER BY saved DESC, n DESC
            """
        ).fetchall()
    return [row_to_dict(r) for r in rows]
