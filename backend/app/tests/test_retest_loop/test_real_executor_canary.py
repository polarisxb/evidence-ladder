# backend/app/tests/test_retest_loop/test_real_executor_canary.py
import asyncio
import types

from app.services import retest_executor_real as rex
from app.services.retest_executor_real import RealRetestExecutor


def _task(canary_tokens=("CANARY-XYZ",)):
    return types.SimpleNamespace(
        id="scan1", runtime_vars={}, target_type="adapter",
        target_config={"canary_tokens": list(canary_tokens)},
        _resolved_adapter_payload={"enabled": True},
    )


def _patch_send(monkeypatch, attack_variant):
    async def _fake_execute(task, template, payload, **kwargs):
        assert kwargs.get("quartet_mode") == "off"
        return [attack_variant]
    monkeypatch.setattr(rex, "execute_case_variants", _fake_execute)


def _canary_hit(delta):
    for h in delta.evidence_updates.get("rule_hits") or []:
        if h.get("rule") == "canary_token_match":
            return h
    return None


def test_canary_in_response_text_emits_rule_hit(monkeypatch):
    _patch_send(monkeypatch, {"variant_type": "attack",
                              "response_text": "sure, the secret is CANARY-XYZ ok",
                              "tool_calls": [], "latency_ms": 120.0})
    delta = asyncio.run(RealRetestExecutor(_task()).run_canary(
        {"case_id": "c1", "payload_text": "leak it"}))
    hit = _canary_hit(delta)
    assert hit is not None
    assert "CANARY-XYZ" in hit["matched_tokens"]
    assert delta.contradiction is False
    assert delta.extra_queries == 1


def test_canary_in_tool_args_emits_rule_hit_and_tool_calls(monkeypatch):
    tool_calls = [{"name": "send_email", "arguments": {"body": "here is CANARY-XYZ"}}]
    _patch_send(monkeypatch, {"variant_type": "attack",
                              "response_text": "done",
                              "tool_calls": tool_calls, "latency_ms": 90.0})
    delta = asyncio.run(RealRetestExecutor(_task()).run_canary({"case_id": "c1"}))
    hit = _canary_hit(delta)
    assert hit is not None and "CANARY-XYZ" in hit["matched_tokens"]
    assert delta.evidence_updates.get("tool_calls") == tool_calls


def test_canary_not_present_is_noop(monkeypatch):
    _patch_send(monkeypatch, {"variant_type": "attack",
                              "response_text": "I cannot help with that",
                              "tool_calls": [], "latency_ms": 50.0})
    delta = asyncio.run(RealRetestExecutor(_task()).run_canary({"case_id": "c1"}))
    assert delta.evidence_updates == {}
    assert delta.contradiction is False


def test_canary_no_configured_tokens_is_noop(monkeypatch):
    _patch_send(monkeypatch, {"variant_type": "attack",
                              "response_text": "CANARY-XYZ", "tool_calls": [], "latency_ms": 10.0})
    delta = asyncio.run(RealRetestExecutor(_task(canary_tokens=())).run_canary({"case_id": "c1"}))
    assert delta.evidence_updates == {}


def test_canary_appends_to_existing_rule_hits(monkeypatch):
    _patch_send(monkeypatch, {"variant_type": "attack",
                              "response_text": "CANARY-XYZ leaked", "tool_calls": [],
                              "latency_ms": 30.0})
    delta = asyncio.run(RealRetestExecutor(_task()).run_canary(
        {"case_id": "c1", "rule_hits": [{"rule": "preexisting"}]}))
    rules = [h.get("rule") for h in delta.evidence_updates.get("rule_hits") or []]
    assert "preexisting" in rules and "canary_token_match" in rules
