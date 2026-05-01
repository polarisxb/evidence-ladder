from __future__ import annotations

from collections.abc import Mapping
import json as _json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.report import AnalysisResult

ResponseOrigin = Literal[
    "model",
    "app_fallback",
    "transport_error",
    "adapter_error",
    "gateway_error",
    "unknown",
]
OriginConfidence = Literal["high", "medium", "low"]
EvaluationValidity = Literal["evaluable", "not_evaluable"]

_DIRECT_MODEL_TARGET_TYPES = {"builtin_vulnerable", "claude", "openai_compatible"}
_ADAPTER_TARGET_TYPES = {"adapter", "custom"}
_TRANSPORT_ERROR_MARKERS = (
    "timeout",
    "timed out",
    "connection refused",
    "connection reset",
    "network is unreachable",
    "name or service not known",
    "temporary failure in name resolution",
    "dns",
    "tls",
    "ssl",
)
_HTML_ERROR_MARKERS = (
    "<html",
    "<body",
    "<title>",
    "502 bad gateway",
    "503 service unavailable",
    "504 gateway timeout",
    "nginx",
    "cloudflare",
)
KNOWN_FALLBACK_SIGNATURES: dict[str, str] = {
    "technical_difficulties_support_line": "i'm experiencing technical difficulties. please contact our support line.",
}
_NOT_EVALUABLE_REASON_MESSAGES = {
    "known_fallback": "The response matched a known non-model fallback template.",
    "configured_origin_rule": "The response matched a target-configured non-model response rule.",
    "transport_error": "The request failed before a stable model response could be evaluated.",
    "http_error": "The endpoint returned a non-success HTTP status instead of a stable model response.",
    "adapter_error": "The adapter reported a failure instead of returning a stable model response.",
    "extract_error": "The adapter response could not be extracted into a stable model reply.",
    "html_error": "The endpoint returned an HTML or gateway error page instead of model output.",
    "empty_response": "The endpoint returned an empty response, so there is no model output to evaluate.",
    "execution_error": "The target returned an execution error instead of model output.",
    "blocked_by_target": "The target system explicitly reported that the request did not reach the LLM.",
}


ProvenanceSource = Literal[
    "target_header",
    "target_body",
    "origin_rule",
    "known_fallback",
    "heuristic",
    "target_type_default",
    "none",
]


class ResponseEvaluation(BaseModel):
    response_origin: ResponseOrigin = "unknown"
    origin_confidence: OriginConfidence = "low"
    evaluation_validity: EvaluationValidity = "evaluable"
    invalid_reason: str | None = None
    matched_signature: str | None = None
    transport_ok: bool = True
    http_status: int | None = None
    content_type: str | None = None
    evidence_codes: list[str] = Field(default_factory=list)
    # Populated by case_executor after screening when the primary
    # response is not_evaluable with a transport-layer invalid_reason
    # (see ``app.services.health_probe.BASELINE_PROBE_TRIGGER_REASONS``).
    # Lets the UI turn a generic ``transport_error`` into either
    # "target online, payload triggered exception" or "target offline".
    baseline_probe: dict | None = None
    # ---- Two-dimensional Provenance (see docs/dev-notes/provenance-protocol.md) ----
    model_invoked: bool | None = None
    post_processed: bool | None = None
    block_reason: str | None = None
    post_reason: str | None = None
    provenance_source: ProvenanceSource | None = None


class TargetResponseEnvelope(BaseModel):
    response_text: str | None = None
    response_error: str | None = None
    response_status: str | None = None
    session_id: str | None = None
    target_type: str
    transport_ok: bool = True
    http_status: int | None = None
    content_type: str | None = None
    transport_meta: dict[str, Any] = Field(default_factory=dict)
    response_origin: ResponseOrigin = "unknown"
    origin_confidence: OriginConfidence = "low"
    evaluation_validity: EvaluationValidity = "evaluable"
    invalid_reason: str | None = None
    matched_signature: str | None = None


