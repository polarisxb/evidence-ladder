"""Regression tests for the advanced-engine envelope propagation fix.

Context
-------
Before the fix, the 7 advanced engines (TAP, PAIR, IRIS, Crescendo,
FITD, MSJ, ICE) all declared their ``send_fn`` as ``(prompt) -> str``
and called ``_send_to_target_with_result`` which only returned the
flattened text. That quietly dropped ``http_status`` / ``content_type``
/ ``transport_meta`` from every envelope, so a case that actually got
"HTTP 200 with empty body" would land in the DB as ``http_status=None``
and get classified as a generic ``empty_response`` — indistinguishable
from "no HTTP call at all".

Fix
---
``scan_runner`` now:
1. Invokes the target via ``invoke_target_with_envelope`` directly from
   every engine's ``send_fn`` closure.
2. Records the full envelope on each probe attempt via
   ``_record_envelope_attempt``.
3. Recovers the envelope tied to the engine's picked ``resolved_response``
   via ``_resolve_envelope_for_response`` and passes its
   ``transport_meta`` through ``_prepare_case_attempt`` /
   ``execute_case_variants`` / ``build_case_variants`` into the primary
   variant's ``transport_meta`` field.

These tests assert:
* The helpers record and resolve envelopes correctly.
* ``envelope_to_variant_transport_meta`` produces the dict shape
  ``screen_response_origin`` consumes (``status_code`` / ``content_type``
  / ``transport_ok``).
* ``build_case_variants`` writes the transport_meta onto the primary
  variant when given ``attack_transport_meta``.
* End-to-end: an engine that invokes the target, gets HTTP 200 with an
  empty body, feeds that envelope back through
  ``_prepare_case_attempt`` → ``execute_case_variant`` (fast-return path)
  → final ``response_evaluation`` now carries ``http_status=200``
  instead of ``http_status=None``. This is the exact failure mode the
  TAP/FinanceBot scan exhibited ("模型空响应·目标健康" instead of a
  generic "无法评测").
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services import health_probe
from app.services.case_executor import (
    build_case_variants,
    envelope_to_variant_transport_meta,
    execute_case_variant,
)
from app.services.response_screening import TargetResponseEnvelope
from app.services.scan_runner import (
    _record_envelope_attempt,
    _resolve_envelope_for_response,
    _envelope_response_error,
)


def _envelope(
    *,
    response_text: str | None,
    http_status: int | None,
    content_type: str | None = "text/plain;charset=UTF-8",
    transport_ok: bool = True,
    response_error: str | None = None,
) -> TargetResponseEnvelope:
    meta: dict = {}
    if http_status is not None:
        meta["status_code"] = http_status
    if content_type is not None:
        meta["content_type"] = content_type
    meta["transport_ok"] = transport_ok
    return TargetResponseEnvelope(
        response_text=response_text,
        response_error=response_error,
        response_status="failed" if response_error else "completed",
        session_id=None,
        target_type="custom",
        transport_ok=transport_ok,
        http_status=http_status,
        content_type=content_type,
        transport_meta=meta,
        response_origin="unknown",
        origin_confidence="low",
        evaluation_validity="evaluable",
    )


class RecordAndResolveEnvelopeTests(unittest.TestCase):
    def test_record_returns_flattened_text_and_stores_envelope(self) -> None:
        attempts: list[dict] = []
        env = _envelope(response_text="hi there", http_status=200)
        returned = _record_envelope_attempt(attempts, "prompt A", env)
        self.assertEqual(returned, "hi there")
        self.assertEqual(len(attempts), 1)
        self.assertIs(attempts[0]["envelope"], env)

    def test_record_flattens_error_envelope_with_error_prefix(self) -> None:
        """A 5xx envelope with no response_text but with response_error
        should still yield a string that advanced engines can treat as
        the target reply, prefixed with ``[ERROR]`` so downstream
        screening can classify it as a transport failure."""
        attempts: list[dict] = []
        env = _envelope(
            response_text=None,
            http_status=500,
            response_error="Internal Server Error",
            transport_ok=False,
        )
        returned = _record_envelope_attempt(attempts, "prompt B", env)
        self.assertTrue(returned.startswith("[ERROR]"))
        self.assertIn("Internal Server Error", returned)

    def test_resolve_matches_best_response_exactly(self) -> None:
        """When multiple attempts yield the same response text, resolver
        returns the most recent matching envelope — matches the engine's
        ``best_response`` fallback which picks the last good one."""
        attempts: list[dict] = []
        older = _envelope(response_text="same reply", http_status=200)
        newer = _envelope(response_text="same reply", http_status=200, content_type="text/json")
        _record_envelope_attempt(attempts, "p1", older)
        _record_envelope_attempt(attempts, "p2", newer)

        resolved = _resolve_envelope_for_response(attempts, "same reply")
        self.assertIs(resolved, newer)

    def test_resolve_falls_back_to_last_attempt_when_response_is_empty(self) -> None:
        """Empty ``resolved_response`` (e.g. FinanceBot returning empty
        body for every TAP variant) still returns an envelope so we can
        surface its ``http_status`` to the UI."""
        attempts: list[dict] = []
        only = _envelope(response_text="", http_status=200)
        _record_envelope_attempt(attempts, "p1", only)

        resolved = _resolve_envelope_for_response(attempts, "")
        self.assertIs(resolved, only)

    def test_resolve_returns_none_on_empty_attempts(self) -> None:
        self.assertIsNone(_resolve_envelope_for_response([], "anything"))

    def test_envelope_response_error_strips_whitespace_only(self) -> None:
        env = _envelope(response_text="ok", http_status=200, response_error="   ")
        self.assertIsNone(_envelope_response_error(env))


class EnvelopeToTransportMetaTests(unittest.TestCase):
    def test_populates_status_code_content_type_and_transport_ok(self) -> None:
        env = _envelope(response_text="", http_status=200, content_type="application/json")
        meta = envelope_to_variant_transport_meta(env)
        self.assertEqual(meta["status_code"], 200)
        self.assertEqual(meta["content_type"], "application/json")
        self.assertIs(meta["transport_ok"], True)

    def test_none_envelope_yields_empty_dict(self) -> None:
        self.assertEqual(envelope_to_variant_transport_meta(None), {})


class BuildCaseVariantsWritesTransportMetaTests(unittest.TestCase):
    def test_transport_meta_flows_into_primary_variant(self) -> None:
        env = _envelope(response_text="", http_status=200)
        meta = envelope_to_variant_transport_meta(env)
        variants = build_case_variants(
            {"id": "T1", "name": "test", "payloads": [{"text": "seed"}]},
            "final attack payload",
            enable_control_variants=False,
            attack_response="",
            attack_transport_meta=meta,
        )
        primary = variants[0]
        self.assertEqual(primary["transport_meta"]["status_code"], 200)
        self.assertIs(primary["is_primary"], True)
        self.assertEqual(primary["response_text"], "")

    def test_explicit_response_error_marks_variant_failed(self) -> None:
        variants = build_case_variants(
            {"id": "T1", "name": "test", "payloads": [{"text": "seed"}]},
            "payload",
            enable_control_variants=False,
            attack_response=None,
            attack_response_error="Connection refused",
        )
        self.assertEqual(variants[0]["response_status"], "failed")
        self.assertEqual(variants[0]["response_error"], "Connection refused")


class EndToEndTapEmptyBodyRepairTests(unittest.IsolatedAsyncioTestCase):
    """The exact repro from the FinanceBot TAP scan: target answered
    HTTP 200 with an empty body. Pre-fix the primary variant in the DB
    had ``http_status=None``. Post-fix it must carry ``http_status=200``
    so the UI can display "模型空响应·目标健康" (see
    ``notEvaluableDisplayCategory`` in the frontend).
    """

    def setUp(self) -> None:
        health_probe._reset_cache_for_tests()

    async def test_tap_like_empty_body_200_reaches_response_evaluation(self) -> None:
        task = SimpleNamespace(
            id="task-tap-repro",
            target_type="custom",
            target_url="http://localhost:8001/chat",
            target_config={},
            runtime_vars={},
            advanced_config={},
        )

        attempts: list[dict] = []
        for _ in range(3):
            # Simulate 3 rounds of TAP — every round the target answered
            # HTTP 200 with an empty body. Pre-fix the engine would have
            # dropped the 200 on the floor.
            _record_envelope_attempt(
                attempts,
                "tap generated prompt",
                _envelope(response_text="", http_status=200),
            )

        # The engine picks an empty best_response (none of the 3 rounds
        # scored above threshold); the resolver must still pick up a
        # valid envelope from the last attempt.
        attack_envelope = _resolve_envelope_for_response(attempts, "")
        self.assertIsNotNone(attack_envelope)

        transport_meta = envelope_to_variant_transport_meta(attack_envelope)
        primary_only = build_case_variants(
            {"id": "TAP-JB-001", "name": "TAP Test", "payloads": [{"text": "seed"}]},
            "attack payload",
            enable_control_variants=False,
            attack_response="",
            attack_response_error=_envelope_response_error(attack_envelope),
            attack_transport_meta=transport_meta,
        )

        # Prevent the baseline probe from firing (200 + empty body is an
        # A-class "model silent" signal, but this test is about envelope
        # propagation, not probe behaviour).
        with patch.object(
            health_probe,
            "invoke_target_with_envelope",
            AsyncMock(return_value=_envelope(response_text="hi", http_status=200)),
        ):
            executed = await execute_case_variant(task, primary_only[0], case_id="case-x")

        evaluation = executed["response_evaluation"]
        # Pre-fix bug: http_status was None. Post-fix: http_status = 200.
        self.assertEqual(evaluation["http_status"], 200)
        self.assertEqual(evaluation["invalid_reason"], "empty_response")
        self.assertEqual(evaluation["evaluation_validity"], "not_evaluable")
        # The UI's notEvaluableDisplayCategory branches on exactly this
        # combination (empty_response + http 2xx) to surface the
        # "model silent · target healthy" label.


if __name__ == "__main__":
    unittest.main()
