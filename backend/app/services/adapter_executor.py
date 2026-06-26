import os
import time
from collections.abc import Mapping
from typing import Any
from urllib.parse import urljoin

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import AppException
from app.models import Adapter
from app.schemas.adapter import AdapterResponse
from app.services.adapter_extractors import extract_adapter_response
from app.services.adapter_renderer import build_adapter_context, render_template_tree
from app.services.error_utils import sanitize_error

HTTP_TIMEOUT_S = 30.0
CUSTOM_COMPAT_TIMEOUT_S = 60.0
MAX_ADAPTER_RESPONSE_BYTES = 1 * 1024 * 1024


def _parse_bool_header(value: str | None) -> bool | None:
    if value is None:
        return None
    v = value.strip().lower()
    if v in ("true", "1", "yes"):
        return True
    if v in ("false", "0", "no"):
        return False
    return None


def _extract_provenance_headers(headers: httpx.Headers) -> dict[str, Any] | None:
    """Extract X-Provenance-* headers into a dict, returns None if none found."""
    result: dict[str, Any] = {}
    mi = _parse_bool_header(headers.get("x-provenance-model-invoked"))
    if mi is not None:
        result["model_invoked"] = mi
    pp = _parse_bool_header(headers.get("x-provenance-post-processed"))
    if pp is not None:
        result["post_processed"] = pp
    br = headers.get("x-provenance-block-reason")
    if br is not None:
        result["block_reason"] = br.strip()
    pr = headers.get("x-provenance-post-reason")
    if pr is not None:
        result["post_reason"] = pr.strip()
    return result if result else None


def build_custom_compat_adapter(target_url: str, target_config: dict | None) -> dict[str, Any]:
    headers = ((target_config or {}).get("headers") or {}) if isinstance(target_config, Mapping) else {}
    resolved_target_url = str(target_url).strip()
    timeout_s = CUSTOM_COMPAT_TIMEOUT_S
    if isinstance(target_config, Mapping):
        raw_timeout = target_config.get("timeout_s")
        if isinstance(raw_timeout, (int, float)) and raw_timeout > 0:
            timeout_s = float(raw_timeout)
    return {
        "name": "custom-compat",
        "description": "Legacy custom target compatibility adapter",
        "mode": "direct_http_adapter",
        "transport": "http_json",
        "base_url": resolved_target_url,
        "auth_config": {"type": "none"},
        "session_config": {"mode": "per_variant_isolated"},
        "invoke_config": {
            "method": "POST",
            "path": resolved_target_url or "/",
            "headers": headers,
            "timeout_s": timeout_s,
            "body_template": {
                "message": "{{input.prompt}}",
                "history": "{{input.history}}",
            },
        },
        "response_extract": {"mode": "raw_text"},
        "enabled": True,
    }


