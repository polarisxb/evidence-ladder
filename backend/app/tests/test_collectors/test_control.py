"""Tests for ``ControlCollector``."""

import unittest

from app.services.collectors.control import ControlCollector

from ._helpers import make_context


class DiscussionSupportedTests(unittest.TestCase):
    def test_emits_moderate_defense_evidence(self):
        ctx = make_context(control_assessment="discussion_supported")
        result = ControlCollector().collect(ctx)
        self.assertEqual(len(result), 1)
        evi = result[0]
        self.assertEqual(evi.source, "control_comparison")
        self.assertEqual(evi.direction, "defense_success")
        self.assertEqual(evi.strength, "moderate")
        self.assertEqual(
            evi.metadata.get("control_assessment"), "discussion_supported"
        )


class AttackDeltaSupportedTests(unittest.TestCase):
    def test_emits_moderate_attack_evidence(self):
        ctx = make_context(control_assessment="attack_delta_supported")
        result = ControlCollector().collect(ctx)
        self.assertEqual(len(result), 1)
        evi = result[0]
        self.assertEqual(evi.source, "control_comparison")
        self.assertEqual(evi.direction, "attack_success")
        self.assertEqual(evi.strength, "moderate")


class ControlSilenceTests(unittest.TestCase):
    def test_none_assessment_emits_nothing(self):
        ctx = make_context(control_assessment=None)
        self.assertEqual(ControlCollector().collect(ctx), [])

    def test_empty_string_assessment_emits_nothing(self):
        ctx = make_context(control_assessment="")
        self.assertEqual(ControlCollector().collect(ctx), [])

    def test_whitespace_only_emits_nothing(self):
        ctx = make_context(control_assessment="   ")
        self.assertEqual(ControlCollector().collect(ctx), [])

    def test_unknown_assessment_emits_nothing(self):
        """Unknown future values must not be guessed in either
        direction — Arbiter R7 will route to manual review."""
        for value in (
            "insufficient_signal",
            "ambiguous",
            "future_unknown_value",
        ):
            with self.subTest(value=value):
                ctx = make_context(control_assessment=value)
                self.assertEqual(ControlCollector().collect(ctx), [])


class ControlIndependenceTests(unittest.TestCase):
    """Other context fields must not affect the collector's output —
    the only input is ``control_assessment``."""

    def test_response_text_is_ignored(self):
        ctx = make_context(
            control_assessment="discussion_supported",
            target_response="any unrelated response text " * 20,
        )
        result = ControlCollector().collect(ctx)
        self.assertEqual(len(result), 1)

    def test_target_config_is_ignored(self):
        ctx = make_context(
            control_assessment="attack_delta_supported",
            target_config={"system_prompt": "huge prompt", "canary_tokens": ["X"]},
        )
        result = ControlCollector().collect(ctx)
        self.assertEqual(result[0].direction, "attack_success")


if __name__ == "__main__":
    unittest.main()
