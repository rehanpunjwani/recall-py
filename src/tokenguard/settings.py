from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class OllamaConfig(BaseModel):
    base_url: str = "http://127.0.0.1:11434"
    embed_model: str = "nomic-embed-text"
    chat_model: str = "llama3.2"
    timeout_seconds: float = 120.0


class StorageConfig(BaseModel):
    db_path: str = "~/.local/share/tokenguard/tokenguard.db"


class LimitsConfig(BaseModel):
    max_local_answer_tokens: int = 512
    max_chunks_for_prompt: int = 8
    chunk_size_chars: int = 1200
    chunk_overlap_chars: int = 150


class PolicyConfig(BaseModel):
    always_escalate_keywords: list[str] = Field(default_factory=list)
    redact_patterns: list[str] = Field(default_factory=list)
    auto_escalate: bool = False
    confidence_threshold: float = 0.5


class ProxyConfig(BaseModel):
    enabled: bool = False
    try_local_first: bool = False
    listen_host: str = "127.0.0.1"
    listen_port: int = 8765
    upstream_base_url: str = ""
    upstream_api_key_env: str = "OPENAI_API_KEY"
    cache_ttl_seconds: int = 86400
    cache_max_entries: int = 10000


class ProviderConfig(BaseModel):
    type: str = "ollama"
    base_url: str = ""
    embed_model: str = ""
    chat_model: str = ""
    api_key_env: str = "OPENAI_API_KEY"


class ApiConfig(BaseModel):
    listen_host: str = "127.0.0.1"
    listen_port: int = 8766


def _default_yaml_candidates() -> list[Path]:
    here = Path(__file__).resolve().parent
    return [
        here / "config" / "default.yaml",
        here.parent.parent / "config" / "default.yaml",
    ]


def _env_config_overlay() -> dict[str, Any]:
    """Docker / k8s overrides without editing YAML."""
    o: dict[str, Any] = {}
    if v := os.environ.get("TOKENGUARD_OLLAMA_BASE_URL", "").strip():
        o.setdefault("ollama", {})["base_url"] = v
    if v := os.environ.get("TOKENGUARD_DB_PATH", "").strip():
        o.setdefault("storage", {})["db_path"] = v
    if v := os.environ.get("TOKENGUARD_API_LISTEN_HOST", "").strip():
        o.setdefault("api", {})["listen_host"] = v
    if v := os.environ.get("TOKENGUARD_API_LISTEN_PORT", "").strip():
        try:
            o.setdefault("api", {})["listen_port"] = int(v)
        except ValueError:
            pass
    return o


class AppSettings(BaseModel):
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    limits: LimitsConfig = Field(default_factory=LimitsConfig)
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)

    @classmethod
    def load(cls, path: Path | None = None) -> AppSettings:
        merged: dict[str, Any] = {}
        for candidate in _default_yaml_candidates():
            if candidate.is_file():
                merged.update(_read_yaml(candidate))
                break
        raw_cfg = os.environ.get("TOKENGUARD_CONFIG", "").strip()
        if raw_cfg:
            user = Path(raw_cfg).expanduser()
            if user.is_file():
                merged = _deep_merge(merged, _read_yaml(user))
        else:
            xdg = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser() / "tokenguard" / "config.yaml"
            if xdg.is_file():
                merged = _deep_merge(merged, _read_yaml(xdg))
        if path and path.is_file():
            merged = _deep_merge(merged, _read_yaml(path))
        merged = _deep_merge(merged, _env_config_overlay())
        return cls.model_validate(merged)

    def resolved_db_path(self) -> Path:
        return Path(self.storage.db_path).expanduser().resolve()


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config root must be a mapping: {path}")
    return data


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out
