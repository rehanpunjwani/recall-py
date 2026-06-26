from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from tokenguard import onboard


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("TOKENGUARD_CONFIG", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    return tmp_path


def test_onboard_creates_config_and_db(isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(onboard.OllamaClient, "health", AsyncMock(return_value=True))
    onboard.run(non_interactive=True, skip_pull=True)
    cfg = isolated_home / ".config" / "tokenguard" / "config.yaml"
    assert cfg.is_file()
    assert "ollama:" in cfg.read_text()
    db = isolated_home / ".local" / "share" / "tokenguard" / "tokenguard.db"
    assert db.is_file()


def test_onboard_respects_tokenguard_config(isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    custom = isolated_home / "my.yaml"
    custom.write_text("storage:\n  db_path: \"" + str(isolated_home / "db.sqlite").replace("\\", "/") + "\"\n", encoding="utf-8")
    monkeypatch.setenv("TOKENGUARD_CONFIG", str(custom))
    monkeypatch.setattr(onboard.OllamaClient, "health", AsyncMock(return_value=True))
    onboard.run(non_interactive=True, skip_pull=True)
    user_cfg = isolated_home / ".config" / "tokenguard" / "config.yaml"
    assert not user_cfg.is_file()
    assert (isolated_home / "db.sqlite").is_file()
