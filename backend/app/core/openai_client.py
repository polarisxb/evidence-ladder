"""Shared OpenAI-compatible client for platform LLM calls (analyzer, engines, builtin target)."""

from openai import AsyncOpenAI

from app.config import settings


def get_platform_openai_client() -> AsyncOpenAI:
    """Client for analysis / generation. Set OPENAI_BASE_URL for DeepSeek, Azure OpenAI, etc."""
    kwargs: dict[str, str] = {"api_key": settings.openai_api_key or ""}
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url.rstrip("/")
    return AsyncOpenAI(**kwargs)
