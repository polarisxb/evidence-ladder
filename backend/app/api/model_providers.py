"""Model Provider management API.

All operations on AI provider credentials follow the same security pattern as Adapters:
- api_key is stored in the database but never returned in plaintext
- ModelProviderResponse includes api_key_set: bool instead
- The /fetch-models endpoint accepts credentials temporarily to query /v1/models
"""
from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.database import get_db
from app.models.model_provider import (
    ModelProvider,
    PROVIDER_TYPES,
    first_api_key,
    mask_key,
    parse_api_keys,
    serialize_api_keys,
)
from app.schemas.model_provider import (
    ApiKeyInfo,
    FetchModelsRequest,
    ModelProviderCreate,
    ModelProviderResponse,
    ModelProviderUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Model id prefixes that indicate non-chat models — filter these from the list
_NON_CHAT_PREFIXES = (
    "text-embedding", "text-moderation", "omni-moderation",
    "tts-", "whisper-", "dall-e", "davinci-0", "babbage-0",
    "gpt-image", "sora", "realtime",
)
# NOTE: "instruct" is intentionally NOT here — most providers (NVIDIA NIM,
# Meta Llama, Qwen, etc.) use "instruct" for chat-tuned models.
# Only OpenAI's gpt-3.5-turbo-instruct is a non-chat completion model,
# which is caught by _NON_CHAT_EXACT below.
_NON_CHAT_CONTAINS = ("embedding", "moderation", "speech", "transcri", "rerank", "vision-encoder")
_NON_CHAT_EXACT = {"gpt-3.5-turbo-instruct"}


def _first_key(raw: str) -> str:
    """Extract the first non-empty API key (JSON or legacy)."""
    return first_api_key(raw)


def _is_chat_model(model_id: str) -> bool:
    mid = model_id.lower()
    if mid in _NON_CHAT_EXACT:
        return False
    if any(mid.startswith(p) for p in _NON_CHAT_PREFIXES):
        return False
    if any(s in mid for s in _NON_CHAT_CONTAINS):
        return False
    return True


def _serialize(provider: ModelProvider) -> dict:
    entries = parse_api_keys(provider.api_key)
    return ModelProviderResponse(
        id=provider.id,
        name=provider.name,
        provider_type=provider.provider_type,
        api_key_set=bool(entries),
        api_key_count=len(entries),
        api_keys=[
            ApiKeyInfo(index=i, label=e["label"], masked_key=mask_key(e["key"]))
            for i, e in enumerate(entries)
        ],
        base_url=provider.base_url,
        judge_model=provider.judge_model,
        mini_model=provider.mini_model,
        is_judge_default=provider.is_judge_default,
        is_generation_default=provider.is_generation_default,
        enabled=provider.enabled,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    ).model_dump()


def _resolve_base_url(provider_type: str, custom_base_url: str | None) -> str | None:
    """Return the effective base_url: explicit custom_base_url overrides the preset."""
    if custom_base_url and custom_base_url.strip():
        return custom_base_url.strip().rstrip("/")
    preset = PROVIDER_TYPES.get(provider_type, "")
    return preset.rstrip("/") if preset else None


async def _fetch_openai_compatible_model_ids(
    *,
    api_key: str,
    provider_type: str,
    base_url_override: str | None,
) -> list[str]:
    base_url = _resolve_base_url(provider_type, base_url_override)
    if not base_url:
        raise AppException(400, "base_url is required for custom providers")

    models_url = f"{base_url}/models"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                models_url,
                headers={"Authorization": f"Bearer {api_key}"},
            )
        if resp.status_code != 200:
            raise AppException(502, f"Provider returned HTTP {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        raw_models: list[dict] = data.get("data", [])
        if not raw_models and isinstance(data, list):
            raw_models = data

        return sorted(
            [m["id"] for m in raw_models if isinstance(m, dict) and _is_chat_model(m.get("id", ""))],
            key=lambda x: x.lower(),
        )
    except AppException:
        raise
    except Exception as e:
        raise AppException(502, f"Failed to fetch models: {e}")


async def _resolve_test_model(provider: ModelProvider) -> tuple[str, bool]:
    """Pick a model for the connection test.

    Priority:
      1. User-configured judge_model / mini_model
      2. Claude → hardcoded default (Anthropic SDK has no /models list)
      3. All other OpenAI-compatible providers → try /models, pick first
         If /models is not supported, ask the user to configure a model.
    """
    configured = (provider.judge_model or provider.mini_model or "").strip()
    if configured:
        return configured, False

    if provider.provider_type == "claude":
        return "claude-haiku-4-5", False

    # Try to auto-detect; some providers don't expose /models at all
    # (e.g. Doubao / Volcengine requires endpoint IDs), so we catch
    # errors gracefully instead of blowing up.
    try:
        chat_models = await _fetch_openai_compatible_model_ids(
            api_key=_first_key(provider.api_key),
            provider_type=provider.provider_type,
            base_url_override=provider.base_url,
        )
    except Exception:
        chat_models = []

    if not chat_models:
        raise AppException(
            400,
            "Unable to auto-detect models for this provider. "
            "Please select a model via 'Fetch Models' first, or manually "
            "enter a model name in Judge Model / Generation Model, then test again.",
        )
    return chat_models[0], True


# ── GET /model-providers ────────────────────────────────────────────────────────
@router.get("", response_model=dict)
async def list_providers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ModelProvider).order_by(ModelProvider.created_at))
    providers = result.scalars().all()
    return {"data": [_serialize(p) for p in providers], "message": "ok"}


