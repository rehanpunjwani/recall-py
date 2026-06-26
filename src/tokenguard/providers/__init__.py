from tokenguard.providers.base import LLMProvider
from tokenguard.providers.ollama import OllamaProvider
from tokenguard.providers.openai_compat import OpenAICompatibleProvider


def create_provider(settings: object) -> LLMProvider:
    from tokenguard.settings import AppSettings

    assert isinstance(settings, AppSettings)
    cfg = settings.ollama

    if settings.provider.type == "openai_compat":
        return OpenAICompatibleProvider(
            base_url=settings.provider.base_url or cfg.base_url,
            embed_model=settings.provider.embed_model or cfg.embed_model,
            chat_model=settings.provider.chat_model or cfg.chat_model,
            api_key_env=settings.provider.api_key_env,
            timeout_seconds=cfg.timeout_seconds,
        )

    return OllamaProvider(cfg)


__all__ = [
    "LLMProvider",
    "OllamaProvider",
    "OpenAICompatibleProvider",
    "create_provider",
]
