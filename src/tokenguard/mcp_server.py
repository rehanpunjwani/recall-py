from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from tokenguard import engine
from tokenguard.app import open_connection
from tokenguard.indexing import index_workspace
from tokenguard.metrics import summary as metrics_summary
from tokenguard.ollama_client import OllamaClient
from tokenguard.settings import AppSettings
from tokenguard.threads import default_workspace_fingerprint

mcp = FastMCP(
    "TokenGuard",
    instructions=(
        "TokenGuard injects retrieved project context — do NOT ignore context_pack. "
        "On each user question: call tokenguard_handle_query (returns context_pack.citations). "
        "Ground answers in those citations; read source files for code work. "
        "For complex tasks call tokenguard_escalate_pack before deep reasoning. "
        "After your reply call tokenguard_ingest_turn(role=assistant). "
        "Run tokenguard_index once per repo if context is empty."
    ),
    log_level="ERROR",
)

_conn = None
_settings: AppSettings | None = None
_ollama: OllamaClient | None = None


def _bootstrap() -> tuple[AppSettings, OllamaClient]:
    global _conn, _settings, _ollama
    try:
        if _settings is None:
            cfg = os.environ.get("TOKENGUARD_CONFIG", "").strip()
            path = Path(cfg).expanduser() if cfg else None
            _settings = AppSettings.load(path if path and path.is_file() else None)
            print(f"TokenGuard: Loaded config (Ollama: {_settings.ollama.base_url})", file=sys.stderr)

        if _ollama is None:
            _ollama = OllamaClient(_settings.ollama)

        if _conn is None:
            _conn = open_connection(_settings)
            print(f"TokenGuard: Database ready at {_settings.resolved_db_path()}", file=sys.stderr)

        assert _settings is not None and _ollama is not None and _conn is not None
        return _settings, _ollama
    except Exception as e:
        print(f"TokenGuard FATAL: Bootstrap failed: {e}", file=sys.stderr)
        raise


def _connection():
    assert _conn is not None
    return _conn


def _workspace_fp(explicit: str) -> str:
    return explicit.strip() or default_workspace_fingerprint()


def _error_json(tool: str, e: Exception) -> str:
    print(f"{tool} failed: {e}", file=sys.stderr)
    return json.dumps(
        {
            "error": str(e),
            "hint": "Check that Ollama is running and models are pulled. Run `tokenguard doctor` for diagnostics.",
        },
        ensure_ascii=False,
    )


@mcp.tool()
async def tokenguard_handle_query(
    query: str,
    thread_id: str | None = None,
    workspace_fingerprint: str = "",
) -> str:
    """Ingest query, retrieve context_pack (citations), optional local hint. Returns unified workspace thread_id."""
    try:
        settings, ollama = _bootstrap()
        conn = _connection()
        out = await engine.handle_query(
            conn,
            settings,
            ollama,
            query=query,
            thread_id=thread_id,
            workspace_fingerprint=_workspace_fp(workspace_fingerprint),
            provider="mcp",
        )
        return json.dumps(out, ensure_ascii=False)
    except Exception as e:
        return _error_json("tokenguard_handle_query", e)


@mcp.tool()
async def tokenguard_answer_stream(
    query: str,
    thread_id: str | None = None,
    workspace_fingerprint: str = "",
) -> str:
    """Stream a local draft response token by token via MCP progress."""
    try:
        settings, ollama = _bootstrap()
        conn = _connection()
        tokens: list[str] = []
        async for token in engine.answer_stream(
            conn,
            settings,
            ollama,
            query=query,
            thread_id=thread_id,
            workspace_fingerprint=_workspace_fp(workspace_fingerprint),
        ):
            tokens.append(token)
        return "".join(tokens)
    except Exception as e:
        return _error_json("tokenguard_answer_stream", e)


@mcp.tool()
async def tokenguard_answer(
    query: str,
    thread_id: str | None = None,
    workspace_fingerprint: str = "",
) -> str:
    """Retrieve context_pack + local hint. Prefer tokenguard_handle_query for new questions."""
    try:
        settings, ollama = _bootstrap()
        conn = _connection()
        out = await engine.answer(
            conn,
            settings,
            ollama,
            query=query,
            thread_id=thread_id,
            workspace_fingerprint=_workspace_fp(workspace_fingerprint),
        )
        return json.dumps(out, ensure_ascii=False)
    except Exception as e:
        return _error_json("tokenguard_answer", e)


@mcp.tool()
async def tokenguard_ingest_turn(
    role: str,
    content: str,
    thread_id: str | None = None,
    title: str = "",
    workspace_fingerprint: str = "",
    provider: str = "",
    model: str = "",
) -> str:
    """Store one message after responding (especially role=assistant)."""
    try:
        settings, ollama = _bootstrap()
        conn = _connection()
        out = await engine.ingest_turn(
            conn,
            settings,
            ollama,
            thread_id=thread_id,
            role=role,
            content=content,
            title=title,
            workspace_fingerprint=_workspace_fp(workspace_fingerprint),
            provider=provider or "mcp",
            model=model,
        )
        return json.dumps(out, ensure_ascii=False)
    except Exception as e:
        return _error_json("tokenguard_ingest_turn", e)


@mcp.tool()
async def tokenguard_escalate_pack(
    query: str,
    thread_id: str | None = None,
    workspace_fingerprint: str = "",
) -> str:
    """Compact RAG + recent turns for cloud reasoning on complex tasks."""
    try:
        settings, ollama = _bootstrap()
        conn = _connection()
        out = await engine.escalate_pack(
            conn,
            settings,
            ollama,
            query=query,
            thread_id=thread_id,
            workspace_fingerprint=_workspace_fp(workspace_fingerprint),
        )
        return json.dumps(out, ensure_ascii=False)
    except Exception as e:
        return _error_json("tokenguard_escalate_pack", e)


@mcp.tool()
async def tokenguard_index(
    workspace_fingerprint: str = "",
    force: bool = False,
) -> str:
    """Index README, rules, and docs into workspace RAG memory. Run once per repo."""
    try:
        settings, ollama = _bootstrap()
        conn = _connection()
        root = Path(_workspace_fp(workspace_fingerprint))
        out = await index_workspace(
            conn,
            settings,
            ollama,
            workspace=root,
            force=force,
        )
        return json.dumps(out, ensure_ascii=False)
    except Exception as e:
        return _error_json("tokenguard_index", e)


@mcp.tool()
async def tokenguard_metrics(thread_id: str | None = None) -> str:
    """Return estimated token savings and usage breakdown (global or per thread_id)."""
    try:
        settings, _ollama = _bootstrap()
        conn = _connection()
        out = metrics_summary(conn, thread_id=thread_id)
        return json.dumps(out, ensure_ascii=False)
    except Exception as e:
        return _error_json("tokenguard_metrics", e)


def run_mcp() -> None:
    mcp.run(transport="stdio")
