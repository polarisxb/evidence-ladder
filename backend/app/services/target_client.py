"""Target communication layer.

Handles all outbound requests to attack targets:
- builtin_vulnerable (local in-process)
- openai_compatible (OpenAI API or compatible endpoint)
- adapter / custom  (via adapter_executor)
- raw HTTP (legacy custom mode)

Extracted from scan_runner.py to give this concern a clear module boundary,
making it independently testable and independently importable.
"""
from __future__ import annotations

import asyncio

import httpx

from app.config import settings
from app.services.response_screening import TargetResponseEnvelope
from app.services.error_utils import sanitize_error
from app.services.adapter_executor import (
    build_custom_compat_adapter,
    execute_adapter_request,
)
from app.services.llm_client import (
    LLMConfigurationError,
    ProviderClientInfo,
    get_generation_provider,
    get_provider_by_id,
)
from app.services.llm_scheduler import schedule_fixed_call
from app.services.url_guard import UnsafeTargetURL, validate_target_url
from app.services.vulnerable_ai import chat_with_vulnerable_ai

TARGET_MODEL_TIMEOUT_S: float = 60.0
MAX_RESPONSE_BYTES: int = 1 * 1024 * 1024  # 1 MB


def _canonical_openai_base_url(url: str | None) -> str:
    normalized = (url or "").strip().rstrip("/")
    if normalized.endswith("/v1"):
        normalized = normalized[:-3]
    return normalized


def is_platform_openai_target(target_url: str | None) -> bool:
    normalized_target = _canonical_openai_base_url(target_url)
    if not normalized_target or normalized_target == "default":
        return True
    platform_base = _canonical_openai_base_url(settings.openai_base_url)
    return bool(platform_base and normalized_target == platform_base)


