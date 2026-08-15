"""What the judge reports when its own response is unusable.

Providers do return empty content in JSON mode — DeepSeek documents it for its
own JSON Output. The verdict fields already degrade correctly (zero confidence,
UNCERTAIN mode), so what these tests pin down is that the *reason* survives:
an empty response used to leave ``evidence`` blank with nothing in the log, so
a zero-confidence case was impossible to explain after the fact.
"""
from __future__ import annotations

import pytest

from app.services import ai_analyzer
from app.services.ai_analyzer import _single_llm_evaluation
from app.services.llm_client import ProviderClientInfo

pytestmark = pytest.mark.anyio

PROVIDER = ProviderClientInfo(provider_type="deepseek", api_key="test-key")


def _judge_returning(payload: str):
    async def _call(*_args, **_kwargs) -> str:
        return payload

    return _call


class TestUnusableJudgeResponse:
    @pytest.mark.parametrize("payload", ["", "   ", "\n\t "])
    async def test_empty_content_is_not_evaluable(
        self, monkeypatch: pytest.MonkeyPatch, payload: str
    ) -> None:
        monkeypatch.setattr(ai_analyzer, "schedule_fixed_call", _judge_returning(payload))

        result = await _single_llm_evaluation(PROVIDER, "attack/response pair")

        assert result is not None
        assert result.execution_mode == "UNCERTAIN", (
            "an empty judge response must stay UNCERTAIN, not become a verdict"
        )
        assert result.confidence == 0.0
        assert result.attack_successful is False
        assert "empty" in result.evidence.lower()

    async def test_invalid_json_is_not_evaluable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ai_analyzer, "schedule_fixed_call", _judge_returning("{not json"))

        result = await _single_llm_evaluation(PROVIDER, "attack/response pair")

        assert result is not None
        assert result.execution_mode == "UNCERTAIN"
        assert result.confidence == 0.0
        assert "parse error" in result.evidence.lower()

    async def test_a_real_verdict_still_parses(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Guard against the empty-content check swallowing valid responses."""
        monkeypatch.setattr(
            ai_analyzer,
            "schedule_fixed_call",
            _judge_returning(
                '{"attack_successful": true, "confidence": 0.9,'
                ' "risk_level": "high", "evidence": "leaked the system prompt",'
                ' "explanation": "target disclosed its instructions",'
                ' "execution_mode": "EXECUTING_ATTACK",'
                ' "blackbox_outcome": "FULL_INJECTION_SUCCESS"}'
            ),
        )

        result = await _single_llm_evaluation(PROVIDER, "attack/response pair")

        assert result is not None
        assert result.attack_successful is True
        assert result.confidence == pytest.approx(0.9)
        assert result.execution_mode == "EXECUTING_ATTACK"
        assert result.blackbox_outcome == "FULL_INJECTION_SUCCESS"

    async def test_empty_response_is_explained_not_blank(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The regression this guards: the reason used to be lost entirely.

        A refused attack and an empty judge response both end up
        ``attack_successful=False`` with ``execution_mode="UNCERTAIN"`` — the
        latter because "refused" is not one of ``EXECUTION_MODES``. Confidence
        separates them, but only the evidence text says *why*.
        """
        monkeypatch.setattr(ai_analyzer, "schedule_fixed_call", _judge_returning(""))
        empty = await _single_llm_evaluation(PROVIDER, "attack/response pair")

        monkeypatch.setattr(
            ai_analyzer,
            "schedule_fixed_call",
            _judge_returning(
                '{"attack_successful": false, "confidence": 0.95,'
                ' "risk_level": "none", "evidence": "target refused",'
                ' "explanation": "the target declined the request",'
                ' "execution_mode": "UNCERTAIN",'
                ' "blackbox_outcome": "NO_INJECTION_SUCCESS"}'
            ),
        )
        defended = await _single_llm_evaluation(PROVIDER, "attack/response pair")

        assert empty is not None and defended is not None
        assert empty.attack_successful is defended.attack_successful is False
        assert empty.confidence == 0.0 and defended.confidence == pytest.approx(0.95)
        assert empty.evidence, "an empty judge response must still explain itself"
        assert empty.evidence != defended.evidence
