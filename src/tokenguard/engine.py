"""Orchestration: ingest, RAG answer, escalation pack."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import AsyncIterator
from typing import Any

import numpy as np

from tokenguard.context import retrieve_context
from tokenguard.metrics import (
    attach_totals,
    record_auto_escalate,
    record_cloud_assistant,
    record_escalate_pack,
    record_force_escalate,
    record_ingest_dedup,
    record_ingest_embeds,
    record_local_draft,
)
from tokenguard.ollama_client import OllamaClient
from tokenguard.router import draft_confidence, rough_token_count, should_force_escalate
from tokenguard.settings import AppSettings
from tokenguard.store import repository as repo
from tokenguard.text.chunking import chunk_text
from tokenguard.text.redact import redact_text
from tokenguard.threads import resolve_workspace_thread


def _embedding_to_blob(values: list[float]) -> tuple[bytes, int]:
    arr = np.array(values, dtype=np.float32)
    return arr.tobytes(), int(arr.shape[0])


async def ingest_turn(
    conn: sqlite3.Connection,
    settings: AppSettings,
    ollama: OllamaClient,
    *,
    thread_id: str | None,
    role: str,
    content: str,
    title: str,
    workspace_fingerprint: str,
    provider: str,
    model: str = "",
    raw_refs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    redacted = redact_text(content, settings.policy.redact_patterns)
    tid, fp = resolve_workspace_thread(thread_id, workspace_fingerprint)
    tid = repo.ensure_thread(
        conn,
        thread_id=tid,
        title=title,
        workspace_fingerprint=fp,
        provider=provider,
    )
    mid = repo.insert_message(
        conn,
        thread_id=tid,
        role=role,
        content=redacted,
        provider=provider,
        model=model,
        raw_refs=raw_refs,
    )
    pieces = chunk_text(
        redacted,
        settings.limits.chunk_size_chars,
        settings.limits.chunk_overlap_chars,
    )
    chunk_ids: list[str] = []
    for piece in pieces:
        emb = await ollama.embed(piece)
        blob, dim = _embedding_to_blob(emb)
        cid = repo.insert_chunk(
            conn,
            message_id=mid,
            thread_id=tid,
            text=piece,
            embedding=blob,
            embedding_dim=dim,
        )
        chunk_ids.append(cid)
    embed_tokens = record_ingest_embeds(
        conn,
        thread_id=tid,
        provider=provider,
        chunk_texts=pieces,
    )
    content_tokens = rough_token_count(redacted)
    conn.execute(
        "UPDATE messages SET tokens_in = ? WHERE id = ?",
        (content_tokens + embed_tokens, mid),
    )
    conn.commit()
    out: dict[str, Any] = {
        "thread_id": tid,
        "message_id": mid,
        "chunk_ids": chunk_ids,
        "chunks_indexed": len(chunk_ids),
        "metrics": {
            "tokens_embedded": embed_tokens,
            "tokens_content": content_tokens,
        },
    }
    if role == "assistant":
        out["metrics"]["cloud_estimate"] = record_cloud_assistant(
            conn,
            thread_id=tid,
            provider=provider,
            content=redacted,
        )
    return out


def _message_exists(conn: sqlite3.Connection, thread_id: str, role: str, content: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM messages WHERE thread_id = ? AND role = ? AND content = ? LIMIT 1",
        (thread_id, role, content),
    ).fetchone()
    return row is not None


async def _ensure_user_query_ingested(
    conn: sqlite3.Connection,
    settings: AppSettings,
    ollama: OllamaClient,
    *,
    query: str,
    thread_id: str | None,
    workspace_fingerprint: str = "",
    provider: str = "tokenguard",
) -> tuple[str | None, dict[str, Any] | None]:
    """Ingest user query if not already stored for this thread. Returns (thread_id, dedup_metrics)."""
    tid, fp = resolve_workspace_thread(thread_id, workspace_fingerprint)
    redacted = redact_text(query.strip(), settings.policy.redact_patterns)
    if not redacted:
        return tid, None
    if _message_exists(conn, tid, "user", redacted):
        dedup = record_ingest_dedup(conn, thread_id=tid, provider=provider, content=redacted)
        return tid, dedup
    out = await ingest_turn(
        conn,
        settings,
        ollama,
        thread_id=tid,
        role="user",
        content=query,
        title="",
        workspace_fingerprint=fp,
        provider=provider,
    )
    return str(out["thread_id"]), None


async def handle_query(
    conn: sqlite3.Connection,
    settings: AppSettings,
    ollama: OllamaClient,
    *,
    query: str,
    thread_id: str | None,
    workspace_fingerprint: str = "",
    provider: str = "tokenguard",
    ingest_assistant: str | None = None,
) -> dict[str, Any]:
    """Primary entry: ingest user query, RAG retrieve, optional assistant ingest."""
    tid, fp = resolve_workspace_thread(thread_id, workspace_fingerprint)
    dedup_metrics: dict[str, Any] | None = None
    if query.strip():
        tid, dedup_metrics = await _ensure_user_query_ingested(
            conn,
            settings,
            ollama,
            query=query,
            thread_id=tid,
            workspace_fingerprint=fp,
            provider=provider,
        )
    answer_out = await answer(
        conn,
        settings,
        ollama,
        query=query,
        thread_id=tid,
        skip_user_ingest=True,
        workspace_fingerprint=fp,
        provider=provider,
    )
    ingest_out: dict[str, Any] | None = None
    if ingest_assistant and ingest_assistant.strip():
        if not (
            tid
            and _message_exists(
                conn, tid, "assistant", redact_text(ingest_assistant, settings.policy.redact_patterns)
            )
        ):
            ingest_out = await ingest_turn(
                conn,
                settings,
                ollama,
                thread_id=tid,
                role="assistant",
                content=ingest_assistant,
                title="",
                workspace_fingerprint=fp,
                provider=provider,
            )
            cloud_m = record_cloud_assistant(
                conn,
                thread_id=tid,
                provider=provider,
                content=ingest_assistant,
            )
            ingest_out["metrics"] = {**ingest_out.get("metrics", {}), "cloud_estimate": cloud_m}
        else:
            dedup_a = record_ingest_dedup(
                conn,
                thread_id=tid,
                provider=provider,
                content=ingest_assistant,
            )
            ingest_out = {"thread_id": tid, "skipped": True, "reason": "duplicate", "metrics": dedup_a}
    turn_metrics = answer_out.get("metrics", {})
    if dedup_metrics:
        turn_metrics = {
            **turn_metrics,
            "ingest_dedup_saved": dedup_metrics.get("tokens_saved", 0),
        }
    metrics_out = attach_totals(conn, turn_metrics, thread_id=tid)
    ctx = answer_out.get("context_pack", {})
    return {
        "thread_id": tid,
        "workspace_fingerprint": fp,
        "context_pack": ctx,
        "policy": {
            "primary": "Use context_pack citations as prior project/memory context.",
            "code": "Still read source files for implementation and debugging.",
            "escalate": "Call tokenguard_escalate_pack for complex multi-step tasks.",
            "ingest": "Call tokenguard_ingest_turn(role=assistant) after your reply.",
        },
        "ingest": {"user": True, "dedup": dedup_metrics is not None},
        "answer": answer_out,
        "assistant_ingest": ingest_out,
        "metrics": metrics_out,
    }


async def answer(
    conn: sqlite3.Connection,
    settings: AppSettings,
    ollama: OllamaClient,
    *,
    query: str,
    thread_id: str | None,
    skip_user_ingest: bool = False,
    workspace_fingerprint: str = "",
    provider: str = "tokenguard",
) -> dict[str, Any]:
    q = redact_text(query.strip(), settings.policy.redact_patterns)
    tid, fp = resolve_workspace_thread(thread_id, workspace_fingerprint)
    if not skip_user_ingest and q:
        tid, _ = await _ensure_user_query_ingested(
            conn,
            settings,
            ollama,
            query=query,
            thread_id=tid,
            workspace_fingerprint=fp,
            provider=provider,
        )
    force, kw = should_force_escalate(q, settings.policy.always_escalate_keywords)
    if force:
        esc_metrics = record_force_escalate(
            conn,
            thread_id=tid,
            provider=provider,
            query=q,
            reason=f"policy_keyword:{kw}",
        )
        return {
            "mode": "escalate",
            "reason": f"policy_keyword:{kw}",
            "escalate_hint": "Call tokenguard_escalate_pack with the same thread_id before deep cloud reasoning.",
            "draft": "",
            "citations": [],
            "context_pack": {"citations": [], "formatted": "", "top_score": 0.0},
            "thread_id": tid,
            "workspace_fingerprint": fp,
            "rough_query_tokens": rough_token_count(q),
            "metrics": esc_metrics,
        }

    rag = await retrieve_context(conn, settings, ollama, query=q, thread_id=tid)
    citations = rag["citations"]
    context = rag["context"]
    embed_tokens = rag["rough_query_tokens"]

    system = (
        "You are TokenGuard's local hint generator. Summarize ONLY from the context blocks. "
        "One short paragraph. If insufficient, say 'escalate'."
    )
    user = f"Question:\n{q}\n\nContext:\n{context or '(none)'}"
    draft = await ollama.chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=min(256, settings.limits.max_local_answer_tokens),
    )
    draft_text = draft.strip()

    if settings.policy.auto_escalate:
        confidence = draft_confidence(q, draft_text)
        if confidence < settings.policy.confidence_threshold:
            esc_metrics = record_auto_escalate(
                conn,
                thread_id=tid,
                provider=provider,
                query=q,
                draft=draft_text,
                confidence=confidence,
            )
            return {
                "mode": "escalate",
                "reason": "auto_escalate_low_confidence",
                "confidence": confidence,
                "threshold": settings.policy.confidence_threshold,
                "draft": draft_text,
                "citations": citations,
                "context_pack": {
                    "citations": citations,
                    "formatted": rag["formatted"],
                    "top_score": rag["top_score"],
                },
                "thread_id": tid,
                "workspace_fingerprint": fp,
                "rough_query_tokens": rough_token_count(q),
                "metrics": esc_metrics,
            }

    draft_metrics = record_local_draft(
        conn,
        thread_id=tid,
        provider=provider,
        query=q,
        context=context,
        system_prompt=system,
        draft=draft_text,
        local_embed_tokens=embed_tokens,
    )
    context_pack = {
        "citations": citations,
        "formatted": rag["formatted"],
        "top_score": rag["top_score"],
    }
    return {
        "mode": "draft",
        "draft": draft_text,
        "draft_note": "Optional local hint — prefer context_pack over draft.",
        "citations": citations,
        "context_pack": context_pack,
        "thread_id": tid,
        "workspace_fingerprint": fp,
        "escalate_hint": (
            "Use context_pack in your answer. For complex work call tokenguard_escalate_pack."
        ),
        "rough_query_tokens": rough_token_count(q),
        "metrics": draft_metrics,
    }


async def answer_stream(
    conn: sqlite3.Connection,
    settings: AppSettings,
    ollama: OllamaClient,
    *,
    query: str,
    thread_id: str | None,
    workspace_fingerprint: str = "",
    provider: str = "tokenguard",
) -> AsyncIterator[str]:
    q = redact_text(query.strip(), settings.policy.redact_patterns)
    tid, fp = resolve_workspace_thread(thread_id, workspace_fingerprint)
    rag = await retrieve_context(conn, settings, ollama, query=q, thread_id=tid)
    context = rag["context"]
    system = (
        "You are TokenGuard's local hint generator. Summarize ONLY from the context blocks. "
        "One short paragraph. If insufficient, say 'escalate'."
    )
    user = f"Question:\n{q}\n\nContext:\n{context or '(none)'}"
    async for token in ollama.chat_stream(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=min(256, settings.limits.max_local_answer_tokens),
    ):
        yield token


async def escalate_pack(
    conn: sqlite3.Connection,
    settings: AppSettings,
    ollama: OllamaClient,
    *,
    query: str,
    thread_id: str | None,
    workspace_fingerprint: str = "",
    recent_message_limit: int = 12,
) -> dict[str, Any]:
    tid, fp = resolve_workspace_thread(thread_id, workspace_fingerprint)
    repo.ensure_thread(
        conn,
        thread_id=tid,
        title="",
        workspace_fingerprint=fp,
        provider="tokenguard",
    )
    q = redact_text(query.strip(), settings.policy.redact_patterns)
    rag = await retrieve_context(conn, settings, ollama, query=q, thread_id=tid)

    history_lines: list[str] = []
    full_history_text = ""
    msgs = repo.list_recent_messages(conn, tid, limit=recent_message_limit)
    for m in msgs:
        role = m.get("role", "")
        body = str(m.get("content", ""))[:2000]
        history_lines.append(f"{role}: {body}")
    full_history_text = "\n".join(history_lines)

    pack = {
        "query": q,
        "rag_context": rag["formatted"],
        "recent_turns": "\n".join(history_lines),
    }
    text = json.dumps(pack, ensure_ascii=False, indent=2)
    pack_metrics = record_escalate_pack(
        conn,
        thread_id=tid,
        provider="tokenguard",
        full_context_tokens=rough_token_count(full_history_text),
        pack_tokens=rough_token_count(text),
    )
    return {
        "pack_json": text,
        "rough_characters": len(text),
        "thread_id": tid,
        "workspace_fingerprint": fp,
        "metrics": pack_metrics,
    }
