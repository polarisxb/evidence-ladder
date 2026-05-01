"""Tests for the Phase-4b in-case retry logic in
``case_executor.execute_case_variant``.

The contract:
- Primary attack variant + transient non-evaluable first response
  → target is called exactly twice, second result wins if evaluable.
- Primary attack variant + non-transient not_evaluable first response
  (``known_fallback`` / ``configured_origin_rule`` / …)
  → target is called exactly once, no retry.
- Control variant (quartet) + transient non-evaluable
  → target is called exactly once; retries are attack-only.
- Retry itself raises → first response wins.
- First response already evaluable → no retry.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services import case_executor


class _FakeTask:
    """Minimal stand-in for a ScanTask. Only the attributes
    execute_case_variant / build_send_target_config read are populated."""

    def __init__(self, target_config: dict | None = None) -> None:
        self.id = "fake-scan"
        self.target_type = "builtin_vulnerable"
        self.target_url = "http://mock-target"
        self.target_config = target_config
        self.runtime_vars: dict = {}
        self.model_provider = None
        self.model_name = None
        self.model_api_key = None
        self.target_model_config = None


def _attack_variant(text: str = "ignore prior") -> dict:
    return {
        "variant_type": "attack",
        "request_text": text,
    }


def _control_variant(text: str = "quoted") -> dict:
    return {
        "variant_type": "quoted",
        "request_text": text,
    }


class InCaseRetryTests(unittest.IsolatedAsyncioTestCase):
    async def _run(self, responses: list[str], variant: dict, task: _FakeTask | None = None):
        """Run execute_case_variant with a scripted sequence of target
        responses. Returns (result_dict, number_of_target_calls)."""
        call_count = {"n": 0}

        async def _fake_send_to_target(
            payload, target_url, target_type, target_config, conversation_history=None
        ):
            i = call_count["n"]
            call_count["n"] = i + 1
            # If more calls than scripted, repeat last.
            return responses[min(i, len(responses) - 1)]

        t = task or _FakeTask()
        with patch.object(case_executor, "send_to_target", _fake_send_to_target):
            result = await case_executor.execute_case_variant(
                t, variant, conversation_history=None, case_id="case-x"
            )
        return result, call_count["n"]

    # ------- basic success path (no retry) -------

    async def test_evaluable_first_response_no_retry(self):
        result, calls = await self._run(
            responses=["I refuse to help with that request."],
            variant=_attack_variant(),
        )
        self.assertEqual(calls, 1, "Target should be called exactly once when first reply is evaluable")
        self.assertEqual(
            result["response_evaluation"]["evaluation_validity"], "evaluable"
        )
        self.assertEqual(result["response_text"], "I refuse to help with that request.")

    # ------- retriable first response paths -------

    async def test_empty_first_response_retries_and_second_reply_wins(self):
        result, calls = await self._run(
            responses=["", "I refuse."],
            variant=_attack_variant(),
        )
        self.assertEqual(calls, 2, "Empty first response should trigger exactly one retry")
        self.assertEqual(
            result["response_evaluation"]["evaluation_validity"], "evaluable",
            "Retry recovered a valid response; result must reflect that",
        )
        self.assertEqual(result["response_text"], "I refuse.")

    async def test_error_first_response_retries(self):
        result, calls = await self._run(
            responses=["[ERROR] connect timeout", "Normal answer."],
            variant=_attack_variant(),
        )
        self.assertEqual(calls, 2)
        self.assertEqual(result["response_text"], "Normal answer.")
        self.assertEqual(
            result["response_evaluation"]["evaluation_validity"], "evaluable"
        )

    async def test_both_attempts_empty_keeps_first(self):
        """When the retry also fails, we keep the first result so the
        user sees a consistent failure signature rather than a second
        possibly-different error blob."""
        result, calls = await self._run(
            responses=["", ""],
            variant=_attack_variant(),
        )
        self.assertEqual(calls, 2, "Still retry once even if it fails")
        self.assertEqual(
            result["response_evaluation"]["evaluation_validity"], "not_evaluable"
        )
        self.assertEqual(
            result["response_evaluation"]["invalid_reason"], "empty_response"
        )

    # ------- non-retriable not_evaluable paths -------

    async def test_known_fallback_is_not_retried(self):
        """Target deliberately returning a canned refusal template
        should NOT be retried — retrying would waste API quota for
        exactly the same output."""
        fallback = "I'm experiencing technical difficulties. Please contact our support line."
        result, calls = await self._run(
            responses=[fallback, "second call should never happen"],
            variant=_attack_variant(),
        )
        self.assertEqual(calls, 1, "known_fallback must not trigger retry")
        self.assertEqual(
            result["response_evaluation"]["evaluation_validity"], "not_evaluable"
        )
        self.assertEqual(
            result["response_evaluation"]["invalid_reason"], "known_fallback"
        )

    async def test_configured_origin_rule_is_not_retried(self):
        task = _FakeTask(target_config={
            "origin_rules": {"exact": ["service temporarily warming up."]}
        })
        result, calls = await self._run(
            responses=["service temporarily warming up.", "second call should never happen"],
            variant=_attack_variant(),
            task=task,
        )
        self.assertEqual(calls, 1, "configured_origin_rule must not trigger retry")
        self.assertEqual(
            result["response_evaluation"]["invalid_reason"], "configured_origin_rule"
        )

    # ------- control variant does not retry -------

    async def test_control_variant_empty_is_not_retried(self):
        """Quartet control variants stay un-retried to avoid doubling
        target API cost on every scan."""
        result, calls = await self._run(
            responses=["", "second call should never happen"],
            variant=_control_variant(),
        )
        self.assertEqual(calls, 1, "control variants must never retry")
        self.assertEqual(
            result["response_evaluation"]["evaluation_validity"], "not_evaluable"
        )

    # ------- retry call itself raises -------

    async def test_retry_exception_falls_back_to_first_result(self):
        """If the retry call raises, keep the first attempt's result
        and continue — never propagate the error up to the scan."""
        call_count = {"n": 0}

        async def _send_with_raising_retry(payload, target_url, target_type, target_config, conversation_history=None):
            i = call_count["n"]
            call_count["n"] = i + 1
            if i == 0:
                return ""  # first attempt empty -> triggers retry
            raise RuntimeError("retry boom")

        t = _FakeTask()
        with patch.object(case_executor, "send_to_target", _send_with_raising_retry):
            result = await case_executor.execute_case_variant(
                t, _attack_variant(), conversation_history=None, case_id="case-x"
            )
        self.assertEqual(call_count["n"], 2)
        # First attempt was not_evaluable / empty; since retry raised,
        # we kept the first attempt.
        self.assertEqual(
            result["response_evaluation"]["evaluation_validity"], "not_evaluable"
        )
        self.assertEqual(
            result["response_evaluation"]["invalid_reason"], "empty_response"
        )


if __name__ == "__main__":
    unittest.main()