def _coerce_bool(value: Any) -> bool | None:
    """Coerce a value to bool, handling JSON booleans and string representations."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "1", "yes"):
            return True
        if v in ("false", "0", "no"):
            return False
    return None


def _normalized_string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _lowered(value: Any) -> str:
    return _normalized_string(value).lower()


def _looks_like_error_prefix(text: str) -> bool:
    lowered = _lowered(text)
    return lowered.startswith("[error]") or lowered.startswith("error:")


def _looks_like_html_error_page(response_text: str, content_type: str | None) -> bool:
    lowered = _lowered(response_text)
    lowered_content_type = _lowered(content_type)
    if lowered_content_type.startswith("text/html"):
        return True
    return any(marker in lowered for marker in _HTML_ERROR_MARKERS)


def _contains_transport_error(text: str) -> bool:
    lowered = _lowered(text)
    return any(marker in lowered for marker in _TRANSPORT_ERROR_MARKERS)


def _default_origin(target_type: str) -> tuple[ResponseOrigin, OriginConfidence]:
    if target_type in _DIRECT_MODEL_TARGET_TYPES:
        return "model", "high"
    return "unknown", "low"


def _origin_rule_values(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        text = _normalized_string(item)
        if text:
            normalized.append(text)
    return normalized


def origin_rules_from_target_config(target_config: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(target_config, Mapping):
        return None
    rules = target_config.get("origin_rules")
    if not isinstance(rules, Mapping):
        return None

    normalized: dict[str, Any] = {}
    for key in ("exact", "contains", "regex"):
        values = _origin_rule_values(rules.get(key))
        if values:
            normalized[key] = values
    structured = rules.get("structured")
    if isinstance(structured, list) and structured:
        normalized["structured"] = structured
    return normalized or None


def _match_configured_origin_rule(
    response_text: str,
    origin_rules: Mapping[str, Any] | None,
) -> tuple[str | None, list[str]]:
    if not isinstance(origin_rules, Mapping):
        return None, []

    lowered_text = _lowered(response_text)
    for rule in _origin_rule_values(origin_rules.get("exact")):
        if lowered_text == rule.lower():
            return f"origin_rule:exact:{rule}", ["configured_origin_rule", "origin_rule_exact"]

    for rule in _origin_rule_values(origin_rules.get("contains")):
        if rule.lower() in lowered_text:
            return f"origin_rule:contains:{rule}", ["configured_origin_rule", "origin_rule_contains"]

    for pattern in _origin_rule_values(origin_rules.get("regex")):
        try:
            if re.search(pattern, response_text, re.IGNORECASE):
                return f"origin_rule:regex:{pattern}", ["configured_origin_rule", "origin_rule_regex"]
        except re.error:
            continue

    return None, []


def _resolve_json_path(data: Any, path: str) -> tuple[Any, bool]:
    """Resolve a simplified JSON path like '$.a.b.c'.

    Returns (value, found). If path starts with 'header:' it reads from
    transport_meta instead.
    """
    if not isinstance(path, str) or not path:
        return None, False
    parts = path.lstrip("$").strip(".").split(".")
    current = data
    for part in parts:
        if not part:
            continue
        if isinstance(current, Mapping):
            if part in current:
                current = current[part]
            else:
                return None, False
        else:
            return None, False
    return current, True


def _match_structured_origin_rules(
    response_text: str,
    origin_rules: Mapping[str, Any] | None,
    transport_meta: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Evaluate structured origin rules against parsed JSON body / headers.

    Returns a dict with mark / reason / label / matched_rule if a rule matches,
    else None.
    """
    if not isinstance(origin_rules, Mapping):
        return None
    structured = origin_rules.get("structured")
    if not isinstance(structured, list) or not structured:
        return None

    # Parse body once
    body: dict | None = None
    if response_text.strip().startswith("{"):
        try:
            body = _json.loads(response_text)
            if not isinstance(body, dict):
                body = None
        except Exception:
            body = None

    for rule in structured:
        if not isinstance(rule, Mapping):
            continue
        field = str(rule.get("field") or "")
        op = str(rule.get("op") or "eq").lower()
        expected = rule.get("value", True)

        # Resolve field value
        if field.startswith("header:"):
            header_name = field[len("header:"):].strip()
            meta = dict(transport_meta or {})
            prov_h = meta.get("provenance_headers") or {}
            actual, found = prov_h.get(header_name), header_name in (prov_h or {})
            if not found:
                actual, found = meta.get(header_name), header_name in meta
        elif field.startswith("$.") and body is not None:
            actual, found = _resolve_json_path(body, field)
        else:
            continue

        # Evaluate operator
        matched = False
        if op == "exists":
            matched = found
        elif op == "not_exists":
            matched = not found
        elif op == "eq":
            matched = found and actual == expected
        elif op == "ne":
            matched = found and actual != expected
        elif op == "contains":
            matched = found and isinstance(actual, str) and str(expected) in actual
        else:
            continue

        if matched:
            return {
                "mark": str(rule.get("mark") or "blocked"),
                "reason": rule.get("reason"),
                "label": rule.get("label"),
                "matched_rule": f"structured:{field}:{op}:{expected}",
            }

    return None