async def send_to_target(
    payload: str,
    target_url: str,
    target_type: str,
    target_config: dict | None,
    conversation_history: list[dict] | None = None,
) -> str:
    """Send a payload to the configured target and return the response text."""
    internal_config = dict(target_config or {}) if isinstance(target_config, dict) else {}

    if target_type == "builtin_vulnerable":
        level = (target_config or {}).get("vulnerable_level", 1)
        return await chat_with_vulnerable_ai(
            payload, level=level, conversation_history=conversation_history,
        )

    if target_type == "claude":
        cfg = target_config or {}
        provider_id = (cfg.get("provider_id") or "").strip() or None
        api_key = (cfg.get("api_key") or "").strip() or None

        # 优先使用 provider_id 关联的供应商凭证
        if provider_id:
            try:
                resolved = await get_provider_by_id(provider_id, role="target")
            except LLMConfigurationError as exc:
                return f"[ERROR] {exc}"
            if not resolved:
                return "[ERROR] 指定的供应商不存在或已禁用"
            provider, default_model = resolved
            if provider.provider_type != "claude":
                return (
                    f"[ERROR] Claude 目标需要 claude 类型的供应商，"
                    f"但「{provider_id}」的类型是 {provider.provider_type}"
                )
            model = (cfg.get("model") or default_model or "claude-haiku-4-5").strip()
        elif api_key:
            provider = ProviderClientInfo(provider_type="claude", api_key=api_key)
            model = (cfg.get("model") or "claude-haiku-4-5").strip()
        else:
            return "[ERROR] Claude target requires api_key or provider_id in target_config"

        system_prompt = cfg.get("system_prompt") or "You are a helpful assistant."
        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": payload})
        try:
            return await schedule_fixed_call(
                provider,
                model,
                messages,
                role="target",
                temperature=0.7,
                max_tokens=500,
            )
        except asyncio.TimeoutError:
            return f"[ERROR] Claude target request timed out after {int(TARGET_MODEL_TIMEOUT_S)}s"
        except Exception as e:
            return f"[ERROR] {sanitize_error(e)}"

    if target_type == "openai_compatible":
        cfg = target_config or {}
        provider_id = (cfg.get("provider_id") or "").strip() or None
        user_api_key = (cfg.get("api_key") or "").strip() or None
        target_is_platform = is_platform_openai_target(target_url)

        # 解析优先级: provider_id > 手动 api_key > 平台默认
        if provider_id:
            # 使用预配置供应商的凭证
            try:
                resolved = await get_provider_by_id(provider_id, role="target")
            except LLMConfigurationError as exc:
                return f"[ERROR] {exc}"
            if not resolved:
                return "[ERROR] 指定的供应商不存在或已禁用"
            provider, default_model = resolved
            if provider.provider_type == "claude":
                return (
                    "[ERROR] OpenAI 兼容目标不能使用 Claude 类型的供应商，"
                    "请切换到 Claude 目标类型或选择其他供应商"
                )
            model = cfg.get("model") or default_model
            # 允许用户手动指定的 target_url 覆盖供应商默认的 base_url
            override_url = target_url.strip() if target_url else ""
            if override_url:
                provider = ProviderClientInfo(
                    provider_type=provider.provider_type,
                    api_key=provider.api_key,
                    base_url=override_url,
                )
        elif user_api_key:
            model = cfg.get("model")
            if not model:
                if target_is_platform:
                    model = settings.openai_mini_model
                else:
                    return (
                        "[ERROR] Custom OpenAI-compatible targets require an explicit model. "
                        "Select a provider or fill target_config.model before running the scan."
                    )
            base_url = settings.openai_base_url if target_is_platform else (target_url or None)
            provider = ProviderClientInfo(
                provider_type="custom",
                api_key=user_api_key,
                base_url=base_url,
            )
        elif target_is_platform:
            try:
                provider, gen_model = await get_generation_provider()
            except LLMConfigurationError as exc:
                return f"[ERROR] {exc}"
            model = cfg.get("model") or gen_model
        else:
            return (
                "[ERROR] Custom OpenAI-compatible targets require an API key in target_config. "
                "The platform key is not forwarded to third-party endpoints."
            )

        system_prompt = cfg.get("system_prompt") or "You are a helpful assistant."

        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": payload})

        try:
            return await schedule_fixed_call(
                provider,
                model,
                messages,
                role="target",
                temperature=0.7,
                max_tokens=500,
            )
        except asyncio.TimeoutError:
            return f"[ERROR] Target model request timed out after {int(TARGET_MODEL_TIMEOUT_S)}s"
        except Exception as e:
            return f"[ERROR] {sanitize_error(e)}"

    if target_type in {"adapter", "custom"}:
        adapter_payload = internal_config.get("__resolved_adapter")
        if target_type == "custom":
            adapter_payload = adapter_payload or build_custom_compat_adapter(target_url, target_config)
        if not adapter_payload:
            return "[ERROR] Adapter target is not configured"

        result = await execute_adapter_request(
            adapter_payload,
            prompt=payload,
            history=conversation_history,
            runtime_vars=internal_config.get("__runtime_vars"),
            scan_id=internal_config.get("__scan_id"),
            case_id=internal_config.get("__case_id"),
            variant_type=internal_config.get("__variant_type"),
        )
        if result.get("success"):
            return str(result.get("response_text") or "")
        return f"[ERROR] {result.get('response_error') or 'Adapter request failed'}"

    # Defense-in-depth SSRF guard: this raw-HTTP egress posts directly to a
    # user-supplied URL. The API ingress already validates target URLs, but
    # re-validate here so no future caller bypasses the guard.
    try:
        validate_target_url(target_url)
    except UnsafeTargetURL as e:
        return f"[ERROR] {e.detail}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = (target_config or {}).get("headers") or {}
        body: dict = {"message": payload}
        if conversation_history:
            body["history"] = conversation_history
        try:
            # Stream and enforce the size cap incrementally so an oversized
            # (or malicious) response is never fully buffered into memory.
            async with client.stream("POST", target_url, json=body, headers=headers) as resp:
                chunks: list[bytes] = []
                total = 0
                async for chunk in resp.aiter_bytes():
                    total += len(chunk)
                    if total > MAX_RESPONSE_BYTES:
                        return f"[ERROR] Response too large (exceeds {MAX_RESPONSE_BYTES} byte limit)"
                    chunks.append(chunk)
                raw = b"".join(chunks)
                encoding = resp.encoding or "utf-8"
                try:
                    return raw.decode(encoding, errors="replace")
                except LookupError:
                    return raw.decode("utf-8", errors="replace")
        except Exception as e:
            return f"[ERROR] {sanitize_error(e)}"


