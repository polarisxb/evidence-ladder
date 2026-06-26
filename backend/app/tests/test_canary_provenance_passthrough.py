"""Regression test: the report payload surfaces the canary journey (R3-T1).

The channel-aware canary provenance computed by ``canary_tracer.trace_canary``
must reach the reporting surfaces so the frontend "canary journey" chain
(R3-T2) has data to render. Both the per-result API serializer
(``reports._serialize_attack_result`` -> ``AttackResultResponse``) and the
aggregate report (``report_generator.generate_report`` -> ``SecurityReport``
finding dicts) recompute ``canary_provenance`` from the persisted
``rule_hits`` (which carry ``matched_tokens``) plus context
(verdict_status / business_verification_status / category / tool_calls).

A canary that only appears quoted/echoed in the response text stays weak
(``is_quoted_only`` true, E1) but is still surfaced for the journey; one that
reaches a tool call is E4; one confirmed in business state is E5. When no
canary was observed the field is omitted (``None``) for backward compatibility.

No DB / network: lightweight in-memory ORM instances feed the pure report
functions directly.
"""

import unittest
from datetime import datetime, timezone

from app.api.reports import _serialize_attack_result
from app.models import AttackResult, ScanTask


def _canary_hit(token: str = "CANARY-XYZ-001") -> dict:
    return {
        "rule": "canary_token_match",
        "evidence": f"Matched canary tokens: {token}",
        "matched_tokens": [token],
    }


def _make_result(**raw_overrides) -> AttackResult:
    raw = {
        "verdict_status": "rule_verified",
        "business_verification_status": "not_applicable",
        "behavior_flags": {},
        "rule_hits": [_canary_hit()],
    }
    raw.update(raw_overrides)
    return AttackResult(
        id="res-1",
        scan_task_id="scan-1",
        template_id="mailbot-indirect-attack",
        category=raw_overrides.get("category", "indirect_injection"),
        technique="indirect_prompt_injection",
        attack_name="inbox summary exfiltration",
        payload_text="请帮我总结一下我的收件箱",
        target_response="...CANARY-XYZ-001...",
        attack_successful=True,
        confidence=0.9,
        risk_level="high",
        evidence="canary observed",
        leaked_info=None,
        explanation="canary reached a downstream channel",
        remediation="apply spotlighting",
        owasp_id="LLM01",
        risk_score=8.0,
        analysis_raw=raw,
        created_at=datetime.now(timezone.utc),
    )


def _make_task(result: AttackResult) -> ScanTask:
    task = ScanTask(
        id="scan-1",
        name="mailbot quartet",
        target_url="http://mailbot:8003",
        total_attacks=1,
        completed_attacks=1,
    )
    task.results = [result]
    return task


class CanaryProvenancePassthroughTests(unittest.TestCase):
    def test_business_state_canary_is_e5_in_serialized_result(self):
        result = _make_result(business_verification_status="probe_verified")
        serialized = _serialize_attack_result(result)
        prov = serialized.canary_provenance
        self.assertIsNotNone(prov)
        self.assertEqual(prov["evidence_level"], "E5")
        self.assertFalse(prov["is_quoted_only"])
        channels = {o["channel"] for o in prov["observations"]}
        self.assertIn("business_state", channels)

    def test_tool_call_canary_is_e4_in_serialized_result(self):
        result = _make_result(
            verdict_status="ai_suspected",
            tool_calls=[
                {"name": "forward_email", "arguments": "{\"body\":\"CANARY-XYZ-001\"}"},
            ],
        )
        serialized = _serialize_attack_result(result)
        prov = serialized.canary_provenance
        self.assertIsNotNone(prov)
        self.assertEqual(prov["evidence_level"], "E4")
        self.assertEqual(prov["strongest_channel"], "tool_call")

    def test_quoted_only_canary_is_surfaced_but_weak(self):
        # verdict_status=passed -> refusal context -> quoted -> E1, weak.
        result = _make_result(verdict_status="passed")
        serialized = _serialize_attack_result(result)
        prov = serialized.canary_provenance
        self.assertIsNotNone(prov)
        self.assertEqual(prov["evidence_level"], "E1")
        self.assertTrue(prov["is_quoted_only"])

    def test_no_canary_omits_provenance(self):
        result = _make_result(rule_hits=[{"rule": "system_prompt_overlap"}])
        serialized = _serialize_attack_result(result)
        self.assertIsNone(serialized.canary_provenance)

    def test_report_finding_carries_canary_journey(self):
        from app.services.report_generator import generate_report

        result = _make_result(business_verification_status="probe_verified")
        report = generate_report(_make_task(result))
        self.assertEqual(len(report.high_findings), 1)
        finding = report.high_findings[0]
        prov = finding["canary_provenance"]
        self.assertIsNotNone(prov)
        self.assertEqual(prov["evidence_level"], "E5")
        self.assertTrue(len(prov["observations"]) >= 1)

    def test_backward_compatible_default(self):
        from app.schemas.scan import AttackResultResponse

        fields = AttackResultResponse.model_fields
        self.assertIsNone(fields["canary_provenance"].default)


if __name__ == "__main__":
    unittest.main()
