from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from tokenguard.indexing import collect_index_files, index_workspace


def test_collect_index_files(tmp_path: Path):
    (tmp_path / "README.md").write_text("# Hi", encoding="utf-8")
    rules = tmp_path / ".cursor" / "rules"
    rules.mkdir(parents=True)
    (rules / "a.mdc").write_text("rule", encoding="utf-8")
    files = collect_index_files(tmp_path, ("README.md", ".cursor/rules/**/*.mdc"))
    rel = {str(p.relative_to(tmp_path)) for p in files}
    assert "README.md" in rel
    assert ".cursor/rules/a.mdc" in rel


@pytest.mark.asyncio
async def test_index_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("TOKENGUARD_CONFIG", raising=False)
    (tmp_path / "README.md").write_text("# TokenGuard\nLocal cache.", encoding="utf-8")
    from tokenguard.app import open_connection
    from tokenguard.ollama_client import OllamaClient
    from tokenguard.settings import AppSettings

    settings = AppSettings.load()
    conn = open_connection(settings)
    ollama = OllamaClient(settings.ollama)

    with patch.object(OllamaClient, "embed", AsyncMock(return_value=[0.1] * 8)):
        out = await index_workspace(
            conn,
            settings,
            ollama,
            workspace=tmp_path,
            globs=("README.md",),
        )
    assert out["files_indexed"] == 1
    row = conn.execute("SELECT COUNT(*) FROM messages WHERE role='doc'").fetchone()
    assert row[0] == 1
