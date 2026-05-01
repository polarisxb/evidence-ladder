"""Tests for ``ProbeCollector``."""

import unittest

from app.services.collectors.probe import ProbeCollector

from ._helpers import make_context


class ProbeVerifiedTests(unittest.TestCase):
    def test_emits_hard_attack_evidence(self):
        ctx = make_context(business_verification_status="probe_verified")
        result = ProbeCollector().collect(ctx)
        self.assertEqual(len(result), 1)
        evi = result[0]
        self.assertEqual(evi.source, "probe_verification")
        self.assertEqual(evi.direction, "attack_success")
        self.assertEqual(evi.strength, "hard")
        self.assertEqual(evi.confidence, 1.0)
        self.assertEqual(
            evi.metadata.get("business_verification_status"), "probe_verified"
        )


class ProbeFailedTests(unittest.TestCase):
    def test_emits_hard_defense_evidence(self):
        ctx = make_context(business_verification_status="probe_failed")
        result = ProbeCollector().collect(ctx)
        self.assertEqual(len(result), 1)
        evi = result[0]
        self.assertEqual(evi.direction, "defense_success")
        self.assertEqual(evi.strength, "hard")
        self.assertEqual(evi.confidence, 1.0)


class TextClaimOnlyTests(unittest.TestCase):
    def test_emits_weak_inconclusive_evidence(self):
        ctx = make_context(business_verification_status="text_claim_only")
        result = ProbeCollector().collect(ctx)
        self.assertEqual(len(result), 1)
        evi = result[0]
        self.assertEqual(evi.direction, "inconclusive")
        self.assertEqual(evi.strength, "weak")
        # Low confidence so Arbiter never confuses this with a real signal.
        self.assertLess(evi.confidence, 0.5)


class ProbeSilenceTests(unittest.TestCase):
    def test_none_status_emits_nothing(self):
        ctx = make_context(business_verification_status=None)
        self.assertEqual(ProbeCollector().collect(ctx), [])

    def test_not_applicable_emits_nothing(self):
        ctx = make_context(business_verification_status="not_applicable")
        self.assertEqual(ProbeCollector().collect(ctx), [])

    def test_pending_emits_nothing(self):
        """Probe still running — collector must stay silent so the
        Arbiter does not pre-judge."""
        ctx = make_context(business_verification_status="pending")
        self.assertEqual(ProbeCollector().collect(ctx), [])

    def test_unknown_status_emits_nothing(self):
        """A future status the collector does not know about should
        not be silently mapped — better to stay silent."""
        for value in ("probe_inconclusive", "future_status", "PROBE_VERIFIED"):
            with self.subTest(value=value):
                ctx = make_context(business_verification_status=value)
                self.assertEqual(ProbeCollector().collect(ctx), [])

    def test_empty_string_emits_nothing(self):
        ctx = make_context(business_verification_status="")
        self.assertEqual(ProbeCollector().collect(ctx), [])


class ProbeIndependenceTests(unittest.TestCase):
    """Other context fields must not affect probe collector output."""

    def test_response_text_is_ignored(self):
        ctx = make_context(
            business_verification_status="probe_verified",
            target_response="any unrelated response",
        )
        result = ProbeCollector().collect(ctx)
        self.assertEqual(result[0].direction, "attack_success")

    def test_judge_outcome_is_ignored(self):
        from app.schemas.report import BehaviorFlags
        from ._helpers import make_analysis

        # Even if judge said NO_INJECTION, probe_verified wins for the
        # collector's own output. (Conflict resolution is the
        # Arbiter's job; the collector only reports what it sees.)
        ctx = make_context(
            business_verification_status="probe_verified",
            analysis=make_analysis(
                blackbox_outcome="NO_INJECTION_SUCCESS",
                confidence=0.95,
                behavior_flags=BehaviorFlags(),
            ),
        )
        result = ProbeCollector().collect(ctx)
        self.assertEqual(result[0].direction, "attack_success")
        self.assertEqual(result[0].strength, "hard")


if __name__ == "__main__":
    unittest.main()