def _derive_response_origin(
    model_invoked: bool | None,
    post_processed: bool | None,
    current_origin: ResponseOrigin,
) -> ResponseOrigin:
    """Derive the legacy response_origin enum from two-dimensional provenance."""
    if current_origin in ("transport_error", "adapter_error", "gateway_error"):
        return current_origin
    if model_invoked is False:
        return "app_fallback"
    if model_invoked is True and not post_processed:
        return "model"
    if model_invoked is True and post_processed is True:
        return "app_fallback"
    return current_origin


def _extract_provenance_from_envelope(
    envelope: TargetResponseEnvelope,
) -> dict[str, Any] | None:
    """Try to extract provenance signals from transport_meta (Level 1).

    Returns a dict with model_invoked / post_processed / block_reason /
    post_reason if any provenance signal is found, else None.
    """
    meta = envelope.transport_meta or {}
    # Priority 1: X-Provenance-* headers captured by adapter_executor
    prov = meta.get("provenance_headers")
    if isinstance(prov, Mapping) and prov:
        return {"source": "target_header", **prov}

    # Priority 2: _provenance field inside JSON response body
    response_text = _normalized_string(envelope.response_text)
    if response_text.startswith("{"):
        try:
            body = _json.loads(response_text)
            if isinstance(body, dict):
                prov_body = body.get("_provenance")
                if isinstance(prov_body, dict):
                    result: dict[str, Any] = {"source": "target_body"}
                    if "model_invoked" in prov_body:
                        val = prov_body["model_invoked"]
                        result["model_invoked"] = _coerce_bool(val)
                    if "post_processed" in prov_body:
                        val = prov_body["post_processed"]
                        result["post_processed"] = _coerce_bool(val)
                    if isinstance(prov_body.get("block_reason"), str):
                        result["block_reason"] = prov_body["block_reason"]
                    if isinstance(prov_body.get("post_reason"), str):
                        result["post_reason"] = prov_body["post_reason"]
                    if len(result) > 1:  # has more than just "source"
                        return result
        except Exception:
            pass
    return None


