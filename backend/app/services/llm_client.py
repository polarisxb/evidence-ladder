"""Unified LLM client abstraction.

Hides the protocol differences between OpenAI-compatible providers and
Anthropic (Claude) behind a single call_chat() function.

Usage
-----
    info = ProviderClientInfo(
        provider_type="claude",
        api_key="sk-ant-...",
        base_url=None,
    )
    text = await call_chat(
        info, model="claude-opus-4-5",
        messages=[{"role": "user", "content": "Hello"}],
    )
"""
from __future__ import annotations

import contextvars
import httpx
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Per-scan provider overrides (set by scan_runner._apply_scan_providers).
_scan_judge_provider_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_scan_judge_provider_id", default=None
)
_scan_judge_model: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_scan_judge_model", default=None
)
_scan_generation_provider_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_scan_generation_provider_id", default=None
)
_scan_generation_model: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_scan_generation_model", default=None
)


def get_generation_routing_override() -> tuple[str | None, str | None]:
    return _scan_generation_provider_id.get(), _scan_generation_model.get()

# ---------------------------------------------------------------------------
# Client instance caches  (keyed by credentials to reuse connection pools)
# ---------------------------------------------------------------------------

_openai_clients: dict[tuple[str, str | None], object] = {}
_anthropic_clients: dict[str, object] = {}

# ---------------------------------------------------------------------------
# Provider result caches  (TTL-based to avoid per-case DB lookups)
# ---------------------------------------------------------------------------

_PROVIDER_CACHE_TTL_S: float = 60.0
_judge_provider_cache: tuple[float, tuple] | None = None    # (expires_at, result)
_generation_provider_cache: tuple[float, tuple] | None = None

# Anthropic-specific error types — imported lazily to avoid hard-dep at module load
_ANTHROPIC_RATE_LIMIT_NAMES = {"RateLimitError"}
_ANTHROPIC_API_ERROR_NAMES = {"APIError", "APIStatusError", "APIConnectionError"}

# Default constants
ANTHROPIC_VERSION = "2023-06-01"
_DEFAULT_MAX_TOKENS = 1024


# ---------------------------------------------------------------------------
# Data transfer object
# ---------------------------------------------------------------------------

@dataclass
class ProviderClientInfo:
    """Lightweight container carrying everything needed to make one LLM call."""

    provider_type: str          # "openai" | "deepseek" | … | "claude" | "custom"
    api_key: str
    base_url: str | None = None

    # For JSON-mode: Anthropic needs a special pre-fill trick; others use response_format
    extra: dict = field(default_factory=dict)


def _resolve_provider_base_url(provider_type: str, custom_base_url: str | None) -> str | None:
    if custom_base_url and custom_base_url.strip():
        return custom_base_url.strip().rstrip("/")

    from app.models.model_provider import PROVIDER_TYPES

    preset = PROVIDER_TYPES.get(provider_type, "")
    return preset.rstrip("/") if preset else None


def _is_chat_model(model_id: str) -> bool:
    mid = model_id.lower()
    non_chat_prefixes = (
        "text-embedding", "text-moderation", "omni-moderation",
        "tts-", "whisper-", "dall-e", "davinci-0", "babbage-0",
        "gpt-image", "sora", "realtime",
    )
    non_chat_contains = ("instruct", "embedding", "moderation", "speech", "transcri")
    if any(mid.startswith(p) for p in non_chat_prefixes):
        return False
    if any(s in mid for s in non_chat_contains):
        return False
    return True


async def fetch_openai_compatible_model_ids(
    *,
    api_key: str,
    provider_type: str,
    base_url_override: str | None,
) -> list[str]:
    base_url = _resolve_provider_base_url(provider_type, base_url_override)
    if not base_url:
        raise LLMConfigurationError("base_url is required for custom providers")

    models_url = f"{base_url}/models"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                models_url,
                headers={"Authorization": f"Bearer {api_key}"},
            )
        if resp.status_code != 200:
            raise LLMConfigurationError(
                f"Provider returned HTTP {resp.status_code} while fetching models: {resp.text[:200]}"
            )

        data = resp.json()
        raw_models: list[dict] = data.get("data", [])
        if not raw_models and isinstance(data, list):
            raw_models = data

        return sorted(
            [m["id"] for m in raw_models if isinstance(m, dict) and _is_chat_model(m.get("id", ""))],
            key=lambda x: x.lower(),
        )
    except LLMConfigurationError:
        raise
    except Exception as exc:
        raise LLMConfigurationError(f"Failed to fetch models: {exc}") from exc


