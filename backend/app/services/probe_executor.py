import json
from collections.abc import Mapping
from typing import Any

import httpx

from app.core.exceptions import AppException
from app.schemas.adapter import (
    AdapterCreate,
    AdapterProbeConfig,
    AdapterProbeTestResponse,
    ProbeStepResult,
    ProbeTestResponse,
)
from app.services.adapter_executor import HTTP_TIMEOUT_S, coerce_adapter_payload, request_adapter_http
from app.services.adapter_extractors import extract_json_path_value
from app.services.adapter_renderer import build_adapter_context
from app.services.error_utils import sanitize_error
from app.services.probe_assertions import evaluate_probe_assertions


def resolve_probe_config(
    adapter: AdapterCreate | Mapping[str, Any],
    override: AdapterProbeConfig | Mapping[str, Any] | None = None,
) -> AdapterProbeConfig:
    if override is not None:
        return (
            override
            if isinstance(override, AdapterProbeConfig)
            else AdapterProbeConfig.model_validate(override)
        )

    payload = coerce_adapter_payload(adapter)
    probe_config = payload.get("probe_config")
    if probe_config is None:
        raise AppException(400, "probe_config is required")
    return (
        probe_config
        if isinstance(probe_config, AdapterProbeConfig)
        else AdapterProbeConfig.model_validate(probe_config)
    )


async def execute_probe(
    adapter: AdapterCreate | Mapping[str, Any],
    *,
    probe_config: AdapterProbeConfig | Mapping[str, Any] | None = None,
    runtime_vars: dict[str, Any] | None,
    session_id: str | None,
    scan_id: str | None,
    case_id: str | None,
    variant_type: str | None,
) -> ProbeTestResponse:
    adapter_payload = coerce_adapter_payload(adapter)
    if not adapter_payload.get("enabled", True):
        raise AppException(400, "Adapter is disabled")

    resolved_probe = resolve_probe_config(adapter_payload, probe_config)
    if not resolved_probe.enabled:
        raise AppException(400, "probe_config is disabled")

    step_results: list[dict[str, Any]] = []
    runtime_probe_steps: dict[str, Any] = {}

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_S, follow_redirects=True) as client:
        for step in resolved_probe.steps:
            context = build_adapter_context(
                runtime_vars=runtime_vars,
                prompt="",
                history=[],
                scan_id=scan_id,
                case_id=case_id,
                variant_type=variant_type,
                session_id=session_id,
                probe_steps=runtime_probe_steps,
            )
            try:
                response, rendered_request = await request_adapter_http(
                    client,
                    adapter=adapter_payload,
                    request_config=step.model_dump(exclude_none=True, exclude={"name", "captures"}),
                    context=context,
                    is_invoke=False,
                )
            except AppException as exc:
                return _failure_response(
                    step_results=step_results,
                    failing_step=step.name,
                    failure_type=_classify_app_exception(exc),
                    failure_reason=exc.detail,
                )
            except httpx.TimeoutException:
                return _failure_response(
                    step_results=step_results,
                    failing_step=step.name,
                    failure_type="timeout",
                    failure_reason="Probe step timed out",
                )
            except httpx.HTTPError as exc:
                return _failure_response(
                    step_results=step_results,
                    failing_step=step.name,
                    failure_type="transport_error",
                    failure_reason=sanitize_error(exc),
                )
            except Exception as exc:
                return _failure_response(
                    step_results=step_results,
                    failing_step=step.name,
                    failure_type="transport_error",
                    failure_reason=sanitize_error(exc),
                )

            if response.status_code in {401, 403}:
                return _failure_response(
                    step_results=step_results,
                    failing_step=step.name,
                    failure_type="auth_error",
                    failure_reason=f"Probe step returned HTTP {response.status_code}",
                    status_code=response.status_code,
                    rendered_request=rendered_request,
                    response_text=response.text,
                )

            capture_values: dict[str, Any] = {}
            if step.captures:
                try:
                    payload = json.loads(response.text)
                except json.JSONDecodeError as exc:
                    return _failure_response(
                        step_results=step_results,
                        failing_step=step.name,
                        failure_type="extract_error",
                        failure_reason=f"Probe capture JSON parse failed: {exc}",
                        status_code=response.status_code,
                        rendered_request=rendered_request,
                        response_text=response.text,
                    )

                for capture_name, capture in step.captures.items():
                    capture_value = extract_json_path_value(payload, capture.json_path)
                    if capture_value is None:
                        return _failure_response(
                            step_results=step_results,
                            failing_step=step.name,
                            failure_type="extract_error",
                            failure_reason=(
                                f"Probe capture {capture_name} did not match path {capture.json_path}"
                            ),
                            status_code=response.status_code,
                            rendered_request=rendered_request,
                            response_text=response.text,
                        )
                    capture_values[capture_name] = capture_value

            step_result = {
                "name": step.name,
                "ok": True,
                "status_code": response.status_code,
                "failure_type": None,
                "failure_reason": None,
                "captures": capture_values,
                "rendered_request": rendered_request,
                "response_preview": response.text[:240],
                "response_text": response.text,
            }
            step_results.append(step_result)
            runtime_probe_steps[step.name] = {
                "status_code": response.status_code,
                "text": response.text,
                "captures": capture_values,
            }

    assertion_results, evidence, verified, failure_reason = evaluate_probe_assertions(
        resolved_probe.assertions,
        step_results=step_results,
    )
    failure_type = None if verified else "assertion_failed"

    return AdapterProbeTestResponse(
        success=verified,
        verified=verified,
        assertion_results=assertion_results,
        evidence=evidence,
        failure_reason=failure_reason,
        failure_type=failure_type,
        step_results=[ProbeStepResult.model_validate(_step_result_public(step)) for step in step_results],
    )


def _step_result_public(step: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "name": step.get("name"),
        "ok": step.get("ok"),
        "status_code": step.get("status_code"),
        "failure_type": step.get("failure_type"),
        "failure_reason": step.get("failure_reason"),
        "captures": step.get("captures") or {},
        "rendered_request": step.get("rendered_request"),
        "response_preview": step.get("response_preview"),
    }


def _failure_response(
    *,
    step_results: list[dict[str, Any]],
    failing_step: str,
    failure_type: str,
    failure_reason: str,
    status_code: int | None = None,
    rendered_request: dict[str, Any] | None = None,
    response_text: str | None = None,
) -> ProbeTestResponse:
    step_results = [
        *step_results,
        {
            "name": failing_step,
            "ok": False,
            "status_code": status_code,
            "failure_type": failure_type,
            "failure_reason": failure_reason,
            "captures": {},
            "rendered_request": rendered_request,
            "response_preview": response_text[:240] if isinstance(response_text, str) else None,
        },
    ]
    return AdapterProbeTestResponse(
        success=False,
        verified=False,
        assertion_results=[],
        evidence=[],
        failure_reason=failure_reason,
        failure_type=failure_type,
        step_results=[ProbeStepResult.model_validate(_step_result_public(step)) for step in step_results],
    )


def _classify_app_exception(exc: AppException) -> str:
    detail = str(exc.detail).lower()
    if "auth" in detail or "secret" in detail or "401" in detail or "403" in detail:
        return "auth_error"
    if "template" in detail or "unsupported template variable" in detail:
        return "render_error"
    return "transport_error"
