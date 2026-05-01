"""Regression tests for the per-case baseline probe.

Covers:
* ``_envelope_is_healthy`` classification for the three envelope shapes
  the probe can produce (2xx, non-2xx, direct-target with no status).
* TTL caching: a second call within the window returns the cached dict
  and does NOT re-invoke the target.
* Trigger policy on ``execute_case_variant``:
  - B-class ``invalid_reason`` (e.g. ``transport_error``) attaches the
    probe result to ``response_evaluation.baseline_probe``.
  - A-class ``invalid_reason`` (e.g. ``known_fallback``) leaves the
    evaluation untouched.
  - ``empty_response`` + HTTP 2xx also leaves it untouched (target is
    clearly alive, probe would be wasted).
  - Control variants (``variant_type != "attack"``) never trigger the
    probe even if their evaluation is not_evaluable.
"""
from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services import health_probe
from app.services.case_executor import execute_case_variant
from app.services.response_screening import TargetResponseEnvelope


def _make_task(target_type: str = "custom") -> SimpleNamespace:
    return SimpleNamespace(
        id="task-probe-test",
        target_type=target_type,
        target_url="http://localhost:9001/chat",
        target_config={},
        runtime_vars={},
        advanced_config={},
    )


def _healthy_envelope() -> TargetResponseEnvelope:
    return TargetResponseEnvelope(
        response_text="hi",
        response_error=None,
        response_status="completed",
        session_id=None,
        target_type="custom",
        transport_ok=True,
        http_status=200,
        content_type="text/plain",
        transport_meta={"status_code": 200, "content_type": "text/plain", "transport_ok": True},
        response_origin="unknown",
        origin_confidence="low",
        evaluation_validity="evaluable",
    )


def _500_envelope() -> TargetResponseEnvelope:
    return TargetResponseEnvelope(
        response_text=None,
        response_error="Internal Server Error",
        response_status="failed",
        session_id=None,
        target_type="custom",
        transport_ok=False,
        http_status=500,
        content_type="text/plain",
        transport_meta={"status_code": 500, "transport_ok": False},
        response_origin="transport_error",
        origin_confidence="high",
        evaluation_validity="not_evaluable",
    )


class BaselineProbeEnvelopeClassificationTests(unittest.TestCase):
    def test_2xx_is_healthy(self) -> None:
        self.assertTrue(health_probe._envelope_is_healthy(_healthy_envelope()))

    def test_5xx_is_unhealthy(self) -> None:
        self.assertFalse(health_probe._envelope_is_healthy(_500_envelope()))

    def test_direct_target_with_text_no_status_is_healthy(self) -> None:
        # builtin / openai_compatible transport doesn't set http_status,
        # but a non-empty response_text means the pipe is working.
        env = TargetResponseEnvelope(
            response_text="anything",
            response_error=None,
            response_status="completed",
            session_id=None,
            target_type="openai_compatible",
            transport_ok=True,
            http_status=None,
            content_type=None,
            transport_meta={},
            response_origin="model",
            origin_confidence="high",
            evaluation_validity="evaluable",
        )
        self.assertTrue(health_probe._envelope_is_healthy(env))

    def test_direct_target_with_empty_text_and_no_status_is_unhealthy(self) -> None:
        env = TargetResponseEnvelope(
            response_text="",
            response_error=None,
            response_status="completed",
            session_id=None,
            target_type="openai_compatible",
            transport_ok=True,
            http_status=None,
            content_type=None,
            transport_meta={},
            response_origin="model",
            origin_confidence="high",
            evaluation_validity="evaluable",
        )
        self.assertFalse(health_probe._envelope_is_healthy(env))


class BaselineProbeCachingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        health_probe._reset_cache_for_tests()

    async def test_cache_hit_does_not_re_invoke_target(self) -> None:
        task = _make_task()
        mock = AsyncMock(return_value=_healthy_envelope())
        with patch.object(health_probe, "invoke_target_with_envelope", mock):
            first = await health_probe.get_cached_baseline_probe(task)
            second = await health_probe.get_cached_baseline_probe(task)

        self.assertEqual(first["status"], "ok")
        self.assertEqual(second["status"], "ok")
        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])
        self.assertEqual(mock.await_count, 1)

    async def test_cache_miss_after_ttl_expiry(self) -> None:
        task = _make_task()
        mock = AsyncMock(return_value=_healthy_envelope())
        with patch.object(health_probe, "invoke_target_with_envelope", mock):
            first = await health_probe.get_cached_baseline_probe(task, now=100.0)
            # Advance the injected clock past ttl_s = 30 (default) relative
            # to the first call's cache expiry (100 + 30 = 130).
            third = await health_probe.get_cached_baseline_probe(task, now=200.0)

        self.assertFalse(first["cached"])
        self.assertFalse(third["cached"])
        self.assertEqual(mock.await_count, 2)

    async def test_probe_timeout_is_captured_as_failed(self) -> None:
        task = _make_task()

        async def _slow(*args, **kwargs):
            await asyncio.sleep(10)
            return _healthy_envelope()

        with patch.object(health_probe, "invoke_target_with_envelope", AsyncMock(side_effect=_slow)):
            # Patch the timeout constant so the test doesn't actually block 5s.
            with patch.object(health_probe, "BASELINE_PROBE_TIMEOUT_S", 0.05):
                result = await health_probe.get_cached_baseline_probe(task)

        self.assertEqual(result["status"], "failed")
        self.assertIn("timeout", (result["reason"] or ""))


