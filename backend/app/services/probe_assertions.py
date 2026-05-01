import json
from collections.abc import Mapping
from typing import Any

from app.schemas.adapter import ProbeAssertion, ProbeAssertionResult, ProbeEvidence
from app.services.adapter_extractors import coerce_text_value, extract_json_path_value


def _load_step_json(step: Mapping[str, Any]) -> Any | None:
    response_text = step.get("response_text")
    if not isinstance(response_text, str):
        return None
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        return None


def evaluate_probe_assertions(
    assertions: list[ProbeAssertion],
    *,
    step_results: list[Mapping[str, Any]],
) -> tuple[list[ProbeAssertionResult], list[ProbeEvidence], bool, str | None]:
    step_lookup = {
        str(step.get("name")): step
        for step in step_results
        if isinstance(step.get("name"), str) and step.get("name")
    }
    default_step = str(step_results[-1].get("name")) if step_results else None

    assertion_results: list[ProbeAssertionResult] = []
    evidence: list[ProbeEvidence] = []
    failure_reason: str | None = None

    for assertion in assertions:
        step_name = assertion.step or default_step
        step = step_lookup.get(step_name or "")
        if step is None:
            reason = f"Probe assertion references missing step: {step_name or 'final'}"
            assertion_results.append(
                ProbeAssertionResult(
                    type=assertion.type,
                    step=step_name,
                    ok=False,
                    expected=_expected_value(assertion),
                    failure_reason=reason,
                )
            )
            failure_reason = failure_reason or reason
            continue

        response_text = coerce_text_value(step.get("response_text"))
        response_json = _load_step_json(step)
        status_code = step.get("status_code")
        actual: Any = None
        ok = False
        reason: str | None = None

        if assertion.type == "json_path_exists":
            actual = extract_json_path_value(response_json, assertion.path) if response_json is not None else None
            ok = actual is not None
            if not ok:
                reason = f"JSON path not found: {assertion.path}"
        elif assertion.type == "json_path_not_exists":
            actual = extract_json_path_value(response_json, assertion.path) if response_json is not None else None
            ok = actual is None
            if not ok:
                reason = f"JSON path unexpectedly found: {assertion.path}"
        elif assertion.type == "json_path_equals":
            actual = extract_json_path_value(response_json, assertion.path) if response_json is not None else None
            ok = actual == assertion.expected
            if not ok:
                reason = f"JSON path {assertion.path} did not equal expected value"
        elif assertion.type == "json_path_contains":
            actual = extract_json_path_value(response_json, assertion.path) if response_json is not None else None
            haystack = coerce_text_value(actual) or ""
            needle = assertion.contains or ""
            ok = needle in haystack
            if not ok:
                reason = f"JSON path {assertion.path} did not contain expected text"
        elif assertion.type == "json_path_not_contains":
            actual = extract_json_path_value(response_json, assertion.path) if response_json is not None else None
            haystack = coerce_text_value(actual) or ""
            needle = assertion.contains or ""
            ok = needle not in haystack
            if not ok:
                reason = f"JSON path {assertion.path} unexpectedly contained forbidden text"
        elif assertion.type == "status_code_is":
            actual = status_code
            ok = actual == assertion.status_code
            if not ok:
                reason = f"Status code {actual} did not match expected {assertion.status_code}"
        elif assertion.type == "text_contains":
            actual = response_text
            needle = assertion.contains or ""
            ok = needle in (response_text or "")
            if not ok:
                reason = "Response text did not contain expected text"
        elif assertion.type == "text_not_contains":
            actual = response_text
            needle = assertion.contains or ""
            ok = needle not in (response_text or "")
            if not ok:
                reason = "Response text unexpectedly contained forbidden text"

        result = ProbeAssertionResult(
            type=assertion.type,
            step=step_name,
            ok=ok,
            actual=actual,
            expected=_expected_value(assertion),
            failure_reason=reason,
            evidence={
                "path": assertion.path,
                "status_code": status_code,
            },
        )
        assertion_results.append(result)

        if ok:
            evidence.append(
                ProbeEvidence(
                    step=step_name or "final",
                    kind=assertion.type,
                    value=actual if actual is not None else _expected_value(assertion),
                )
            )
        else:
            failure_reason = failure_reason or reason

    verified = all(result.ok for result in assertion_results) if assertion_results else False
    return assertion_results, evidence, verified, failure_reason


def _expected_value(assertion: ProbeAssertion) -> Any:
    if assertion.type == "status_code_is":
        return assertion.status_code
    if assertion.type in {"json_path_contains", "json_path_not_contains", "text_contains", "text_not_contains"}:
        return assertion.contains
    return assertion.expected