async def resolve_provider_model(
    *,
    provider_type: str,
    api_key: str,
    base_url: str | None,
    configured_models: list[str | None],
    role_label: str,
) -> str:
    for candidate in configured_models:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    if provider_type == "claude":
        return "claude-haiku-4-5"

    models = await fetch_openai_compatible_model_ids(
        api_key=api_key,
        provider_type=provider_type,
        base_url_override=base_url,
    )
    if not models:
        raise LLMConfigurationError(
            f"No chat model was detected for the configured {role_label} provider. "
            "Set a model explicitly or verify the provider credentials/base URL."
        )
    return models[0]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def call_chat(
    info: ProviderClientInfo,
    model: str,
    messages: list[dict],
    *,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    temperature: float = 0.7,
    json_mode: bool = False,
    seed: int | None = None,
) -> str:
    """Send a chat request to the given provider and return the response text.

    Handles both OpenAI-compatible endpoints and Anthropic natively.

    Args:
        info: Provider credentials and type.
        model: Model identifier string.
        messages: Standard OpenAI-style message list
                  ([{"role": "system"|"user"|"assistant", "content": "..."}]).
        max_tokens: Maximum tokens in the response.
        temperature: Sampling temperature.
        json_mode: If True, instruct the model to respond with valid JSON.
                   For OpenAI-compatible providers this sets response_format.
                   For Anthropic this injects a JSON instruction + pre-fill.

    Returns:
        The assistant's response as a plain string.
    """
    if info.provider_type == "claude":
        # Anthropic has no ``seed`` parameter; it is silently ignored there.
        return await _call_anthropic(
            info, model, messages,
            max_tokens=max_tokens,
            temperature=temperature,
            json_mode=json_mode,
        )
    return await _call_openai_compatible(
        info, model, messages,
        max_tokens=max_tokens,
        temperature=temperature,
        json_mode=json_mode,
        seed=seed,
    )


# ---------------------------------------------------------------------------
# OpenAI-compatible path
# ---------------------------------------------------------------------------

async def _call_openai_compatible(
    info: ProviderClientInfo,
    model: str,
    messages: list[dict],
    *,
    max_tokens: int,
    temperature: float,
    json_mode: bool,
    seed: int | None = None,
) -> str:
    from openai import AsyncOpenAI, RateLimitError, APIError

    cache_key = (info.api_key, info.base_url)
    client = _openai_clients.get(cache_key)
    if client is None:
        client = AsyncOpenAI(api_key=info.api_key, base_url=info.base_url or None)
        _openai_clients[cache_key] = client
    kwargs: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    # Best-effort determinism: only sent when explicitly requested. Providers
    # that don't support ``seed`` (e.g. most non-OpenAI backends) ignore it.
    if seed is not None:
        kwargs["seed"] = seed
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        response = await client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""
    except RateLimitError as exc:
        retry_after: float | None = None
        if hasattr(exc, "response") and exc.response is not None:
            ra = exc.response.headers.get("retry-after")
            if ra:
                try:
                    retry_after = float(ra)
                except (ValueError, TypeError):
                    pass
        raise LLMRateLimitError(
            f"Rate limit reached on {info.provider_type}",
            retry_after_s=retry_after,
        ) from exc
    except APIError as e:
        raise LLMAPIError(f"API error from {info.provider_type}: {e}") from e


# ---------------------------------------------------------------------------
# Anthropic (Claude) path
# ---------------------------------------------------------------------------

async def _call_anthropic(
    info: ProviderClientInfo,
    model: str,
    messages: list[dict],
    *,
    max_tokens: int,
    temperature: float,
    json_mode: bool,
) -> str:
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError(
            "anthropic package is not installed. "
            "Add `anthropic>=0.40.0` to requirements.txt and reinstall."
        ) from exc

    # Separate system message from user/assistant turns
    system_text: str | anthropic.NOT_GIVEN = anthropic.NOT_GIVEN  # type: ignore[attr-defined]
    chat_messages: list[dict] = []

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "system":
            # Anthropic only accepts a single system string; concatenate if multiple
            if system_text is anthropic.NOT_GIVEN:  # type: ignore[attr-defined]
                system_text = str(content)
            else:
                system_text = f"{system_text}\n\n{content}"
        elif role in {"user", "assistant"}:
            chat_messages.append({"role": role, "content": str(content)})

    # JSON mode: append instruction to last user message and pre-fill assistant
    # Track the pre-fill so we can prepend it to the response (Anthropic returns only
    # the continuation after the pre-fill, not the pre-fill itself).
    prefill: str = ""
    if json_mode:
        _inject_json_mode(chat_messages)
        # _inject_json_mode appends {"role": "assistant", "content": "{"}
        if chat_messages and chat_messages[-1]["role"] == "assistant":
            prefill = chat_messages[-1]["content"]

    client = _anthropic_clients.get(info.api_key)
    if client is None:
        client = anthropic.AsyncAnthropic(api_key=info.api_key)
        _anthropic_clients[info.api_key] = client

    create_kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": chat_messages,
    }
    # temperature is NOT_GIVEN for extended thinking models; pass when explicitly set
    if temperature != 1.0:
        create_kwargs["temperature"] = temperature
    if system_text is not anthropic.NOT_GIVEN:  # type: ignore[attr-defined]
        create_kwargs["system"] = system_text

    try:
        response = await client.messages.create(**create_kwargs)
        # content is a list of ContentBlock — extract text blocks
        parts: list[str] = []
        for block in response.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        text = "".join(parts)
        # Re-attach the pre-fill prefix (e.g. "{") so the caller gets valid JSON
        return prefill + text if prefill else text
    except Exception as exc:
        exc_type = type(exc).__name__
        if exc_type in _ANTHROPIC_RATE_LIMIT_NAMES:
            retry_after: float | None = None
            if hasattr(exc, "response") and exc.response is not None:
                ra = getattr(exc.response, "headers", {}).get("retry-after")
                if ra:
                    try:
                        retry_after = float(ra)
                    except (ValueError, TypeError):
                        pass
            raise LLMRateLimitError(
                f"Rate limit reached on claude: {exc}",
                retry_after_s=retry_after,
            ) from exc
        if exc_type in _ANTHROPIC_API_ERROR_NAMES:
            raise LLMAPIError(f"Anthropic API error: {exc}") from exc
        raise


