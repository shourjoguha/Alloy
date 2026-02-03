"""LLM adapter package."""
from app.llm.base import (
    LLMProvider,
    LLMConfig,
    LLMResponse,
    Message,
    StreamChunk,
    PromptBuilder,
)
from app.llm.ollama_provider import (
    OllamaProvider,
    SESSION_PLAN_SCHEMA,
    ADAPTATION_RESPONSE_SCHEMA,
)


__all__ = [
    "LLMProvider",
    "LLMConfig",
    "LLMResponse",
    "Message",
    "StreamChunk",
    "PromptBuilder",
    "OllamaProvider",
    "SESSION_PLAN_SCHEMA",
    "ADAPTATION_RESPONSE_SCHEMA",
    "get_llm_provider",
    "cleanup_llm_provider",
]


# Module-level singleton instance
_provider_instance: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:
    """
    Get the singleton LLM provider instance.
    
    Returns the appropriate provider based on settings.
    Currently only Ollama is implemented; future providers
    (OpenAI, Anthropic, etc.) can be added here.
    
    Uses singleton pattern to reuse HTTP connections and prevent resource leaks.
    """
    global _provider_instance
    
    if _provider_instance is not None:
        return _provider_instance
    
    from app.config.settings import get_settings
    
    settings = get_settings()
    
    if settings.llm_provider == "ollama":
        _provider_instance = OllamaProvider()
    else:
        # Future: Add other providers
        raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
    
    return _provider_instance


async def cleanup_llm_provider():
    """
    Clean up the LLM provider singleton.
    
    Closes HTTP connections and releases resources.
    Should be called during application shutdown.
    """
    global _provider_instance
    
    if _provider_instance is not None:
        await _provider_instance.close()
        _provider_instance = None