def coerce_adapter_payload(adapter: Adapter | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(adapter, Mapping):
        return dict(adapter)
    if hasattr(adapter, "model_dump"):
        return adapter.model_dump(exclude_none=True)
    return AdapterResponse.model_validate(adapter).model_dump()


def _adapter_payload(adapter: Adapter | Mapping[str, Any]) -> dict[str, Any]:
    return coerce_adapter_payload(adapter)


def _resolve_secret_ref(secret_ref: str) -> str:
    ref = secret_ref.strip()
    if not ref:
        raise AppException(400, "auth_config.secret_ref cannot be empty")

    if ref.startswith("env:"):
        env_name = ref.split(":", 1)[1].strip()
        secret = os.getenv(env_name, "")
        if secret:
            return secret
        raise AppException(400, f"Secret reference env:{env_name} is not configured")

    if ref.startswith("settings:"):
        attr_name = ref.split(":", 1)[1].strip()
        secret = getattr(settings, attr_name, "")
        if secret:
            return str(secret)
        raise AppException(400, f"Secret reference settings:{attr_name} is not configured")

    env_secret = os.getenv(ref, "")
    if env_secret:
        return env_secret

    normalized_attr = ref.lower().replace("-", "_")
    attr_secret = getattr(settings, normalized_attr, "")
    if attr_secret:
        return str(attr_secret)

    raise AppException(400, f"Secret reference {ref} is not configured")


def _apply_auth(
    *,
    auth_config: Mapping[str, Any] | None,
    headers: dict[str, str],
    query: dict[str, Any],
) -> None:
    auth = dict(auth_config or {})
    auth_type = str(auth.get("type") or "none")
    if auth_type == "none":
        return

    secret_value = _resolve_secret_ref(str(auth.get("secret_ref") or ""))
    if auth_type == "bearer":
        scheme = str(auth.get("scheme") or "Bearer")
        headers["Authorization"] = f"{scheme} {secret_value}"
        return

    name = str(auth.get("name") or "").strip()
    if not name:
        raise AppException(400, "auth_config.name is required for header/query auth")
    if auth_type == "header":
        headers[name] = secret_value
        return
    if auth_type == "query":
        query[name] = secret_value
        return
    raise AppException(400, f"Unsupported auth type: {auth_type}")


def _normalize_body(value: Any) -> Any:
    if value is None:
        return None
    return value


def _build_invoke_body(
    adapter: Mapping[str, Any],
    invoke_config: Mapping[str, Any],
    context: Mapping[str, Any],
) -> Any:
    rendered_template = render_template_tree(invoke_config.get("body_template"), context)
    if adapter.get("transport") != "openai_chat":
        return _normalize_body(rendered_template)

    if rendered_template is not None:
        return _normalize_body(rendered_template)

    history = context.get("input", {}).get("history") if isinstance(context.get("input"), Mapping) else []
    prompt = context.get("input", {}).get("prompt") if isinstance(context.get("input"), Mapping) else ""
    system_prompt = invoke_config.get("system_prompt")
    messages: list[dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": render_template_tree(system_prompt, context)})
    if isinstance(history, list):
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    return {
        "model": invoke_config.get("model") or settings.openai_mini_model,
        "messages": messages,
    }


def _request_path(default_path: str, configured_path: Any) -> str:
    raw = str(configured_path or default_path).strip()
    if not raw:
        raw = default_path
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    if not raw.startswith("/"):
        return f"/{raw}"
    return raw


def _request_url(base_url: str, path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return urljoin(f"{base_url.rstrip('/')}/", path.lstrip("/"))


def _request_timeout_s(request_config: Mapping[str, Any]) -> float | None:
    raw_timeout = request_config.get("timeout_s")
    if isinstance(raw_timeout, (int, float)) and raw_timeout > 0:
        return float(raw_timeout)
    return None


async def _request_json(
    client: httpx.AsyncClient,
    *,
    adapter: Mapping[str, Any],
    request_config: Mapping[str, Any],
    context: Mapping[str, Any],
    is_invoke: bool,
) -> tuple[httpx.Response, dict[str, Any]]:
    transport = str(adapter.get("transport") or "http_json")
    default_path = "/chat/completions" if transport == "openai_chat" and is_invoke else "/"
    method = str(request_config.get("method") or "POST").upper()
    path = _request_path(default_path, render_template_tree(request_config.get("path") or default_path, context))
    headers = render_template_tree(request_config.get("headers") or {}, context) or {}
    query = render_template_tree(request_config.get("query") or {}, context) or {}
    body = (
        _build_invoke_body(adapter, request_config, context)
        if is_invoke
        else render_template_tree(request_config.get("body_template"), context)
    )
    headers = {str(key): str(value) for key, value in dict(headers).items() if value is not None}
    query = {str(key): value for key, value in dict(query).items() if value is not None}
    _apply_auth(auth_config=adapter.get("auth_config"), headers=headers, query=query)

    url = _request_url(str(adapter.get("base_url") or ""), path)
    kwargs: dict[str, Any] = {"headers": headers, "params": query}
    if method not in {"GET", "DELETE"} and body is not None:
        kwargs["json"] = body
    request_timeout = _request_timeout_s(request_config)
    if request_timeout is not None:
        kwargs["timeout"] = request_timeout

    response = await client.request(method, url, **kwargs)
    return response, {
        "method": method,
        "url": url,
        "headers": headers,
        "query": query,
        "body": body,
        "timeout_s": request_timeout or HTTP_TIMEOUT_S,
    }


async def request_adapter_http(
    client: httpx.AsyncClient,
    *,
    adapter: Mapping[str, Any],
    request_config: Mapping[str, Any],
    context: Mapping[str, Any],
    is_invoke: bool,
) -> tuple[httpx.Response, dict[str, Any]]:
    return await _request_json(
        client,
        adapter=adapter,
        request_config=request_config,
        context=context,
        is_invoke=is_invoke,
    )


async def execute_adapter_request(
    adapter: Adapter | Mapping[str, Any],
    *,
    prompt: str,
    history: list[dict] | None,
    runtime_vars: dict | None,
    scan_id: str | None,
    case_id: str | None,
    variant_type: str | None,
) -> dict[str, Any]:
    payload = _adapter_payload(adapter)
    if not payload.get("enabled", True):
        raise AppException(400, "Adapter is disabled")

    session_config = payload.get("session_config") or {"mode": "per_variant_isolated"}
    invoke_config = payload.get("invoke_config") or {}
    response_extract = payload.get("response_extract") or {}
    steps: list[dict[str, Any]] = []
    session_id: str | None = None
    rendered_request: dict[str, Any] | None = None
    transport_meta: dict[str, Any] = {
        "transport": payload.get("transport"),
        "base_url": payload.get("base_url"),
    }

    # Stage 1.1b — disable redirect-following so a 30x to a private/loopback
    # IP cannot bypass the URL guard. A 30x is now surfaced as the response
    # status; legitimate external endpoints rarely require redirect-chasing.
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_S, follow_redirects=False) as client:
        try:
            if session_config.get("create"):
                create_context = build_adapter_context(
                    runtime_vars=runtime_vars,
                    prompt=prompt,
                    history=history,
                    scan_id=scan_id,
                    case_id=case_id,
                    variant_type=variant_type,
                    session_id=None,
                )
                create_response, rendered_create = await _request_json(
                    client,
                    adapter=payload,
                    request_config=session_config["create"],
                    context=create_context,
                    is_invoke=False,
                )
                steps.append(
                    {
                        "name": "session_create",
                        "ok": create_response.is_success,
                        "detail": create_response.text[:240],
                        "status_code": create_response.status_code,
                    }
                )
                if not create_response.is_success:
                    return {
                        "success": False,
                        "response_status": "failed",
                        "response_text": None,
                        "response_error": f"Session create failed with HTTP {create_response.status_code}",
                        "transport_ok": True,
                        "http_status": create_response.status_code,
                        "content_type": create_response.headers.get("content-type"),
                        "session_id": None,
                        "transport_meta": {
                            **transport_meta,
                            "session_create": rendered_create,
                        },
                        "rendered_request": rendered_create,
                        "steps": steps,
                    }

                extracted = extract_adapter_response(
                    response_text=create_response.text,
                    response_extract={
                        "mode": "json_paths",
                        "text_path": session_config["create"]["extract"]["session_id"],
                    },
                    transport="http_json",
                )
                session_id = extracted.get("response_text")
                if not session_id:
                    return {
                        "success": False,
                        "response_status": "failed",
                        "response_text": None,
                        "response_error": extracted.get("response_error") or "Session create did not return session_id",
                        "transport_ok": True,
                        "http_status": create_response.status_code,
                        "content_type": create_response.headers.get("content-type"),
                        "session_id": None,
                        "transport_meta": {
                            **transport_meta,
                            "session_create": rendered_create,
                        },
                        "rendered_request": rendered_create,
                        "steps": steps,
                    }

            invoke_context = build_adapter_context(
                runtime_vars=runtime_vars,
                prompt=prompt,
                history=history,
                scan_id=scan_id,
                case_id=case_id,
                variant_type=variant_type,
                session_id=session_id,
            )
            invoke_started_at = time.perf_counter()
            invoke_response, rendered_request = await _request_json(
                client,
                adapter=payload,
                request_config=invoke_config,
                context=invoke_context,
                is_invoke=True,
            )
            latency_ms = (time.perf_counter() - invoke_started_at) * 1000
            if len(invoke_response.content) > MAX_ADAPTER_RESPONSE_BYTES:
                return {
                    "success": False,
                    "response_status": "failed",
                    "response_text": None,
                    "response_error": (
                        f"Adapter response too large ({len(invoke_response.content)} bytes, "
                        f"limit {MAX_ADAPTER_RESPONSE_BYTES})"
                    ),
                    "transport_ok": True,
                    "http_status": invoke_response.status_code,
                    "content_type": invoke_response.headers.get("content-type"),
                    "session_id": session_id,
                    "transport_meta": {
                        **transport_meta,
                        "latency_ms": latency_ms,
                        "status_code": invoke_response.status_code,
                    },
                    "rendered_request": rendered_request,
                    "steps": steps,
                }

            extracted = extract_adapter_response(
                response_text=invoke_response.text,
                response_extract=response_extract,
                transport=str(payload.get("transport") or "http_json"),
            )
            response_error = extracted.get("response_error")
            response_text = extracted.get("response_text")
            success = invoke_response.is_success and not response_error
            steps.append(
                {
                    "name": "invoke",
                    "ok": success,
                    "detail": response_error or (response_text[:240] if isinstance(response_text, str) else None),
                    "status_code": invoke_response.status_code,
                }
            )

            return {
                "success": success,
                "response_status": "completed" if success else "failed",
                "response_text": response_text,
                "response_error": (
                    response_error or
                    (f"Invoke failed with HTTP {invoke_response.status_code}" if not invoke_response.is_success else None)
                ),
                "transport_ok": True,
                "http_status": invoke_response.status_code,
                "content_type": invoke_response.headers.get("content-type"),
                "session_id": session_id,
                "transport_meta": {
                    **transport_meta,
                    "latency_ms": latency_ms,
                    "status_code": invoke_response.status_code,
                    "content_type": invoke_response.headers.get("content-type"),
                    "tool_calls": extracted.get("tool_calls"),
                    "provenance_headers": _extract_provenance_headers(invoke_response.headers),
                },
                "rendered_request": rendered_request,
                "steps": steps,
            }
        except AppException as exc:
            return {
                "success": False,
                "response_status": "failed",
                "response_text": None,
                "response_error": exc.detail,
                "transport_ok": False,
                "http_status": None,
                "content_type": None,
                "session_id": session_id,
                "transport_meta": transport_meta,
                "rendered_request": rendered_request,
                "steps": steps,
            }
        except Exception as exc:
            return {
                "success": False,
                "response_status": "failed",
                "response_text": None,
                "response_error": sanitize_error(exc),
                "transport_ok": False,
                "http_status": None,
                "content_type": None,
                "session_id": session_id,
                "transport_meta": transport_meta,
                "rendered_request": rendered_request,
                "steps": steps,
            }
        finally:
            if session_id and session_config.get("close"):
                close_context = build_adapter_context(
                    runtime_vars=runtime_vars,
                    prompt=prompt,
                    history=history,
                    scan_id=scan_id,
                    case_id=case_id,
                    variant_type=variant_type,
                    session_id=session_id,
                )
                try:
                    close_response, rendered_close = await _request_json(
                        client,
                        adapter=payload,
                        request_config=session_config["close"],
                        context=close_context,
                        is_invoke=False,
                    )
                    steps.append(
                        {
                            "name": "session_close",
                            "ok": close_response.is_success,
                            "detail": close_response.text[:240],
                            "status_code": close_response.status_code,
                        }
                    )
                    transport_meta["session_close"] = rendered_close
                except Exception as exc:
                    steps.append(
                        {
                            "name": "session_close",
                            "ok": False,
                            "detail": sanitize_error(exc),
                            "status_code": None,
                        }
                    )


async def get_adapter_or_raise(db: AsyncSession, adapter_id: str) -> Adapter:
    result = await db.execute(select(Adapter).where(Adapter.id == adapter_id))
    adapter = result.scalar_one_or_none()
    if not adapter:
        raise AppException(404, "Adapter not found")
    return adapter


async def resolve_task_adapter_payload(db: AsyncSession, adapter_id: str | None) -> dict[str, Any]:
    if not adapter_id:
        raise AppException(400, "adapter_id is required for adapter scans")
    adapter = await get_adapter_or_raise(db, adapter_id)
    if not adapter.enabled:
        raise AppException(400, "Adapter is disabled")
    return _adapter_payload(adapter)
