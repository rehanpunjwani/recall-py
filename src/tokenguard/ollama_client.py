from __future__ import annotations

from collections.abc import AsyncIterator

from tokenguard.providers import (
    LLMProvider,
    OllamaProvider,
    create_provider,
)
from tokenguard.settings import AppSettings, OllamaConfig

__all__ = ["OllamaClient", "LLMProvider"]


class OllamaClient(LLMProvider):
    def __init__(self, cfg: OllamaConfig) -> None:
        self._wrapped = OllamaProvider(cfg)

    @classmethod
    def from_settings(cls, settings: AppSettings) -> OllamaClient:
        wrapped = create_provider(settings)
        client = cls.__new__(cls)
        client._wrapped = wrapped
        return client

    async def embed(self, text: str) -> list[float]:
        return await self._wrapped.embed(text)

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
    ) -> str:
        return await self._wrapped.chat(messages, max_tokens=max_tokens)

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        async for token in self._wrapped.chat_stream(messages, max_tokens=max_tokens):
            yield token

    async def health(self) -> bool:
        return await self._wrapped.health()