def _inject_json_mode(messages: list[dict]) -> None:
    """Mutate the message list in-place to steer Claude toward JSON output.

    Strategy:
    1. Append a JSON reminder to the last user message.
    2. Pre-fill the assistant turn with '{' so the model completes a JSON object.
    """
    if not messages:
        return

    # Find and update last user message
    for i in range(len(messages) - 1, -1, -1):
        if messages[i]["role"] == "user":
            messages[i] = {
                "role": "user",
                "content": messages[i]["content"] + "\n\nRespond with valid JSON only.",
            }
            break

    # Pre-fill assistant response to strongly steer toward JSON
    if messages and messages[-1]["role"] != "assistant":
        messages.append({"role": "assistant", "content": "{"})


# ---------------------------------------------------------------------------
# Platform provider factory helpers
# ---------------------------------------------------------------------------

def make_platform_provider() -> ProviderClientInfo:
    """Return a ProviderClientInfo built from platform settings (fallback path)."""
    from app.config import settings
    return ProviderClientInfo(
        provider_type="openai",
        api_key=settings.openai_api_key or "",
        base_url=settings.openai_base_url or None,
    )


async def get_judge_provider() -> tuple[ProviderClientInfo, str]:
    """Return (ProviderClientInfo, model_name) for the judge role.

    Priority:
    1. Per-scan override (scan_runner._apply_scan_providers)
    2. Database ModelProvider with is_judge_default=True and enabled=True
    3. Fallback to platform settings (.env)
    """
    override_id = _scan_judge_provider_id.get()
    if override_id:
        result = await get_provider_by_id(override_id, role="judge")
        if result:
            info, default_model = result
            model = _scan_judge_model.get() or default_model
            return info, model

    global _judge_provider_cache
    now = time.monotonic()
    if _judge_provider_cache is not None and now < _judge_provider_cache[0]:
        return _judge_provider_cache[1]  # type: ignore[return-value]

    from app.config import settings
    result_tuple: tuple[ProviderClientInfo, str]
    try:
        from sqlalchemy import select
        from app.database import async_session
        from app.models.model_provider import ModelProvider
        async with async_session() as db:
            row = await db.execute(
                select(ModelProvider)
                .where(ModelProvider.is_judge_default == True)  # noqa: E712
                .where(ModelProvider.enabled == True)            # noqa: E712
                .limit(1)
            )
            provider = row.scalar_one_or_none()
        if provider and provider.api_key:
            info = ProviderClientInfo(
                provider_type=provider.provider_type,
                api_key=provider.api_key,
                base_url=provider.base_url or None,
            )
            model = await resolve_provider_model(
                provider_type=provider.provider_type,
                api_key=provider.api_key,
                base_url=provider.base_url,
                configured_models=[provider.judge_model, provider.mini_model],
                role_label="judge",
            )
            result_tuple = (info, model)
            _judge_provider_cache = (now + _PROVIDER_CACHE_TTL_S, result_tuple)
            return result_tuple
    except LLMConfigurationError:
        raise
    except Exception:
        pass
    result_tuple = (make_platform_provider(), settings.openai_model)
    _judge_provider_cache = (now + _PROVIDER_CACHE_TTL_S, result_tuple)
    return result_tuple


