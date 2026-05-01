"""Tests for the Collector base abstractions.

The two invariants we lock here:

1. ``CollectorContext`` is frozen — Collectors cannot mutate it.
2. ``safe_collect`` swallows exceptions and never returns ``None``.
"""

import unittest
from dataclasses import FrozenInstanceError

from app.services.collectors.base import (
    Collector,
    CollectorContext,
    safe_collect,
)
from app.services.evidence import Evidence

from ._helpers import make_analysis, make_context


class CollectorContextTests(unittest.TestCase):
    def test_context_is_frozen(self):
        ctx = make_context()
        with self.assertRaises(FrozenInstanceError):
            ctx.target_response = "mutated"  # type: ignore[misc]

    def test_context_default_optional_fields_are_none(self):
        ctx = CollectorContext(
            attack_payload="x",
            target_response="y",
            analysis=make_analysis(),
        )
        self.assertIsNone(ctx.target_config)
        self.assertIsNone(ctx.control_assessment)
        self.assertIsNone(ctx.business_verification_status)
        self.assertIsNone(ctx.response_evaluation)

    def test_context_carries_all_fields(self):
        ctx = make_context(
            attack_payload="atk",
            target_response="resp",
            target_config={"k": "v"},
            control_assessment="discussion_supported",
            business_verification_status="probe_verified",
            response_evaluation={"origin": "model"},
        )
        self.assertEqual(ctx.attack_payload, "atk")
        self.assertEqual(ctx.target_response, "resp")
        self.assertEqual(dict(ctx.target_config or {}), {"k": "v"})
        self.assertEqual(ctx.control_assessment, "discussion_supported")
        self.assertEqual(ctx.business_verification_status, "probe_verified")
        self.assertEqual(dict(ctx.response_evaluation or {}), {"origin": "model"})


class _StaticCollector(Collector):
    """A Collector that always emits a fixed evidence list."""

    source = "ai_judge"

    def __init__(self, evidences: list[Evidence] | None) -> None:
        self._evidences = evidences

    def collect(self, ctx: CollectorContext) -> list[Evidence]:
        # Returning the stored value verbatim — including ``None`` so
        # we can verify ``safe_collect``'s defensive normalisation.
        return self._evidences  # type: ignore[return-value]


class _BoomCollector(Collector):
    source = "ai_judge"

    def collect(self, ctx: CollectorContext) -> list[Evidence]:
        raise RuntimeError("boom")


class SafeCollectTests(unittest.TestCase):
    def test_returns_evidence_list_when_collector_succeeds(self):
        evi = Evidence(
            source="ai_judge",
            direction="defense_success",
            strength="strong",
            confidence=0.9,
            rationale="ok",
        )
        out = safe_collect(_StaticCollector([evi]), make_context())
        self.assertEqual(out, [evi])

    def test_returns_empty_list_when_collector_returns_none(self):
        out = safe_collect(_StaticCollector(None), make_context())
        self.assertEqual(out, [])

    def test_returns_empty_list_when_collector_raises(self):
        out = safe_collect(_BoomCollector(), make_context())
        self.assertEqual(out, [])

    def test_returns_empty_list_for_empty_emission(self):
        out = safe_collect(_StaticCollector([]), make_context())
        self.assertEqual(out, [])

    def test_safe_collect_never_returns_none(self):
        """Property check across all branches above."""
        for collector in (
            _StaticCollector(None),
            _StaticCollector([]),
            _BoomCollector(),
        ):
            with self.subTest(collector=collector.__class__.__name__):
                self.assertIsInstance(
                    safe_collect(collector, make_context()), list
                )


if __name__ == "__main__":
    unittest.main()
