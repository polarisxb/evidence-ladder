from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.schemas.adapter import (
    AdapterProbeTestResponse,
    ProbeAssertionResult,
    ProbeEvidence,
    ProbeStepResult,
)


_BUSINESS_STATE: set[tuple[str, str, str]] = set()


def read_builtin_hidden_state(
    *,
    scan_id: str,
    case_id: str,
    state_key: str,
) -> bool:
    return (scan_id, case_id, state_key) in _BUSINESS_STATE


def commit_builtin_hidden_state(
    *,
    scan_id: str,
    case_id: str,
    state_key: str,
) -> None:
    _BUSINESS_STATE.add((scan_id, case_id, state_key))


def execute_builtin_target(
    payload: str,
    target_config: Mapping[str, Any],
) -> str | None:
    probe_config = target_config.get("builtin_probe_config")
    if not isinstance(probe_config, Mapping) or not probe_config.get("enabled", True):
        return None

    state_key = str(probe_config.get("state_key") or "").strip()
    action_trigger = str(probe_config.get("action_trigger") or "").strip()
    scan_id = str(target_config.get("__scan_id") or "")
    case_id = str(target_config.get("__case_id") or "")
    if state_key and action_trigger and action_trigger in payload:
        commit_builtin_hidden_state(
            scan_id=scan_id,
            case_id=case_id,
            state_key=state_key,
        )

    return str(probe_config.get("response_text") or "Action completed.")


def execute_builtin_probe(
    adapter_payload: Mapping[str, Any],
    *,
    scan_id: str | None,
    case_id: str | None,
) -> AdapterProbeTestResponse:
    probe_config = adapter_payload.get("probe_config")
    if not isinstance(probe_config, Mapping) or not probe_config.get("enabled", True):
        return AdapterProbeTestResponse(
            success=False,
            verified=False,
            failure_reason="Built-in probe is unavailable",
            failure_type="assertion_failed",
        )

    state_key = str(probe_config.get("state_key") or "").strip()
    verified = read_builtin_hidden_state(
        scan_id=str(scan_id or ""),
        case_id=str(case_id or ""),
        state_key=state_key,
    )
    failure_reason = None if verified else f"Built-in state {state_key!r} was not observed"
    return AdapterProbeTestResponse(
        success=verified,
        verified=verified,
        assertion_results=[
            ProbeAssertionResult(
                type="builtin_state_exists",
                step="builtin_business_state",
                ok=verified,
                actual=verified,
                expected=True,
                failure_reason=failure_reason,
                evidence={"state_key": state_key},
            )
        ],
        evidence=[
            ProbeEvidence(
                step="builtin_business_state",
                kind="business_state",
                value={"state_key": state_key, "observed": verified},
            )
        ],
        failure_reason=failure_reason,
        failure_type=None if verified else "assertion_failed",
        step_results=[
            ProbeStepResult(
                name="builtin_business_state",
                ok=verified,
                failure_type=None if verified else "assertion_failed",
                failure_reason=failure_reason,
                captures={"state_key": state_key, "observed": verified},
                response_preview=f"{state_key}={verified}",
            )
        ],
    )