async def get_generation_provider() -> tuple[ProviderClientInfo, str]:
    """Return (ProviderClientInfo, model_name) for the generation role.

    Priority:
    1. Per-scan override (scan_runner._apply_scan_providers)
    2. Database ModelProvider with is_generation_default=True and enabled=True
    3. Fallback to platform settings (.env)
    """
    override_id = _scan_generation_provider_id.get()
    if override_id:
        result = await get_provider_by_id(override_id, role="generation")
        if result:
            info, default_model = result
            model = _scan_generation_model.get() or default_model
            return info, model

    global _generation_provider_cache
    now = time.monotonic()
    if _generation_provider_cache is not None and now < _generation_provider_cache[0]:
        return _generation_provider_cache[1]  # type: ignore[return-value]

    from app.config import settings
    result_tuple: tuple[ProviderClientInfo, str]
    try:
        from sqlalchemy import select
        from app.database import async_session
        from app.models.model_provider import ModelProvider
        async with async_session() as db:
            row = await db.execute(
                select(ModelProvider)
                .where(ModelProvider.is_generation_default == True)  # noqa: E712
                .where(ModelProvider.enabled == True)                 # noqa: E712
                .limit(1)
            )
            provider = row.scalar_one_or_none()
        if provider and provider.api_key:
            info = ProviderClientInfo(
                provider_type=provider.provider_type,
                api_key=provider.api_key,
                base_url=provider.base_url or None,
            )
            model = await resolve_provider_model(
                provider_type=provider.provider_type,
                api_key=provider.api_key,
                base_url=provider.base_url,
                configured_models=[provider.mini_model, provider.judge_model],
                role_label="generation",
            )
            result_tuple = (info, model)
            _generation_provider_cache = (now + _PROVIDER_CACHE_TTL_S, result_tuple)
            return result_tuple
    except LLMConfigurationError:
        raise
    except Exception:
        pass
    result_tuple = (make_platform_provider(), settings.openai_mini_model)
    _generation_provider_cache = (now + _PROVIDER_CACHE_TTL_S, result_tuple)
    return result_tuple



# ---------------------------------------------------------------------------
# 按 ID 获取指定供应商（带 TTL 缓存，避免同一扫描内重复查 DB）
# ---------------------------------------------------------------------------

_provider_by_id_cache: dict[tuple[str, str], tuple[float, tuple | None]] = {}


async def get_provider_by_id(
    provider_id: str,
    *,
    role: str = "generation",
) -> tuple[ProviderClientInfo, str] | None:
    """根据 ID 从数据库获取供应商配置。

    Returns:
        (ProviderClientInfo, default_model) 或 None（未找到/已禁用/无 key）。
        default_model 优先取 mini_model，其次 judge_model。
        ProviderClientInfo.provider_type 反映供应商的实际类型，调用方可据此做路由校验。
    """
    now = time.monotonic()
    cache_key = (provider_id, role)
    cached = _provider_by_id_cache.get(cache_key)
    if cached is not None and now < cached[0]:
        return cached[1]  # type: ignore[return-value]

    result: tuple[ProviderClientInfo, str] | None = None
    try:
        from sqlalchemy import select
        from app.database import async_session
        from app.models.model_provider import ModelProvider
        async with async_session() as db:
            row = await db.execute(
                select(ModelProvider)
                .where(ModelProvider.id == provider_id)
                .where(ModelProvider.enabled == True)  # noqa: E712
                .limit(1)
            )
            provider = row.scalar_one_or_none()
        if provider and provider.api_key:
            from app.models.model_provider import first_api_key
            key = first_api_key(provider.api_key)
            info = ProviderClientInfo(
                provider_type=provider.provider_type,
                api_key=key,
                base_url=provider.base_url or None,
            )
            configured_models = (
                [provider.judge_model, provider.mini_model]
                if role == "judge"
                else [provider.mini_model, provider.judge_model]
            )
            default_model = await resolve_provider_model(
                provider_type=provider.provider_type,
                api_key=key,
                base_url=provider.base_url,
                configured_models=configured_models,
                role_label=role,
            )
            result = (info, default_model)
    except LLMConfigurationError:
        raise
    except Exception:
        logger.warning("Failed to look up provider %s", provider_id, exc_info=True)

    _provider_by_id_cache[cache_key] = (now + _PROVIDER_CACHE_TTL_S, result)
    return result


# ---------------------------------------------------------------------------
# Unified exceptions
# ---------------------------------------------------------------------------

def invalidate_provider_cache() -> None:
    """Force-expire the cached provider results (e.g. after a model provider update)."""
    global _judge_provider_cache, _generation_provider_cache
    _judge_provider_cache = None
    _generation_provider_cache = None
    _provider_by_id_cache.clear()


class LLMRateLimitError(Exception):
    """Raised when any provider returns a rate-limit response."""

    def __init__(self, message: str, *, retry_after_s: float | None = None):
        super().__init__(message)
        self.retry_after_s = retry_after_s


class LLMConfigurationError(Exception):
    """Raised when a provider is reachable but lacks a usable model configuration."""


class LLMAPIError(Exception):
    """Raised when any provider returns an API-level error."""
