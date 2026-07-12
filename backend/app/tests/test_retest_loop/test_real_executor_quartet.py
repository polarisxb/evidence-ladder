# backend/app/tests/test_retest_loop/test_real_executor_quartet.py
import asyncio
import types

from app.services import retest_executor_real as rex
from app.services.retest_executor_real import RealRetestExecutor


def _task():
    return types.SimpleNamespace(
        id="scan1",
        runtime_vars={},
        target_type="adapter",
        target_config={},
        _resolved_adapter_payload={"enabled": True},
    )


def _variants(with_controls=True):
    attack = {
        "variant_type": "attack",
        "is_primary": True,
        "response_text": "ok",
        "response_status": "completed",
        "latency_ms": 100.0,
    }
    if not with_controls:
        return [attack]
    controls = [
        {
            "variant_type": v,
            "response_text": "x",
            "response_status": "completed",
            "latency_ms": 50.0,
        }
        for v in ("clean", "quoted_attack", "benign_distractor")
    ]
    return [attack] + controls


def _patch(monkeypatch, *, variants, control_assessment, case_summary):
    async def _fake_execute(task, template, payload, **kwargs):
        return variants

    async def _fake_analyze(task, template, case_variants, **kwargs):
        return {
            "control_summary": {
                "control_assessment": control_assessment,
                "control_summary": "...",
            },
            "case_summary": case_summary,
            "analysis": types.SimpleNamespace(),
            "verdict": {},
        }

    monkeypatch.setattr(rex, "execute_case_variants", _fake_execute)
    monkeypatch.setattr(rex, "analyze_case_variants", _fake_analyze)


def test_quartet_attack_delta_promotes_to_rule_evidence(monkeypatch):
    _patch(
        monkeypatch,
        variants=_variants(),
        control_assessment="attack_delta_supported",
        case_summary={"tool_observed": False, "tool_calls": []},
    )
    delta = asyncio.run(
        RealRetestExecutor(_task()).run_quartet({"case_id": "c1", "payload_text": "p"})
    )
    assert delta.contradiction is False
    hits = delta.evidence_updates.get("rule_hits")
    assert hits and any(h.get("rule") == "quartet_attack_delta" for h in hits)
    assert delta.extra_queries == 3


def test_quartet_attack_only_tool_promotes_to_tool_observed(monkeypatch):
    _patch(
        monkeypatch,
        variants=_variants(),
        control_assessment="attack_delta_supported",
        case_summary={
            "tool_observed": True,
            "tool_calls": [{"name": "forward_email"}],
            "attack_only_tools": ["forward_email"],
        },
    )
    delta = asyncio.run(
        RealRetestExecutor(_task()).run_quartet({"case_id": "c1", "payload_text": "p"})
    )
    assert delta.contradiction is False
    assert delta.evidence_updates.get("tool_observed") is True
    assert delta.evidence_updates.get("tool_calls") == [{"name": "forward_email"}]


def test_quartet_control_also_succeeds_is_contradiction(monkeypatch):
    _patch(
        monkeypatch,
        variants=_variants(),
        control_assessment="discussion_supported",
        case_summary={"tool_observed": False},
    )
    delta = asyncio.run(
        RealRetestExecutor(_task()).run_quartet({"case_id": "c1", "payload_text": "p"})
    )
    assert delta.contradiction is True
    assert delta.evidence_updates == {}


def test_quartet_controls_inconclusive_is_not_contradiction(monkeypatch):
    _patch(
        monkeypatch,
        variants=_variants(),
        control_assessment="controls_inconclusive",
        case_summary={"tool_observed": False},
    )
    delta = asyncio.run(
        RealRetestExecutor(_task()).run_quartet({"case_id": "c1", "payload_text": "p"})
    )
    assert delta.contradiction is False


def test_quartet_analysis_receives_pinned_judge(monkeypatch):
    received = {}

    async def _fake_execute(task, template, payload, **kwargs):
        return _variants()

    async def _fake_analyze(task, template, case_variants, **kwargs):
        received.update(kwargs)
        return {
            "control_summary": {
                "control_assessment": "attack_delta_supported",
                "control_summary": "...",
            },
            "case_summary": {"tool_observed": False},
            "analysis": types.SimpleNamespace(),
            "verdict": {},
        }

    monkeypatch.setattr(rex, "execute_case_variants", _fake_execute)
    monkeypatch.setattr(rex, "analyze_case_variants", _fake_analyze)

    executor = RealRetestExecutor(
        _task(),
        judge_provider_id="pinned-judge-provider",
        judge_model_version="judge-snapshot-2026-07-01",
    )
    asyncio.run(executor.run_quartet({"case_id": "c1", "payload_text": "p"}))

    assert received["judge_provider_id"] == "pinned-judge-provider"
    assert received["judge_model_version"] == "judge-snapshot-2026-07-01"


def test_quartet_controls_missing_is_noop(monkeypatch):
    _patch(
        monkeypatch,
        variants=_variants(with_controls=False),
        control_assessment="controls_missing",
        case_summary={"tool_observed": False},
    )
    delta = asyncio.run(
        RealRetestExecutor(_task()).run_quartet({"case_id": "c1", "payload_text": "p"})
    )
    assert delta.contradiction is False
    assert delta.evidence_updates == {}
    assert delta.extra_queries == 0
