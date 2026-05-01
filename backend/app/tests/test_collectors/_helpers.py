"""Shared test helpers for Phase 3 collector tests.

Centralised so each collector test file does not duplicate the
``AnalysisResult`` boilerplate (which would silently drift if Pydantic
field requirements change).
"""

from __future__ import annotations

from typing import Any

from app.schemas.report import AnalysisResult, BehaviorFlags
from app.services.collectors.base import CollectorContext


def make_analysis(
    *,
    attack_successful: bool = False,
    confidence: float = 0.0,
    blackbox_outcome: str | None = None,
    behavior_flags: BehaviorFlags | None = None,
    leaked_info: str | None = None,
    risk_level: str = "none",
) -> AnalysisResult:
    fields: dict[str, Any] = {
        "attack_successful": attack_successful,
        "confidence": confidence,
        "risk_level": risk_level,
        "evidence": "",
        "explanation": "",
    }
    if blackbox_outcome is not None:
        fields["blackbox_outcome"] = blackbox_outcome
    if behavior_flags is not None:
        fields["behavior_flags"] = behavior_flags
    if leaked_info is not None:
        fields["leaked_info"] = leaked_info
    return AnalysisResult(**fields)


def make_context(
    *,
    attack_payload: str = "",
    target_response: str = "",
    analysis: AnalysisResult | None = None,
    target_config: dict | None = None,
    control_assessment: str | None = None,
    business_verification_status: str | None = None,
    response_evaluation: dict | None = None,
) -> CollectorContext:
    return CollectorContext(
        attack_payload=attack_payload,
        target_response=target_response,
        analysis=analysis or make_analysis(),
        target_config=target_config,
        control_assessment=control_assessment,
        business_verification_status=business_verification_status,
        response_evaluation=response_evaluation,
    )