def build_send_target_config(
    task,  # ScanTask — avoid circular import by not type-hinting here
    *,
    case_id: str,
    variant_type: str,
) -> dict:
    """Build the internal config dict used by _send_to_target and variant execution."""
    config = dict(task.target_config or {}) if isinstance(task.target_config, dict) else {}
    config["__runtime_vars"] = task.runtime_vars or {}
    config["__scan_id"] = task.id
    config["__case_id"] = case_id
    config["__variant_type"] = variant_type

    resolved_adapter = getattr(task, "_resolved_adapter_payload", None)
    if resolved_adapter:
        config["__resolved_adapter"] = resolved_adapter
    return config


async def invoke_target_with_envelope(
    task,
    payload: str,
    *,
    case_id: str,
    variant_type: str,
    conversation_history: list[dict] | None = None,
) -> TargetResponseEnvelope:
    send_config = build_send_target_config(task, case_id=case_id, variant_type=variant_type)
    default_origin = "model" if task.target_type in {"builtin_vulnerable", "claude", "openai_compatible"} else "unknown"
    default_confidence = "high" if default_origin == "model" else "low"

    if task.target_type in {"adapter", "custom"}:
        adapter_payload = send_config.get("__resolved_adapter")
        if task.target_type == "custom":
            adapter_payload = adapter_payload or build_custom_compat_adapter(
                task.target_url, task.target_config
            )
        result = await execute_adapter_request(
            adapter_payload,
            prompt=payload,
            history=conversation_history,
            runtime_vars=send_config.get("__runtime_vars"),
            scan_id=send_config.get("__scan_id"),
            case_id=send_config.get("__case_id"),
            variant_type=send_config.get("__variant_type"),
        )
        return TargetResponseEnvelope(
            response_text=str(result.get("response_text") or "") or None,
            response_error=result.get("response_error"),
            response_status=result.get("response_status"),
            session_id=result.get("session_id"),
            target_type=task.target_type,
            transport_ok=bool(result.get("transport_ok", result.get("success", False))),
            http_status=(
                int(result["http_status"])
                if isinstance(result.get("http_status"), int)
                else (
                    int(result["http_status"])
                    if isinstance(result.get("http_status"), float)
                    else None
                )
            ),
            content_type=(
                str(result.get("content_type"))
                if result.get("content_type") is not None
                else None
            ),
            transport_meta=result.get("transport_meta") if isinstance(result.get("transport_meta"), dict) else {},
            response_origin="unknown",
            origin_confidence="low",
            evaluation_validity="evaluable",
        )

    response_text = await send_to_target(
        payload,
        task.target_url,
        task.target_type,
        send_config,
        conversation_history=conversation_history,
    )
    response_error = (
        response_text
        if isinstance(response_text, str)
        and (response_text.strip().lower().startswith("[error]") or response_text.strip().lower().startswith("error:"))
        else None
    )
    return TargetResponseEnvelope(
        response_text=response_text,
        response_error=response_error,
        response_status="failed" if response_error else "completed",
        session_id=None,
        target_type=task.target_type,
        transport_ok=response_error is None,
        http_status=None,
        content_type=None,
        transport_meta={},
        response_origin=default_origin,
        origin_confidence=default_confidence,
        evaluation_validity="evaluable",
    )


async def send_to_target_with_result(
    task,
    payload: str,
    *,
    case_id: str,
    variant_type: str,
    conversation_history: list[dict] | None = None,
) -> tuple[str, str | None]:
    """Send a payload and return (response_text, session_id)."""
    envelope = await invoke_target_with_envelope(
        task,
        payload,
        case_id=case_id,
        variant_type=variant_type,
        conversation_history=conversation_history,
    )
    response_text = str(envelope.response_text or "")
    if envelope.response_error and not response_text:
        response_text = f"[ERROR] {envelope.response_error}"
    return response_text, envelope.session_id
