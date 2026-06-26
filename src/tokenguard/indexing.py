"""Index workspace documentation into the workspace thread for RAG."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Any

from tokenguard.engine import ingest_turn
from tokenguard.ollama_client import OllamaClient
from tokenguard.settings import AppSettings
from tokenguard.store import repository as repo
from tokenguard.threads import resolve_workspace_thread

DEFAULT_INDEX_GLOBS = (
    "README.md",
    "TROUBLESHOOTING.md",
    "docs/**/*.md",
    ".cursor/rules/**/*.mdc",
    ".cursor/rules/**/*.md",
)

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
}


def _doc_indexed(conn: sqlite3.Connection, thread_id: str, source_path: str, content_hash: str) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM messages
        WHERE thread_id = ? AND role = 'doc'
          AND json_extract(raw_refs, '$.source_path') = ?
          AND json_extract(raw_refs, '$.content_hash') = ?
        LIMIT 1
        """,
        (thread_id, source_path, content_hash),
    ).fetchone()
    return row is not None


def collect_index_files(workspace: Path, globs: tuple[str, ...]) -> list[Path]:
    root = workspace.resolve()
    found: set[Path] = set()
    for pattern in globs:
        for path in root.glob(pattern):
            if not path.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            found.add(path.resolve())
    return sorted(found)


async def index_workspace(
    conn: sqlite3.Connection,
    settings: AppSettings,
    ollama: OllamaClient,
    *,
    workspace: Path,
    globs: tuple[str, ...] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    root = workspace.resolve()
    tid, fp = resolve_workspace_thread(workspace_fingerprint_arg=str(root))
    repo.ensure_thread(
        conn,
        thread_id=tid,
        title=root.name,
        workspace_fingerprint=fp,
        provider="workspace-index",
    )
    patterns = globs or DEFAULT_INDEX_GLOBS
    files = collect_index_files(root, patterns)
    indexed: list[str] = []
    skipped: list[str] = []
    errors: list[dict[str, str]] = []

    for path in files:
        rel = str(path.relative_to(root))
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as e:
            errors.append({"path": rel, "error": str(e)})
            continue
        if not content.strip():
            skipped.append(rel)
            continue
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if not force and _doc_indexed(conn, tid, rel, content_hash):
            skipped.append(rel)
            continue
        body = f"# {rel}\n\n{content}"
        raw_refs = {"source_path": rel, "content_hash": content_hash, "kind": "workspace-doc"}
        await ingest_turn(
            conn,
            settings,
            ollama,
            thread_id=tid,
            role="doc",
            content=body,
            title=rel,
            workspace_fingerprint=fp,
            provider="workspace-index",
            raw_refs=raw_refs,
        )
        indexed.append(rel)

    return {
        "thread_id": tid,
        "workspace_fingerprint": fp,
        "workspace": str(root),
        "files_indexed": len(indexed),
        "files_skipped": len(skipped),
        "indexed": indexed,
        "skipped": skipped,
        "errors": errors,
    }