# ── POST /model-providers ───────────────────────────────────────────────────────
@router.post("", response_model=dict)
async def create_provider(body: ModelProviderCreate, db: AsyncSession = Depends(get_db)):
    # Prefer structured api_keys; fall back to legacy api_key
    if body.api_keys:
        raw_key = serialize_api_keys([{"label": e.label, "key": e.key} for e in body.api_keys])
    elif body.api_key:
        raw_key = body.api_key
    else:
        raise AppException(400, "At least one API key is required")
    provider = ModelProvider(
        name=body.name,
        provider_type=body.provider_type,
        api_key=raw_key,
        base_url=_resolve_base_url(body.provider_type, body.base_url),
        judge_model=body.judge_model,
        mini_model=body.mini_model,
        enabled=body.enabled,
    )
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    from app.services.llm_client import invalidate_provider_cache
    invalidate_provider_cache()
    return {"data": _serialize(provider), "message": "Provider created"}


# ── PATCH /model-providers/{id} ─────────────────────────────────────────────────
@router.patch("/{provider_id}", response_model=dict)
async def update_provider(
    provider_id: str,
    body: ModelProviderUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ModelProvider).where(ModelProvider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise AppException(404, f"Provider {provider_id} not found")

    if body.name is not None:
        provider.name = body.name
    if body.provider_type is not None:
        provider.provider_type = body.provider_type

    # Structured api_keys takes precedence over legacy api_key
    if body.api_keys is not None:
        old_entries = parse_api_keys(provider.api_key)
        merged: list[dict[str, str]] = []
        for inp in body.api_keys:
            if inp.key.strip():
                merged.append({"label": inp.label, "key": inp.key.strip()})
            elif 0 <= inp.index < len(old_entries):
                merged.append({"label": inp.label, "key": old_entries[inp.index]["key"]})
        if merged:
            provider.api_key = serialize_api_keys(merged)
    elif body.api_key is not None and body.api_key.strip():
        provider.api_key = body.api_key.strip()

    if body.judge_model is not None:
        provider.judge_model = body.judge_model or None
    if body.mini_model is not None:
        provider.mini_model = body.mini_model or None
    if body.enabled is not None:
        provider.enabled = body.enabled

    # Re-resolve base_url if provider_type or base_url changed
    if body.base_url is not None or body.provider_type is not None:
        provider.base_url = _resolve_base_url(
            provider.provider_type,
            body.base_url if body.base_url is not None else provider.base_url,
        )

    await db.commit()
    await db.refresh(provider)
    from app.services.llm_client import invalidate_provider_cache
    invalidate_provider_cache()
    return {"data": _serialize(provider), "message": "Provider updated"}


# ── DELETE /model-providers/{id} ────────────────────────────────────────────────
@router.delete("/{provider_id}", response_model=dict)
async def delete_provider(provider_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ModelProvider).where(ModelProvider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise AppException(404, f"Provider {provider_id} not found")
    await db.delete(provider)
    await db.commit()
    from app.services.llm_client import invalidate_provider_cache
    invalidate_provider_cache()
    return {"data": None, "message": "Provider deleted"}


# ── POST /model-providers/{id}/test ─────────────────────────────────────────────
@router.post("/{provider_id}/test", response_model=dict)
async def test_provider(provider_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ModelProvider).where(ModelProvider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise AppException(404, f"Provider {provider_id} not found")

    try:
        model, auto_detected = await _resolve_test_model(provider)
    except AppException as e:
        return {"data": {"connected": False, "error": e.detail}, "message": "Connection failed"}

    first_key = _first_key(provider.api_key)
    if provider.provider_type == "claude":
        return await _test_claude(first_key, model)

    from openai import AsyncOpenAI
    base_url = provider.base_url or None
    client = AsyncOpenAI(api_key=first_key, base_url=base_url)

    # Build candidate list: configured model first, then auto-detected ones
    candidates = [model]
    if auto_detected:
        # model is already candidates[0]; append remaining from the list
        try:
            all_models = await _fetch_openai_compatible_model_ids(
                api_key=first_key,
                provider_type=provider.provider_type,
                base_url_override=provider.base_url,
            )
            for m in all_models:
                if m not in candidates:
                    candidates.append(m)
        except Exception:
            pass

    last_error = ""
    for candidate in candidates[:5]:  # try up to 5 models
        try:
            resp = await client.chat.completions.create(
                model=candidate,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5,
            )
            return {
                "data": {
                    "connected": True,
                    "model": resp.model,
                    "resolved_model": candidate,
                    "auto_detected_model": auto_detected,
                },
                "message": "ok",
            }
        except Exception as e:
            last_error = str(e)
            # 404/403 = model not accessible, try next candidate
            if "404" in last_error or "403" in last_error:
                logger.info("Test model %s failed (%s), trying next…", candidate, last_error[:80])
                continue
            # Other errors (auth, network) → stop immediately
            break

    return {"data": {"connected": False, "error": last_error}, "message": "Connection failed"}


async def _test_claude(api_key: str, model: str) -> dict:
    """Test connectivity using the Anthropic SDK."""
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)
        resp = await client.messages.create(
            model=model,
            max_tokens=5,
            messages=[{"role": "user", "content": "Hi"}],
        )
        model_id = getattr(resp, "model", model)
        return {"data": {"connected": True, "model": model_id}, "message": "ok"}
    except Exception as e:
        return {"data": {"connected": False, "error": str(e)}, "message": "Connection failed"}


# ── POST /model-providers/{id}/set-judge ────────────────────────────────────────
@router.post("/{provider_id}/set-judge", response_model=dict)
async def set_judge_default(provider_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ModelProvider).where(ModelProvider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise AppException(404, f"Provider {provider_id} not found")

    # Clear all existing judge defaults first
    await db.execute(
        update(ModelProvider)
        .where(ModelProvider.is_judge_default == True)
        .values(is_judge_default=False)
    )
    provider.is_judge_default = True

    # Notify analyzer to reset its cached client
    from app.services.ai_analyzer import reset_analyzer_client
    reset_analyzer_client()

    await db.commit()
    await db.refresh(provider)
    return {"data": _serialize(provider), "message": "Judge default updated"}


# ── POST /model-providers/{id}/set-generation ───────────────────────────────────
@router.post("/{provider_id}/set-generation", response_model=dict)
async def set_generation_default(provider_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ModelProvider).where(ModelProvider.id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise AppException(404, f"Provider {provider_id} not found")

    await db.execute(
        update(ModelProvider)
        .where(ModelProvider.is_generation_default == True)
        .values(is_generation_default=False)
    )
    provider.is_generation_default = True
    await db.commit()
    await db.refresh(provider)
    from app.services.llm_client import invalidate_provider_cache
    invalidate_provider_cache()
    return {"data": _serialize(provider), "message": "Generation default updated"}


# ── POST /model-providers/fetch-models ──────────────────────────────────────────
@router.post("/fetch-models", response_model=dict)
async def fetch_models(body: FetchModelsRequest, db: AsyncSession = Depends(get_db)):
    """Call GET /v1/models on the given provider and return chat-capable model ids.

    Accepts either a direct api_key or a provider_id (to use the saved key from DB).
    """
    api_key = body.api_key
    base_url_override = body.base_url
    provider_type = body.provider_type

    # If provider_id given, load the saved credentials
    if body.provider_id and not api_key:
        result = await db.execute(select(ModelProvider).where(ModelProvider.id == body.provider_id))
        saved = result.scalar_one_or_none()
        if not saved:
            raise AppException(404, f"Provider {body.provider_id} not found")
        api_key = first_api_key(saved.api_key)
        if not base_url_override:
            base_url_override = saved.base_url
        provider_type = saved.provider_type  # type: ignore[assignment]

    if not api_key:
        raise AppException(400, "api_key is required")

    # Claude uses a different authentication header and endpoint format
    if provider_type == "claude":
        return await _fetch_claude_models(api_key)

    chat_models = await _fetch_openai_compatible_model_ids(
        api_key=api_key,
        provider_type=provider_type,
        base_url_override=base_url_override,
    )
    return {"data": {"models": chat_models, "total": len(chat_models)}, "message": "ok"}


async def _fetch_claude_models(api_key: str) -> dict:
    """Fetch available models from the Anthropic models API.

    Anthropic requires x-api-key + anthropic-version headers instead of
    the OpenAI-style Authorization: Bearer header.
    """
    from app.services.llm_client import ANTHROPIC_VERSION
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://api.anthropic.com/v1/models",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": ANTHROPIC_VERSION,
                },
            )
        if resp.status_code != 200:
            raise AppException(502, f"Anthropic returned HTTP {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        raw_models: list[dict] = data.get("data", [])
        # Anthropic model objects: {"id": "claude-...", "display_name": "...", "type": "model"}
        # Filter to only claude-* chat models
        chat_models = sorted(
            [m["id"] for m in raw_models if isinstance(m, dict) and str(m.get("id", "")).startswith("claude")],
            key=lambda x: x.lower(),
        )
        return {"data": {"models": chat_models, "total": len(chat_models)}, "message": "ok"}
    except AppException:
        raise
    except Exception as e:
        raise AppException(502, f"Failed to fetch Anthropic models: {e}")
