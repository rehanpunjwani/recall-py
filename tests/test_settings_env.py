
from tokenguard.settings import AppSettings


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("TOKENGUARD_OLLAMA_BASE_URL", "http://example:11434")
    monkeypatch.setenv("TOKENGUARD_DB_PATH", "/tmp/tg.db")
    monkeypatch.setenv("TOKENGUARD_API_LISTEN_HOST", "0.0.0.0")
    monkeypatch.setenv("TOKENGUARD_API_LISTEN_PORT", "9999")
    s = AppSettings.load()
    assert s.ollama.base_url == "http://example:11434"
    assert s.storage.db_path == "/tmp/tg.db"
    assert s.api.listen_host == "0.0.0.0"
    assert s.api.listen_port == 9999


def test_env_invalid_port_ignored(monkeypatch):
    monkeypatch.delenv("TOKENGUARD_API_LISTEN_PORT", raising=False)
    monkeypatch.setenv("TOKENGUARD_API_LISTEN_PORT", "not-a-port")
    s = AppSettings.load()
    assert s.api.listen_port == 8766