class _DummyAnalyzeResponse:
    """Stand-in for ai_analyzer.analyze_response used by the adaptive path."""

    def __init__(self) -> None:
        self.attack_successful = False
        self.confidence = 0.9
        self.risk_level = "low"
        self.evidence = "test"
        self.leaked_info = None
        self.explanation = "test"
        self.remediation = "test"
        self.behavior_flags = None
        self.utility_score = None
        self.attack_goal_score = None
        self.execution_mode = None
        self.blackbox_outcome = None


class CaseExecutorBaselineProbeTriggerTests(unittest.IsolatedAsyncioTestCase):
    """Proves the ``_maybe_attach_baseline_probe`` trigger logic is wired
    into ``execute_case_variant`` for both the fast-return and slow paths."""

    def setUp(self) -> None:
        health_probe._reset_cache_for_tests()

    async def test_transport_error_primary_attack_triggers_probe(self) -> None:
        """Fast-return path: a pre-filled primary ``attack`` variant whose
        response_text is an ``[ERROR]`` marker triggers the probe.
        """
        task = _make_task(target_type="custom")
        case_variant = {
            "variant_type": "attack",
            "position": 0,
            "request_text": "hi",
            "response_text": "[ERROR] Connection refused",
            "response_error": "Connection refused",
            "response_status": "failed",
            "is_primary": True,
            "transport_meta": {"status_code": 500, "transport_ok": False},
        }
        probe_mock = AsyncMock(return_value=_healthy_envelope())
        with patch.object(health_probe, "invoke_target_with_envelope", probe_mock):
            result = await execute_case_variant(task, case_variant, case_id="c-1")

        evaluation = result["response_evaluation"]
        self.assertEqual(evaluation["evaluation_validity"], "not_evaluable")
        self.assertIsNotNone(evaluation.get("baseline_probe"))
        self.assertEqual(evaluation["baseline_probe"]["status"], "ok")
        # One (and only one) probe call happened.
        self.assertEqual(probe_mock.await_count, 1)

    async def test_known_fallback_does_not_trigger_probe(self) -> None:
        """A-class fallback (target returned our known fallback template):
        probe must NOT fire — target is evidently alive and further probing
        just burns API quota.
        """
        task = _make_task(target_type="custom")
        case_variant = {
            "variant_type": "attack",
            "position": 0,
            "request_text": "hi",
            # Match KNOWN_FALLBACK_SIGNATURES exactly (lowercased comparison):
            "response_text": "I'm experiencing technical difficulties. Please contact our support line.",
            "response_error": None,
            "response_status": "completed",
            "is_primary": True,
            "transport_meta": {"status_code": 200, "content_type": "text/plain", "transport_ok": True},
        }
        probe_mock = AsyncMock(return_value=_healthy_envelope())
        with patch.object(health_probe, "invoke_target_with_envelope", probe_mock):
            result = await execute_case_variant(task, case_variant, case_id="c-2")

        evaluation = result["response_evaluation"]
        self.assertEqual(evaluation["evaluation_validity"], "not_evaluable")
        self.assertEqual(evaluation["invalid_reason"], "known_fallback")
        self.assertIsNone(evaluation.get("baseline_probe"))
        self.assertEqual(probe_mock.await_count, 0)

    async def test_empty_response_with_2xx_does_not_trigger_probe(self) -> None:
        """``empty_response`` + HTTP 2xx means the target is clearly alive
        (reply was just empty) — no probe needed."""
        task = _make_task(target_type="custom")
        case_variant = {
            "variant_type": "attack",
            "position": 0,
            "request_text": "hi",
            "response_text": "",
            "response_error": None,
            "response_status": "completed",
            "is_primary": True,
            "transport_meta": {"status_code": 200, "content_type": "text/plain", "transport_ok": True},
        }
        probe_mock = AsyncMock(return_value=_healthy_envelope())
        with patch.object(health_probe, "invoke_target_with_envelope", probe_mock):
            result = await execute_case_variant(task, case_variant, case_id="c-3")

        evaluation = result["response_evaluation"]
        self.assertEqual(evaluation["evaluation_validity"], "not_evaluable")
        self.assertEqual(evaluation["invalid_reason"], "empty_response")
        self.assertIsNone(evaluation.get("baseline_probe"))
        self.assertEqual(probe_mock.await_count, 0)

    async def test_control_variant_does_not_trigger_probe(self) -> None:
        """Even with a transport failure, a non-attack variant must not
        probe — control variants multiply probes without adding signal."""
        task = _make_task(target_type="custom")
        case_variant = {
            "variant_type": "clean",
            "position": 1,
            "request_text": "hi",
            "response_text": "[ERROR] timeout",
            "response_error": "timeout",
            "response_status": "failed",
            "is_primary": False,
            "transport_meta": {"status_code": None, "transport_ok": False},
        }
        probe_mock = AsyncMock(return_value=_healthy_envelope())
        with patch.object(health_probe, "invoke_target_with_envelope", probe_mock):
            result = await execute_case_variant(task, case_variant, case_id="c-4")

        evaluation = result["response_evaluation"]
        self.assertEqual(evaluation["evaluation_validity"], "not_evaluable")
        self.assertIsNone(evaluation.get("baseline_probe"))
        self.assertEqual(probe_mock.await_count, 0)


if __name__ == "__main__":
    unittest.main()
