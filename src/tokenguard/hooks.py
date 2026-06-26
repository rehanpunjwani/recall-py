"""Cursor hook handlers and shared thread resolution for automatic ingest."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from tokenguard.app import open_connection
from tokenguard.context import build_agent_context_message, retrieve_context
from tokenguard.engine import ingest_turn
from tokenguard.metrics import record_ingest_dedup
from tokenguard.ollama_client import OllamaClient
from tokenguard.settings import AppSettings
from tokenguard.text.redact import redact_text
from tokenguard.threads import (
    resolve_workspace_thread,
    workspace_fingerprint,
)


def _read_stdin_json() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    data = json.loads(raw)
    return data if isinstance(data, dict) else {}


def _extract_prompt(payload: dict[str, Any]) -> str:
    for key in ("prompt", "user_message", "message", "text", "content"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _extract_response(payload: dict[str, Any]) -> str:
    for key in ("response", "assistant_message", "agent_message", "text", "content", "message"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _message_exists(conn, thread_id: str, role: str, content: str) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM messages
        WHERE thread_id = ? AND role = ? AND content = ?
        LIMIT 1
        """,
        (thread_id, role, content),
    ).fetchone()
    return row is not None


async def _ingest_if_new(
    *,
    role: str,
    content: str,
    payload: dict[str, Any],
    provider: str,
) -> dict[str, Any] | None:
    if not content.strip():
        return None
    settings = AppSettings.load()
    conn = open_connection(settings)
    try:
        ollama = OllamaClient(settings.ollama)
        fp = workspace_fingerprint(payload)
        tid, fp = resolve_workspace_thread(workspace_fingerprint_arg=fp)
        redacted = redact_text(content, settings.policy.redact_patterns)
        if _message_exists(conn, tid, role, redacted):
            dedup = record_ingest_dedup(conn, thread_id=tid, provider=provider, content=redacted)
            return {"thread_id": tid, "skipped": True, "reason": "duplicate", "metrics": dedup}
        return await ingest_turn(
            conn,
            settings,
            ollama,
            thread_id=tid,
            role=role,
            content=content,
            title="cursor-auto",
            workspace_fingerprint=fp,
            provider=provider,
            model="",
        )
    finally:
        conn.close()


async def run_before_prompt() -> int:
    payload = _read_stdin_json()
    prompt = _extract_prompt(payload)
    fp = workspace_fingerprint(payload)
    tid, fp = resolve_workspace_thread(workspace_fingerprint_arg=fp)
    out: dict[str, Any] = {"thread_id": tid, "workspace_fingerprint": fp}

    if prompt:
        try:
            result = await _ingest_if_new(
                role="user",
                content=prompt,
                payload=payload,
                provider="cursor-hook",
            )
            if result:
                out["tokenguard_ingest"] = result
        except Exception as e:
            print(f"TokenGuard hook before-prompt ingest failed: {e}", file=sys.stderr)

        try:
            settings = AppSettings.load()
            conn = open_connection(settings)
            ollama = OllamaClient(settings.ollama)
            rag = await retrieve_context(conn, settings, ollama, query=prompt, thread_id=tid)
            out["agent_message"] = build_agent_context_message(
                thread_id=tid,
                workspace_fingerprint=fp,
                user_query=prompt,
                citations=rag["citations"],
                top_score=float(rag["top_score"]),
            )
            out["context_pack"] = {
                "citations": rag["citations"],
                "top_score": rag["top_score"],
            }
        except Exception as e:
            print(f"TokenGuard hook RAG failed: {e}", file=sys.stderr)
            out["agent_message"] = (
                f"TokenGuard (RAG unavailable: {e}). thread_id={tid!r}. "
                "Call MCP `tokenguard_handle_query` with workspace context. "
                "Run `tokenguard doctor` and `tokenguard index`."
            )
    else:
        out["agent_message"] = (
            f"TokenGuard active. thread_id={tid!r}. "
            "Use retrieved context from handle_query / hooks. "
            "Call `tokenguard_escalate_pack` for complex tasks."
        )

    print(json.dumps(out))
    return 0


async def run_after_response() -> int:
    payload = _read_stdin_json()
    response = _extract_response(payload)
    if response:
        try:
            await _ingest_if_new(
                role="assistant",
                content=response,
                payload=payload,
                provider="cursor-hook",
            )
        except Exception as e:
            print(f"TokenGuard hook after-response ingest failed: {e}", file=sys.stderr)
    print("{}")
    return 0


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python -m tokenguard.hooks before-prompt|after-response", file=sys.stderr)
        raise SystemExit(2)
    cmd = sys.argv[1]
    if cmd == "before-prompt":
        raise SystemExit(asyncio.run(run_before_prompt()))
    if cmd == "after-response":
        raise SystemExit(asyncio.run(run_after_response()))
    print(f"unknown hook command: {cmd}", file=sys.stderr)
    raise SystemExit(2)


if __name__ == "__main__":
    main()