def _build_evaluation(
    envelope: TargetResponseEnvelope,
    *,
    response_origin: ResponseOrigin,
    origin_confidence: OriginConfidence,
    evaluation_validity: EvaluationValidity,
    invalid_reason: str | None = None,
    matched_signature: str | None = None,
    evidence_codes: list[str] | None = None,
    model_invoked: bool | None = None,
    post_processed: bool | None = None,
    block_reason: str | None = None,
    post_reason: str | None = None,
    provenance_source: "ProvenanceSource | None" = None,
) -> ResponseEvaluation:
    # When provenance signals are available, derive legacy response_origin
    if model_invoked is not None or post_processed is not None:
        response_origin = _derive_response_origin(model_invoked, post_processed, response_origin)
        if model_invoked is not None and origin_confidence == "low":
            origin_confidence = "high"
    return ResponseEvaluation(
        response_origin=response_origin,
        origin_confidence=origin_confidence,
        evaluation_validity=evaluation_validity,
        invalid_reason=invalid_reason,
        matched_signature=matched_signature,
        transport_ok=bool(envelope.transport_ok),
        http_status=envelope.http_status,
        content_type=_normalized_string(envelope.content_type) or None,
        evidence_codes=list(evidence_codes or []),
        model_invoked=model_invoked,
        post_processed=post_processed,
        block_reason=block_reason,
        post_reason=post_reason,
        provenance_source=provenance_source,
    )


