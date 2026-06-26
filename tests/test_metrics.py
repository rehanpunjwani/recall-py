from unittest.mock import AsyncMock, patch

import pytest

from recall_py.app import open_connection
from recall_py.engine import answer, escalate_pack, handle_query
from recall_py.metrics import (
    record_ingest_dedup,
    record_local_draft,
    summary,
)
from recall_py.ollama_client import OllamaClient
from recall_py.settings import AppSettings
from recall_py.store.db import CURRENT_SCHEMA_VERSION, get_schema_version


def test_schema_includes_usage_events(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("RECALL_PY_CONFIG", raising=False)
    settings = AppSettings.load()
    conn = open_connection(settings)
    assert get_schema_version(conn) == CURRENT_SCHEMA_VERSION
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "usage_events" in tables


def test_record_local_draft_and_summary(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("RECALL_PY_CONFIG", raising=False)
    settings = AppSettings.load()
    conn = open_connection(settings)

    turn = record_local_draft(
        conn,
        thread_id=None,
        provider="test",
        query="What is RecallPy?",
        context="[abc]\nRecallPy saves tokens.",
        system_prompt="You are helpful.",
        draft="RecallPy is a local cache.",
        local_embed_tokens=10,
    )
    assert turn["tokens_saved"] >= 0
    assert turn["tokens_local_out"] > 0

    data = summary(conn)
    assert data["totals"]["event_count"] == 1
    assert data["totals"]["tokens_saved"] == turn["tokens_saved"]
    assert data["by_event_type"][0]["event_type"] == "local_draft"


def test_ingest_dedup_records_savings(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("RECALL_PY_CONFIG", raising=False)
    settings = AppSettings.load()
    conn = open_connection(settings)

    dedup = record_ingest_dedup(
        conn,
        thread_id=None,
        provider="hook",
        content="duplicate user message here",
    )
    assert dedup["tokens_saved"] > 0
    data = summary(conn)
    assert any(row["event_type"] == "ingest_dedup" for row in data["by_event_type"])


@pytest.mark.asyncio
async def test_handle_query_returns_metrics(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("RECALL_PY_CONFIG", raising=False)
    settings = AppSettings.load()
    conn = open_connection(settings)
    ollama = OllamaClient(settings.ollama)

    with (
        patch.object(OllamaClient, "embed", AsyncMock(return_value=[0.1] * 8)),
        patch.object(OllamaClient, "chat", AsyncMock(return_value="draft text")),
    ):
        out = await handle_query(
            conn,
            settings,
            ollama,
            query="What is RecallPy?",
            thread_id=None,
            workspace_fingerprint=str(tmp_path),
        )

    assert "metrics" in out
    assert "context_pack" in out
    assert out["metrics"]["session_totals"]["event_count"] >= 1
    assert out["answer"]["metrics"]["tokens_local_out"] > 0


@pytest.mark.asyncio
async def test_answer_dedup_skips_reingest_metrics(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("RECALL_PY_CONFIG", raising=False)
    settings = AppSettings.load()
    conn = open_connection(settings)
    ollama = OllamaClient(settings.ollama)

    with (
        patch.object(OllamaClient, "embed", AsyncMock(return_value=[0.1] * 8)),
        patch.object(OllamaClient, "chat", AsyncMock(return_value="draft")),
    ):
        first = await handle_query(conn, settings, ollama, query="same question", thread_id=None)
        second = await handle_query(
            conn,
            settings,
            ollama,
            query="same question",
            thread_id=first["thread_id"],
        )

    assert second["ingest"]["dedup"] is True
    assert second["metrics"].get("ingest_dedup_saved", 0) > 0


@pytest.mark.asyncio
async def test_escalate_pack_metrics(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("RECALL_PY_CONFIG", raising=False)
    settings = AppSettings.load()
    conn = open_connection(settings)
    ollama = OllamaClient(settings.ollama)

    with patch.object(OllamaClient, "embed", AsyncMock(return_value=[0.1] * 8)):
        out = await escalate_pack(
            conn,
            settings,
            ollama,
            query="help",
            thread_id=None,
            workspace_fingerprint=str(tmp_path),
        )

    assert "metrics" in out
    assert "tokens_saved" in out["metrics"]


@pytest.mark.asyncio
async def test_answer_includes_metrics(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("RECALL_PY_CONFIG", raising=False)
    settings = AppSettings.load()
    conn = open_connection(settings)
    ollama = OllamaClient(settings.ollama)

    with (
        patch.object(OllamaClient, "embed", AsyncMock(return_value=[0.1] * 8)),
        patch.object(OllamaClient, "chat", AsyncMock(return_value="short draft")),
    ):
        out = await answer(conn, settings, ollama, query="hello", thread_id=None)

    assert out["mode"] == "draft"
    assert out["metrics"]["tokens_local_out"] > 0
