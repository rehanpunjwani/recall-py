"""RAG retrieval and agent-facing context formatting."""

from __future__ import annotations

import sqlite3
from typing import Any

from recall_py.ollama_client import OllamaClient
from recall_py.retrieve import build_ann_index, top_k_chunks
from recall_py.router import rough_token_count
from recall_py.settings import AppSettings


def format_context_injection(
    citations: list[dict[str, Any]],
    *,
    max_chars: int = 6000,
) -> str:
    if not citations:
        return (
            "(No indexed context yet. Run `recall-py index` in the repo root, "
            "then retry. Hooks and MCP share this workspace memory.)"
        )
    blocks: list[str] = []
    for c in citations:
        cid = c.get("chunk_id", "?")
        score = float(c.get("score", 0.0))
        text = str(c.get("text") or c.get("preview") or "")
        blocks.append(f"[{cid} score={score:.2f}]\n{text}")
    body = "\n\n".join(blocks)
    if len(body) > max_chars:
        body = body[:max_chars] + "\n...[truncated by RecallPy]"
    return body


def build_agent_context_message(
    *,
    thread_id: str,
    workspace_fingerprint: str,
    user_query: str,
    citations: list[dict[str, Any]],
    top_score: float,
) -> str:
    formatted = format_context_injection(citations)
    lines = [
        "RecallPy — use this retrieved context before answering.",
        f"thread_id={thread_id!r} workspace={workspace_fingerprint!r}",
        "",
        "=== RETRIEVED CONTEXT (cite when relevant) ===",
        formatted,
        "=== END CONTEXT ===",
        "",
        f"User message: {user_query}",
        "",
    ]
    if top_score >= 0.7:
        lines.append(
            "Policy: High-confidence citations above — ground your answer in them. "
            "Still read source files for code changes."
        )
    elif top_score >= 0.4:
        lines.append(
            "Policy: Partial context match — combine citations with file reads. "
            "Call MCP `recall_py_escalate_pack` for complex multi-step work."
        )
    else:
        lines.append(
            "Policy: Weak context match — read project files. "
            "Run `recall-py index` if docs are missing. "
            "Use `recall_py_escalate_pack` before heavy reasoning."
        )
    lines.append(
        f"After your final reply, call MCP `recall_py_ingest_turn` with role=assistant and thread_id={thread_id!r}."
    )
    return "\n".join(lines)


async def retrieve_context(
    conn: sqlite3.Connection,
    settings: AppSettings,
    ollama: OllamaClient,
    *,
    query: str,
    thread_id: str | None,
) -> dict[str, Any]:
    q = query.strip()
    if not q:
        return {
            "citations": [],
            "context": "",
            "formatted": format_context_injection([]),
            "top_score": 0.0,
            "rough_query_tokens": 0,
        }
    q_emb = await ollama.embed(q)
    k = settings.limits.max_chunks_for_prompt
    ann_index = build_ann_index(conn, thread_id=thread_id)
    ranked = top_k_chunks(conn, q_emb, k=k, thread_id=thread_id, ann_index=ann_index)
    citations: list[dict[str, Any]] = []
    context_blocks: list[str] = []
    top_score = 0.0
    for score, row in ranked:
        top_score = max(top_score, score)
        cid = str(row["id"])
        text = str(row["text"])
        citations.append(
            {
                "chunk_id": cid,
                "score": score,
                "text": text,
                "preview": text[:240],
            }
        )
        context_blocks.append(f"[{cid}]\n{text}")
    context = "\n\n".join(context_blocks) if context_blocks else ""
    return {
        "citations": citations,
        "context": context,
        "formatted": format_context_injection(citations),
        "top_score": top_score,
        "rough_query_tokens": rough_token_count(q),
    }
