from __future__ import annotations

import json as _json
import os
from collections.abc import AsyncIterator
from typing import Any

import httpx

from tokenguard.providers.base import LLMProvider


class OpenAICompatibleProvider(LLMProvider):
    def __init__(
        self,
        base_url: str,
        embed_model: str = "",
        chat_model: str = "",
        api_key_env: str = "OPENAI_API_KEY",
        timeout_seconds: float = 120.0,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._embed_model = embed_model
        self._chat_model = chat_model
        self._api_key_env = api_key_env
        self._timeout = httpx.Timeout(timeout_seconds)

    def _headers(self) -> dict[str, str]:
        api_key = os.environ.get(self._api_key_env, "")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    async def embed(self, text: str) -> list[float]:
        if not self._embed_model:
            raise RuntimeError("Embedding model not configured for this provider")
        url = f"{self._base}/embeddings"
        payload: dict[str, Any] = {
            "model": self._embed_model,
            "input": text,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.post(url, json=payload, headers=self._headers())
            r.raise_for_status()
            data = r.json()
        emb_data = data.get("data", [])
        if not emb_data:
            raise RuntimeError(f"Unexpected embeddings response: {data!r}")
        embedding = emb_data[0].get("embedding")
        if not isinstance(embedding, list):
            raise RuntimeError(f"Unexpected embedding format: {data!r}")
        return [float(x) for x in embedding]

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
    ) -> str:
        if not self._chat_model:
            raise RuntimeError("Chat model not configured for this provider")
        url = f"{self._base}/chat/completions"
        payload: dict[str, Any] = {
            "model": self._chat_model,
            "messages": messages,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.post(url, json=payload, headers=self._headers())
            r.raise_for_status()
            data = r.json()
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError(f"Unexpected chat response: {data!r}")
        content = choices[0].get("message", {}).get("content", "")
        if not isinstance(content, str):
            raise RuntimeError(f"Unexpected content format: {data!r}")
        return content

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        if not self._chat_model:
            raise RuntimeError("Chat model not configured for this provider")
        url = f"{self._base}/chat/completions"
        payload: dict[str, Any] = {
            "model": self._chat_model,
            "messages": messages,
            "stream": True,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream("POST", url, json=payload, headers=self._headers()) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line.strip():
                        continue
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = _json.loads(data_str)
                    except _json.JSONDecodeError:
                        continue
                    choices = data.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    content = delta.get("content", "")
                    if isinstance(content, str) and content:
                        yield content

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                r = await client.get(f"{self._base}/models", headers=self._headers())
                return r.status_code == 200
        except httpx.HTTPError:
            return False
