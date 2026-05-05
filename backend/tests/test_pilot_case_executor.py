from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.schemas.quartet import QuartetPrompts, QuartetVariantSet
from app.schemas.report import AnalysisResult
from app.services import case_executor

pytestmark = pytest.mark.anyio


def _suite_case() -> QuartetPrompts:
    return QuartetPrompts(
        case_id="TPL-001:0",
        category="prompt_injection",
        template_id="TPL-001",
        template_name="Pilot Template",
        owasp_id="LLM01",
        payload_language="en",
        payload_variant="seed",
        variants=QuartetVariantSet(
            attack="attack prompt from suite",
            clean="clean prompt from suite",
            quoted_attack="quoted prompt from suite",
            benign_distractor="benign prompt from suite",
        ),
    )


def _task() -> SimpleNamespace:
    return SimpleNamespace(
        id="scan-1",
        target_url="builtin",
        target_type="builtin_vulnerable",
        target_config={"vulnerable_level": 2},
        runtime_vars={},
        advanced_config={"skip_confirmation": True},
    )


async def test_prepare_explicit_case_attempt_uses_suite_prompts_in_stable_order(
    monkeypatch,
) -> None:
    calls: list[tuple[str, str, int, str]] = []

    async def fake_execute_case_variant(
        task,
        case_variant,
        *,
        conversation_history=None,
        case_id: str,
    ):
        calls.append(
            (
                case_id,
                str(case_variant["variant_type"]),
                int(case_variant["position"]),
                str(case_variant["request_text"]),
            )
        )
        return {
            **case_variant,
            "response_text": f"response::{case_variant['variant_type']}",
            "response_error": None,
            "response_status": "completed",
            "latency_ms": 1.0,
            "analysis_raw": {
                "response_evaluation": {"evaluation_validity": "evaluable"},
            },
            "response_evaluation": {"evaluation_validity": "evaluable"},
        }

    async def fake_analyze_case_variants(
        task,
        template,
        case_variants,
        *,
        attack_type: str | None = None,
        extra_context: str = "",
        skip_confirmation: bool = False,
    ):
        analysis = AnalysisResult(
            attack_successful=True,
            confidence=0.91,
            risk_level="high",
            evidence="mock evidence",
            leaked_info=None,
            explanation="mock explanation",
            remediation="mock remediation",
        )
        return {
            "case_variants": case_variants,
            "payload_text": case_variants[0]["request_text"],
            "target_response": case_variants[0]["response_text"],
            "analysis": analysis,
            "risk_score": 7.0,
            "verdict": {
                "verdict_status": "rule_verified",
                "verdict_reason": "mock verdict",
                "rule_hits": [{"rule": "mock_rule", "evidence": "mock_evidence"}],
            },
            "control_results": [
                {
                    "variant": str(variant["variant_type"]),
                    "prompt": str(variant["request_text"]),
                    "response": str(variant["response_text"]),
                }
                for variant in case_variants
                if variant["variant_type"] != "attack"
            ],
            "control_summary": {
                "control_assessment": "attack_delta_supported",
                "control_summary": "mock control summary",
            },
            "response_evaluation": {"evaluation_validity": "evaluable"},
            "case_summary": {
                "protocol_version": "quartet_v1",
                "quartet_present": True,
                "variant_count": 4,
                "primary_attack_successful": True,
                "case_final_outcome": "rule_verified_finding",
                "control_assessment": "attack_delta_supported",
                "control_summary": "mock control summary",
                "verdict_status": "rule_verified",
                "verdict_reason": "mock verdict",
                "response_evaluation": {"evaluation_validity": "evaluable"},
            },
        }

    async def fake_apply_business_verification(task, case_attempt, ws_clients=None):
        return case_attempt

    monkeypatch.setattr(case_executor, "execute_case_variant", fake_execute_case_variant)
    monkeypatch.setattr(case_executor, "analyze_case_variants", fake_analyze_case_variants)
    monkeypatch.setattr(case_executor, "apply_business_verification", fake_apply_business_verification)

    template = {
        "id": "TPL-001",
        "name": "Pilot Template",
        "category": "prompt_injection",
        "category_name": "prompt_injection",
        "owasp_id": "LLM01",
        "technique": "pilot_suite",
    }

    result = await case_executor.prepare_explicit_case_attempt(
        _task(),
        template,
        _suite_case(),
    )

    assert result["case_id"] == "TPL-001:0"
    assert result["payload_text"] == "attack prompt from suite"
    assert [variant["variant_type"] for variant in result["case_variants"]] == [
        "attack",
        "clean",
        "quoted_attack",
        "benign_distractor",
    ]
    assert calls == [
        ("TPL-001:0", "attack", 0, "attack prompt from suite"),
        ("TPL-001:0", "clean", 1, "clean prompt from suite"),
        ("TPL-001:0", "quoted_attack", 2, "quoted prompt from suite"),
        ("TPL-001:0", "benign_distractor", 3, "benign prompt from suite"),
    ]
