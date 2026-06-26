from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class LLMProvider(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]: ...

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
    ) -> str: ...

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        yield await self.chat(messages, max_tokens=max_tokens)

    @abstractmethod
    async def health(self) -> bool: ...