def screen_response_origin(
    envelope: TargetResponseEnvelope,
    *,
    origin_rules: Mapping[str, Any] | None = None,
) -> ResponseEvaluation:
    response_text = _normalized_string(envelope.response_text)
    response_error = _normalized_string(envelope.response_error)
    combined_text = "\n".join(part for part in (response_error, response_text) if part)
    lowered_text = response_text.lower()
    default_origin, default_confidence = _default_origin(envelope.target_type)

    # ---- Level 1: Provenance protocol (header or body) ----
    provenance = _extract_provenance_from_envelope(envelope)
    if provenance is not None:
        prov_source: ProvenanceSource = provenance.pop("source", "target_header")
        mi = provenance.get("model_invoked")
        pp = provenance.get("post_processed")
        br = provenance.get("block_reason")
        pr = provenance.get("post_reason")
        ev_validity: EvaluationValidity = "evaluable"
        ev_invalid_reason: str | None = None
        # If the target explicitly says the model was NOT invoked, mark not_evaluable
        if mi is False:
            ev_validity = "not_evaluable"
            ev_invalid_reason = "blocked_by_target"
        return _build_evaluation(
            envelope,
            response_origin=default_origin,
            origin_confidence="high",
            evaluation_validity=ev_validity,
            invalid_reason=ev_invalid_reason,
            evidence_codes=["provenance_protocol"],
            model_invoked=mi,
            post_processed=pp,
            block_reason=br,
            post_reason=pr,
            provenance_source=prov_source,
        )

    # ---- Level 2: known fallback signatures ----
    for signature_name, signature_value in KNOWN_FALLBACK_SIGNATURES.items():
        if lowered_text == signature_value:
            return _build_evaluation(
                envelope,
                response_origin="app_fallback",
                origin_confidence="high",
                evaluation_validity="not_evaluable",
                invalid_reason="known_fallback",
                matched_signature=signature_name,
                evidence_codes=["known_fallback_signature"],
                model_invoked=False,
                post_processed=False,
                provenance_source="known_fallback",
            )

    # ---- Level 2b: user-configured origin_rules (text matching) ----
    configured_signature, configured_evidence = _match_configured_origin_rule(
        response_text,
        origin_rules,
    )
    if configured_signature is not None:
        return _build_evaluation(
            envelope,
            response_origin="app_fallback",
            origin_confidence="high",
            evaluation_validity="not_evaluable",
            invalid_reason="configured_origin_rule",
            matched_signature=configured_signature,
            evidence_codes=configured_evidence,
            model_invoked=False,
            post_processed=False,
            provenance_source="origin_rule",
        )

    # ---- Level 2c: structured origin_rules (JSON path / header matching) ----
    structured_match = _match_structured_origin_rules(
        response_text, origin_rules, envelope.transport_meta,
    )
    if structured_match is not None:
        mark = structured_match["mark"]
        s_mi: bool | None = None
        s_pp: bool | None = None
        s_ev: EvaluationValidity = "evaluable"
        s_inv: str | None = None
        if mark == "blocked":
            s_mi, s_pp = False, False
            s_ev = "not_evaluable"
            s_inv = "configured_origin_rule"
        elif mark == "model":
            s_mi, s_pp = True, False
        elif mark == "post_processed":
            s_mi, s_pp = True, True
        return _build_evaluation(
            envelope,
            response_origin=default_origin,
            origin_confidence="high",
            evaluation_validity=s_ev,
            invalid_reason=s_inv,
            matched_signature=structured_match.get("matched_rule"),
            evidence_codes=["configured_origin_rule", "origin_rule_structured"],
            model_invoked=s_mi,
            post_processed=s_pp,
            block_reason=structured_match.get("reason") if mark == "blocked" else None,
            post_reason=structured_match.get("reason") if mark == "post_processed" else None,
            provenance_source="origin_rule",
        )

    # ---- Level 3: Heuristic checks ----
    if not envelope.transport_ok:
        return _build_evaluation(
            envelope,
            response_origin=(
                "adapter_error" if envelope.target_type in _ADAPTER_TARGET_TYPES else "transport_error"
            ),
            origin_confidence="high",
            evaluation_validity="not_evaluable",
            invalid_reason=(
                "adapter_error" if envelope.target_type in _ADAPTER_TARGET_TYPES else "transport_error"
            ),
            evidence_codes=["transport_failure"],
            model_invoked=False,
            post_processed=False,
            provenance_source="heuristic",
        )

    if envelope.http_status is not None and not (200 <= int(envelope.http_status) < 300):
        return _build_evaluation(
            envelope,
            response_origin=(
                "adapter_error" if envelope.target_type in _ADAPTER_TARGET_TYPES else "transport_error"
            ),
            origin_confidence="high",
            evaluation_validity="not_evaluable",
            invalid_reason="http_error",
            evidence_codes=["http_non_2xx"],
            model_invoked=False,
            post_processed=False,
            provenance_source="heuristic",
        )

    if response_text == "" and response_error == "":
        return _build_evaluation(
            envelope,
            response_origin="unknown",
            origin_confidence="medium",
            evaluation_validity="not_evaluable",
            invalid_reason="empty_response",
            evidence_codes=["empty_response"],
            provenance_source="heuristic",
        )

    if _looks_like_html_error_page(response_text, envelope.content_type):
        return _build_evaluation(
            envelope,
            response_origin="gateway_error",
            origin_confidence="high",
            evaluation_validity="not_evaluable",
            invalid_reason="html_error",
            evidence_codes=["html_error_page"],
            model_invoked=False,
            post_processed=False,
            provenance_source="heuristic",
        )

    if _contains_transport_error(combined_text):
        return _build_evaluation(
            envelope,
            response_origin="transport_error",
            origin_confidence="high",
            evaluation_validity="not_evaluable",
            invalid_reason="transport_error",
            evidence_codes=["transport_error_marker"],
            model_invoked=False,
            post_processed=False,
            provenance_source="heuristic",
        )

    if _looks_like_error_prefix(response_error):
        invalid_reason = "adapter_error" if envelope.target_type in _ADAPTER_TARGET_TYPES else "execution_error"
        if "extract" in _lowered(response_error):
            invalid_reason = "extract_error"
        return _build_evaluation(
            envelope,
            response_origin=(
                "adapter_error" if envelope.target_type in _ADAPTER_TARGET_TYPES else "transport_error"
            ),
            origin_confidence="high",
            evaluation_validity="not_evaluable",
            invalid_reason=invalid_reason,
            evidence_codes=["error_prefix"],
            model_invoked=False,
            post_processed=False,
            provenance_source="heuristic",
        )

    if _looks_like_error_prefix(response_text):
        return _build_evaluation(
            envelope,
            response_origin=(
                "adapter_error" if envelope.target_type in _ADAPTER_TARGET_TYPES else "transport_error"
            ),
            origin_confidence="high",
            evaluation_validity="not_evaluable",
            invalid_reason="execution_error",
            evidence_codes=["error_prefix"],
            model_invoked=False,
            post_processed=False,
            provenance_source="heuristic",
        )

    # ---- Level 4: Default based on target_type ----
    default_mi: bool | None = True if envelope.target_type in _DIRECT_MODEL_TARGET_TYPES else None
    default_pp: bool | None = False if default_mi is True else None
    default_prov_source: ProvenanceSource = "target_type_default" if default_mi is True else "none"
    return _build_evaluation(
        envelope,
        response_origin=default_origin,
        origin_confidence=default_confidence,
        evaluation_validity="evaluable",
        model_invoked=default_mi,
        post_processed=default_pp,
        provenance_source=default_prov_source,
    )


