"""Token savings estimation and usage event recording."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from recall_py.router import rough_token_count
from recall_py.store import repository as repo

# Rough budget for a cloud assistant reply when no actual usage is available.
DEFAULT_CLOUD_RESPONSE_BUDGET = 1024


def estimate_cloud_turn_tokens(
    *,
    query: str,
    context: str = "",
    response_budget: int = DEFAULT_CLOUD_RESPONSE_BUDGET,
) -> int:
    """Estimate cloud tokens for query + context + a typical assistant reply."""
    return rough_token_count(query) + rough_token_count(context) + response_budget


def estimate_local_embed_tokens(text: str) -> int:
    return rough_token_count(text)


def record_event(
    conn: sqlite3.Connection,
    *,
    event_type: str,
    thread_id: str | None = None,
    provider: str = "",
    tokens_local_in: int = 0,
    tokens_local_out: int = 0,
    tokens_cloud_estimated: int = 0,
    tokens_saved: int = 0,
    metadata: dict[str, Any] | None = None,
) -> str:
    saved = max(0, int(tokens_saved))
    return repo.insert_usage_event(
        conn,
        thread_id=thread_id,
        event_type=event_type,
        provider=provider,
        tokens_local_in=max(0, int(tokens_local_in)),
        tokens_local_out=max(0, int(tokens_local_out)),
        tokens_cloud_estimated=max(0, int(tokens_cloud_estimated)),
        tokens_saved=saved,
        metadata=metadata,
    )


def record_local_draft(
    conn: sqlite3.Connection,
    *,
    thread_id: str | None,
    provider: str,
    query: str,
    context: str,
    system_prompt: str,
    draft: str,
    local_embed_tokens: int,
) -> dict[str, Any]:
    local_in = (
        rough_token_count(system_prompt) + rough_token_count(context) + rough_token_count(query) + local_embed_tokens
    )
    local_out = rough_token_count(draft)
    cloud_est = estimate_cloud_turn_tokens(query=query, context=context)
    local_total = local_in + local_out
    tokens_saved = max(0, cloud_est - local_total) if draft.strip() else 0
    record_event(
        conn,
        event_type="local_draft",
        thread_id=thread_id,
        provider=provider,
        tokens_local_in=local_in,
        tokens_local_out=local_out,
        tokens_cloud_estimated=cloud_est,
        tokens_saved=tokens_saved,
        metadata={"mode": "draft"},
    )
    return turn_metrics(local_in, local_out, cloud_est, tokens_saved)


def record_auto_escalate(
    conn: sqlite3.Connection,
    *,
    thread_id: str | None,
    provider: str,
    query: str,
    draft: str,
    confidence: float,
) -> dict[str, Any]:
    cloud_est = estimate_cloud_turn_tokens(query=query)
    local_out = rough_token_count(draft)
    record_event(
        conn,
        event_type="auto_escalate",
        thread_id=thread_id,
        provider=provider,
        tokens_local_out=local_out,
        tokens_cloud_estimated=cloud_est,
        tokens_saved=0,
        metadata={"confidence": confidence, "reason": "low_confidence"},
    )
    return turn_metrics(0, local_out, cloud_est, 0)


def record_force_escalate(
    conn: sqlite3.Connection,
    *,
    thread_id: str | None,
    provider: str,
    query: str,
    reason: str,
) -> dict[str, Any]:
    cloud_est = estimate_cloud_turn_tokens(query=query)
    record_event(
        conn,
        event_type="force_escalate",
        thread_id=thread_id,
        provider=provider,
        tokens_cloud_estimated=cloud_est,
        tokens_saved=0,
        metadata={"reason": reason},
    )
    return turn_metrics(0, 0, cloud_est, 0)


def record_ingest_dedup(
    conn: sqlite3.Connection,
    *,
    thread_id: str | None,
    provider: str,
    content: str,
) -> dict[str, Any]:
    saved = estimate_local_embed_tokens(content)
    record_event(
        conn,
        event_type="ingest_dedup",
        thread_id=thread_id,
        provider=provider,
        tokens_saved=saved,
        metadata={"chars": len(content)},
    )
    return turn_metrics(0, 0, 0, saved)


def record_ingest_embeds(
    conn: sqlite3.Connection,
    *,
    thread_id: str | None,
    provider: str,
    chunk_texts: list[str],
) -> int:
    total = sum(estimate_local_embed_tokens(t) for t in chunk_texts)
    if total <= 0:
        return 0
    record_event(
        conn,
        event_type="local_embed",
        thread_id=thread_id,
        provider=provider,
        tokens_local_in=total,
        tokens_saved=0,
        metadata={"chunks": len(chunk_texts)},
    )
    return total


def record_escalate_pack(
    conn: sqlite3.Connection,
    *,
    thread_id: str | None,
    provider: str,
    full_context_tokens: int,
    pack_tokens: int,
) -> dict[str, Any]:
    saved = max(0, full_context_tokens - pack_tokens)
    record_event(
        conn,
        event_type="escalate_pack",
        thread_id=thread_id,
        provider=provider,
        tokens_cloud_estimated=pack_tokens,
        tokens_saved=saved,
        metadata={
            "full_context_tokens": full_context_tokens,
            "pack_tokens": pack_tokens,
        },
    )
    return turn_metrics(0, 0, pack_tokens, saved)


def record_cloud_assistant(
    conn: sqlite3.Connection,
    *,
    thread_id: str | None,
    provider: str,
    content: str,
    rag_context_tokens: int = 0,
) -> dict[str, Any]:
    """Record estimated cloud tokens for an assistant reply (baseline for comparison)."""
    out_tokens = rough_token_count(content)
    in_tokens = rag_context_tokens + out_tokens // 2
    record_event(
        conn,
        event_type="cloud_assistant",
        thread_id=thread_id,
        provider=provider,
        tokens_local_in=0,
        tokens_local_out=out_tokens,
        tokens_cloud_estimated=in_tokens + out_tokens,
        tokens_saved=0,
        metadata={"note": "cloud_usage_estimate"},
    )
    return turn_metrics(in_tokens, out_tokens, in_tokens + out_tokens, 0)


def record_proxy_cache_hit(
    conn: sqlite3.Connection,
    *,
    cached_json: str,
) -> dict[str, Any]:
    usage = _parse_openai_usage(cached_json)
    saved = usage.get("total_tokens", 0) or rough_token_count(cached_json) // 8
    record_event(
        conn,
        event_type="proxy_cache_hit",
        provider="proxy",
        tokens_cloud_estimated=saved,
        tokens_saved=saved,
        metadata=usage,
    )
    return turn_metrics(0, 0, saved, saved)


def record_proxy_local_first(
    conn: sqlite3.Connection,
    *,
    query: str,
    context: str,
    draft: str,
) -> dict[str, Any]:
    cloud_est = estimate_cloud_turn_tokens(query=query, context=context)
    local_out = rough_token_count(draft)
    saved = max(0, cloud_est - local_out)
    record_event(
        conn,
        event_type="proxy_local_first",
        provider="proxy",
        tokens_local_out=local_out,
        tokens_cloud_estimated=cloud_est,
        tokens_saved=saved,
        metadata={"mode": "try_local_first"},
    )
    return turn_metrics(0, local_out, cloud_est, saved)


def record_proxy_compress(
    conn: sqlite3.Connection,
    *,
    chars_removed: int,
) -> dict[str, Any]:
    saved = max(0, chars_removed // 4)
    if saved <= 0:
        return turn_metrics(0, 0, 0, 0)
    record_event(
        conn,
        event_type="proxy_compress",
        provider="proxy",
        tokens_saved=saved,
        metadata={"chars_removed": chars_removed},
    )
    return turn_metrics(0, 0, 0, saved)


def turn_metrics(
    local_in: int,
    local_out: int,
    cloud_estimated: int,
    tokens_saved: int,
) -> dict[str, Any]:
    return {
        "tokens_local_in": local_in,
        "tokens_local_out": local_out,
        "tokens_cloud_estimated": cloud_estimated,
        "tokens_saved": max(0, tokens_saved),
    }


def summary(conn: sqlite3.Connection, *, thread_id: str | None = None) -> dict[str, Any]:
    totals = repo.usage_totals(conn, thread_id=thread_id)
    by_type = repo.usage_by_event_type(conn, thread_id=thread_id)
    return {
        "totals": totals,
        "by_event_type": by_type,
        "note": (
            "Savings are estimates (chars/4). local_draft = avoided full cloud turn; "
            "escalate_pack = compact context vs full history; ingest_dedup = skipped embed work."
        ),
    }


def attach_totals(conn: sqlite3.Connection, turn: dict[str, Any], *, thread_id: str | None) -> dict[str, Any]:
    out = dict(turn)
    out["session_totals"] = repo.usage_totals(conn, thread_id=thread_id)
    out["global_totals"] = repo.usage_totals(conn, thread_id=None)
    return out


def _parse_openai_usage(cached_json: str) -> dict[str, Any]:
    try:
        data = json.loads(cached_json)
    except json.JSONDecodeError:
        return {}
    usage = data.get("usage")
    if not isinstance(usage, dict):
        return {}
    return {
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
    }
