from unittest.mock import AsyncMock, patch

import pytest

from tokenguard.threads import thread_id_for_workspace, workspace_fingerprint


def test_workspace_fingerprint_from_roots():
    assert workspace_fingerprint({"workspace_roots": ["/tmp/proj"]}) == "/tmp/proj"


def test_thread_id_stable_per_workspace():
    a = thread_id_for_workspace({"cwd": "/tmp/foo"})
    b = thread_id_for_workspace({"cwd": "/tmp/foo"})
    c = thread_id_for_workspace({"cwd": "/tmp/bar"})
    assert a == b
    assert a != c


@pytest.mark.asyncio
async def test_handle_query_ingests_user(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("TOKENGUARD_CONFIG", raising=False)
    monkeypatch.setenv("TOKENGUARD_WORKSPACE", str(tmp_path / "proj"))
    from tokenguard.app import open_connection
    from tokenguard.engine import handle_query
    from tokenguard.ollama_client import OllamaClient
    from tokenguard.settings import AppSettings
    from tokenguard.threads import thread_id_for_fingerprint

    settings = AppSettings.load()
    conn = open_connection(settings)
    ollama = OllamaClient(settings.ollama)
    ws = str(tmp_path / "proj")

    with (
        patch.object(OllamaClient, "embed", AsyncMock(return_value=[0.1] * 8)),
        patch.object(OllamaClient, "chat", AsyncMock(return_value="draft text")),
    ):
        out = await handle_query(
            conn,
            settings,
            ollama,
            query="What is TokenGuard?",
            thread_id=None,
            workspace_fingerprint=ws,
        )
    expected_tid = thread_id_for_fingerprint(ws)
    assert out["thread_id"] == expected_tid
    assert out["workspace_fingerprint"] == ws
    assert out["answer"]["mode"] == "draft"
    assert "context_pack" in out
    assert "metrics" in out
    row = conn.execute("SELECT COUNT(*) FROM messages WHERE role='user'").fetchone()
    assert row[0] >= 1