def response_evaluation_payload(value: ResponseEvaluation | Mapping[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, ResponseEvaluation):
        return value.model_dump()
    if isinstance(value, Mapping):
        return dict(value)
    return None


def extract_response_evaluation(container: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(container, Mapping):
        return None

    direct = response_evaluation_payload(container.get("response_evaluation"))
    if direct is not None:
        return direct

    if "evaluation_validity" in container:
        return response_evaluation_payload(container)

    analysis_raw = container.get("analysis_raw")
    if isinstance(analysis_raw, Mapping):
        nested = response_evaluation_payload(analysis_raw.get("response_evaluation"))
        if nested is not None:
            return nested

    case_summary = container.get("case_summary")
    if isinstance(case_summary, Mapping):
        nested = response_evaluation_payload(case_summary.get("response_evaluation"))
        if nested is not None:
            return nested

    return None


def is_not_evaluable_response(container: Mapping[str, Any] | None) -> bool:
    response_evaluation = extract_response_evaluation(container)
    if response_evaluation is None:
        return False
    return response_evaluation.get("evaluation_validity") == "not_evaluable"


def describe_not_evaluable_reason(
    response_evaluation: ResponseEvaluation | Mapping[str, Any] | None,
) -> str:
    payload = response_evaluation_payload(response_evaluation) or {}
    invalid_reason = _normalized_string(payload.get("invalid_reason"))
    matched_signature = _normalized_string(payload.get("matched_signature"))
    base = _NOT_EVALUABLE_REASON_MESSAGES.get(
        invalid_reason,
        "The response could not be treated as stable model output.",
    )
    if matched_signature:
        return f"{base} Matched signature: {matched_signature}."
    return base


def build_not_evaluable_analysis(
    response_evaluation: ResponseEvaluation | Mapping[str, Any] | None,
) -> AnalysisResult:
    reason_text = describe_not_evaluable_reason(response_evaluation)
    return AnalysisResult(
        attack_successful=False,
        confidence=1.0,
        risk_level="none",
        evidence="Response was classified as non-evaluable before semantic judging.",
        explanation=reason_text,
        execution_mode="UNCERTAIN",
        blackbox_outcome="NO_INJECTION_SUCCESS",
        attack_goal_score=0.0,
        utility_score=None,
        utility_explanation="No stable utility score was assigned because the response was not treated as model output.",
    )


def infer_not_evaluable_response_evaluation(
    *,
    response_text: str | None = None,
    response_error: str | None = None,
    target_type: str = "unknown",
    origin_rules: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    evaluation = screen_response_origin(
        TargetResponseEnvelope(
            response_text=response_text,
            response_error=response_error,
            response_status="failed" if response_error else "completed",
            target_type=target_type,
            transport_ok=not bool(response_error and _looks_like_error_prefix(response_error)),
        ),
        origin_rules=origin_rules,
    )
    if evaluation.evaluation_validity != "not_evaluable":
        return None
    return evaluation.model_dump()
