import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import openai
import pytest

from app.config import settings
from app.services import ai_analyzer, llm_client, llm_scheduler
from app.services.evidence_arbiter import arbitrate_evidence
from app.services.verdict_engine import classify_verdict

pytestmark = pytest.mark.anyio


@pytest.fixture(params=["openai", "claude"])
def sdk(request, monkeypatch):
    class APITimeoutError(Exception):
        pass

    create = AsyncMock(return_value=SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))],
        content=[SimpleNamespace(text="{}")],
    ))
    constructor = Mock(return_value=SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
        messages=SimpleNamespace(create=create),
    ))
    monkeypatch.setattr(openai, "AsyncOpenAI", constructor)
    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(
        AsyncAnthropic=constructor, NOT_GIVEN=object(), APITimeoutError=APITimeoutError,
    ))
    monkeypatch.setattr(llm_client, "_openai_clients", {})
    monkeypatch.setattr(llm_client, "_anthropic_clients", {})
    monkeypatch.setitem(settings.__dict__, "llm_request_timeout_s", 0.03)
    info = llm_client.ProviderClientInfo(request.param, "synthetic-timeout-key")
    error = (
        openai.APITimeoutError(request=httpx.Request("POST", "https://fixture.example.com"))
        if request.param == "openai" else APITimeoutError("synthetic timeout")
    )
    return info, create, constructor, error


async def test_sdk_receives_explicit_timeout_without_nested_retries(sdk):
    info, create, constructor, _ = sdk
    await llm_client.call_chat(info, "fixture-model", [{"role": "user", "content": "fixture"}])
    assert constructor.call_args.kwargs.get("timeout") == 0.03
    assert constructor.call_args.kwargs.get("max_retries") == 0
    assert create.call_args.kwargs.get("timeout") == 0.03


@pytest.mark.parametrize("failure", ["deadline", "sdk_timeout"])
async def test_judge_timeout_releases_slot_and_records_not_evaluable(sdk, monkeypatch, failure):
    info, create, _, sdk_error = sdk
    cancelled = asyncio.Event()

    async def hang(**kwargs):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    create.side_effect = hang if failure == "deadline" else sdk_error
    controller = llm_scheduler.AIMDController()
    monkeypatch.setattr(llm_scheduler, "_aimd", controller)
    monkeypatch.setattr(llm_scheduler, "_dedup", None)
    monkeypatch.setattr(settings, "judge_cache_enabled", False)
    result = await asyncio.wait_for(
        ai_analyzer._single_llm_evaluation(info, "fixture pair", model="fixture-model"),
        timeout=0.5,
    )
    assert create.await_count == 1
    assert result.confidence == 0.0
    assert result.execution_mode == "UNCERTAIN"
    assert "timed out" in result.evidence.lower()
    assert all(bucket["in_flight"] == 0 for bucket in controller.stats().values())
    if failure == "deadline":
        assert cancelled.is_set()
    verdict = classify_verdict(attack_payload="fixture", target_response="neutral fixture", analysis=result)
    assessment = arbitrate_evidence({**result.model_dump(), **verdict}, abstention_policy="e0")
    assert assessment.evidence_level == "E0"
    assert not assessment.is_evaluable
