from __future__ import annotations

import json
from collections import OrderedDict
from collections.abc import AsyncIterator
from typing import Any

import httpx

from tokenguard.providers.base import LLMProvider
from tokenguard.settings import OllamaConfig


class _LRUCache:
    def __init__(self, maxsize: int = 1024) -> None:
        self._maxsize = maxsize
        self._dict: OrderedDict[str, list[float]] = OrderedDict()

    def get(self, key: str) -> list[float] | None:
        if key not in self._dict:
            return None
        self._dict.move_to_end(key)
        return self._dict[key]

    def put(self, key: str, value: list[float]) -> None:
        self._dict[key] = value
        self._dict.move_to_end(key)
        if len(self._dict) > self._maxsize:
            self._dict.popitem(last=False)


class OllamaProvider(LLMProvider):
    def __init__(self, cfg: OllamaConfig) -> None:
        self._cfg = cfg
        self._base = cfg.base_url.rstrip("/")
        self._timeout = httpx.Timeout(cfg.timeout_seconds)
        self._embed_cache = _LRUCache()

    async def embed(self, text: str) -> list[float]:
        key = f"{self._cfg.embed_model}:{text}"
        cached = self._embed_cache.get(key)
        if cached is not None:
            return cached
        url = f"{self._base}/api/embeddings"
        payload: dict[str, Any] = {"model": self._cfg.embed_model, "prompt": text}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
        emb = data.get("embedding")
        if not isinstance(emb, list):
            raise RuntimeError(f"Unexpected Ollama embeddings response: {data!r}")
        result = [float(x) for x in emb]
        self._embed_cache.put(key, result)
        return result

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
    ) -> str:
        url = f"{self._base}/api/chat"
        options: dict[str, Any] = {}
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        payload: dict[str, Any] = {
            "model": self._cfg.chat_model,
            "messages": messages,
            "stream": False,
        }
        if options:
            payload["options"] = options
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
        msg = data.get("message") or {}
        content = msg.get("content")
        if not isinstance(content, str):
            raise RuntimeError(f"Unexpected Ollama chat response: {data!r}")
        return content

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        url = f"{self._base}/api/chat"
        options: dict[str, Any] = {}
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        payload: dict[str, Any] = {
            "model": self._cfg.chat_model,
            "messages": messages,
            "stream": True,
        }
        if options:
            payload["options"] = options
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream("POST", url, json=payload) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    msg = data.get("message") or {}
                    content = msg.get("content")
                    if isinstance(content, str) and content:
                        yield content

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                r = await client.get(f"{self._base}/api/tags")
                return r.status_code == 200
        except httpx.HTTPError:
            return False
