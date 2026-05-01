"""Regression tests for the shared finding classifier (direction 1: 口径统一).

These tests pin down four invariants that were broken before:

1. ``vulnerabilities_found`` has a single, verdict-driven definition — not
   "attack_successful OR rule_verified" in one path and "attack_successful"
   in another.
2. ``manual_review_needed`` (low-confidence AI judgement) is NOT counted as
   a vulnerability even when the underlying ``analysis.attack_successful``
   is True. It belongs in its own bucket so reviewers triage it explicitly
   instead of having it inflate the headline count.
3. ``compute_posture_metrics`` exposes a ``finding_counts`` breakdown that
   covers every finding class exactly once (total sums to ``total_tests``).
4. ``generate_report`` produces a ``finding_breakdown`` (keyed by verdict
   status) whose totals stay consistent with ``finding_counts`` (keyed by
   finding class). Previously cases with a disagreeing ``attack_successful``
   flag were silently dropped from ``finding_breakdown``, so the two views
   didn't sum to the same number of cases.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.schemas.report import AnalysisResult
from app.services.finding_classifier import (
    classify_finding,
    finding_class_counts,
    is_confirmed_finding,
)
from app.services.report_generator import generate_report, render_html_report
from app.services.risk_scorer import compute_posture_metrics


def _case_attempt(
    *,
    verdict_status: str | None,
    attack_successful: bool = False,
) -> dict:
    """Build a minimal case_attempt dict shaped like scan_runner produces."""
    return {
        "analysis": AnalysisResult(
            attack_successful=attack_successful,
            confidence=0.9,
            risk_level="medium" if attack_successful else "none",
            evidence="test-evidence",
            explanation="test-explanation",
            execution_mode="UNCERTAIN",
            blackbox_outcome=(
                "FULL_INJECTION_SUCCESS" if attack_successful else "NO_INJECTION_SUCCESS"
            ),
        ),
        "verdict": {
            "verdict_status": verdict_status,
            "verdict_reason": "unit-test",
            "rule_hits": [],
        } if verdict_status else {},
    }


def _flat_result(*, verdict_status: str | None, attack_successful: bool = False) -> dict:
    """Build a flat result dict shaped like scan_recovery / risk_scorer receives."""
    return {
        "attack_successful": attack_successful,
        "risk_score": 5.0 if attack_successful else 0.0,
        "verdict_status": verdict_status,
        "target_response": "some model output",
    }


class FindingClassifierTests(unittest.TestCase):
    def test_rule_verified_maps_to_confirmed_and_counts_as_vuln(self):
        attempt = _case_attempt(verdict_status="rule_verified", attack_successful=True)
        self.assertEqual(classify_finding(attempt), "confirmed")
        self.assertTrue(is_confirmed_finding(attempt))

    def test_ai_suspected_maps_to_suspected_and_counts_as_vuln(self):
        attempt = _case_attempt(verdict_status="ai_suspected", attack_successful=True)
        self.assertEqual(classify_finding(attempt), "suspected")
        self.assertTrue(is_confirmed_finding(attempt))

    def test_manual_review_needed_does_not_count_as_vuln(self):
        """Low-confidence AI judgement must not inflate the vuln count.

        This is the single most important behaviour change from direction 1:
        previously ``attack_successful=True + verdict=manual_review_needed``
        counted as a vulnerability in scan_runner (but not in scan_recovery),
        giving users a misleading "found X vulnerabilities" number that
        included unresolved judge calls.
        """
        attempt = _case_attempt(
            verdict_status="manual_review_needed", attack_successful=True
        )
        self.assertEqual(classify_finding(attempt), "needs_review")
        self.assertFalse(is_confirmed_finding(attempt))

    def test_passed_and_not_evaluable_and_false_positive_not_vulns(self):
        for status in ("passed", "not_evaluable", "false_positive"):
            with self.subTest(verdict=status):
                attempt = _case_attempt(verdict_status=status)
                self.assertFalse(is_confirmed_finding(attempt))

    def test_flat_result_shape_classified_the_same_as_case_attempt(self):
        """scan_recovery feeds flat dicts; scan_runner feeds case_attempts.

        Both must classify identically — that was the core inconsistency in
        vulnerabilities_found.
        """
        for status in (
            "rule_verified",
            "ai_suspected",
            "manual_review_needed",
            "passed",
            "not_evaluable",
            "false_positive",
        ):
            with self.subTest(verdict=status):
                attempt = _case_attempt(verdict_status=status, attack_successful=True)
                flat = _flat_result(verdict_status=status, attack_successful=True)
                self.assertEqual(classify_finding(attempt), classify_finding(flat))
                self.assertEqual(
                    is_confirmed_finding(attempt), is_confirmed_finding(flat)
                )

    def test_legacy_row_without_verdict_falls_back_to_attack_successful(self):
        """Historical AttackResult rows predate the verdict engine.

        They must still classify sensibly so archived scans don't silently
        become empty. attack_successful=True → suspected (not confirmed);
        attack_successful=False → passed.
        """
        self.assertEqual(
            classify_finding(_flat_result(verdict_status=None, attack_successful=True)),
            "suspected",
        )
        self.assertEqual(
            classify_finding(_flat_result(verdict_status=None, attack_successful=False)),
            "passed",
        )

    def test_finding_class_counts_covers_every_bucket_exactly_once(self):
        """Sum of all bucket counts must equal the number of inputs."""
        results = [
            _flat_result(verdict_status="rule_verified", attack_successful=True),
            _flat_result(verdict_status="ai_suspected", attack_successful=True),
            _flat_result(verdict_status="ai_suspected", attack_successful=True),
            _flat_result(verdict_status="manual_review_needed", attack_successful=True),
            _flat_result(verdict_status="passed"),
            _flat_result(verdict_status="not_evaluable"),
            _flat_result(verdict_status="false_positive"),
        ]
        counts = finding_class_counts(results)

        self.assertEqual(counts["confirmed"], 1)
        self.assertEqual(counts["suspected"], 2)
        self.assertEqual(counts["needs_review"], 1)
        self.assertEqual(counts["passed"], 1)
        self.assertEqual(counts["not_evaluable"], 1)
        self.assertEqual(counts["false_positive"], 1)
        self.assertEqual(sum(counts.values()), len(results))


class PostureMetricsBreakdownTests(unittest.TestCase):
    def test_posture_metrics_exposes_finding_counts_matching_classifier(self):
        """compute_posture_metrics must surface the same distribution that
        scan_runner / scan_recovery use to compute vulnerabilities_found.
        """
        results = [
            _flat_result(verdict_status="rule_verified", attack_successful=True),
            _flat_result(verdict_status="ai_suspected", attack_successful=True),
            _flat_result(verdict_status="manual_review_needed", attack_successful=True),
            _flat_result(verdict_status="passed"),
            _flat_result(verdict_status="not_evaluable"),
        ]
        metrics = compute_posture_metrics(results)

        # confirmed_findings is the headline number and must match
        # sum(is_confirmed_finding(r) for r in results).
        self.assertEqual(metrics["confirmed_findings"], 2)
        self.assertEqual(metrics["needs_review_count"], 1)
        self.assertEqual(metrics["false_positive_count"], 0)

        # finding_counts breakdown is the single source of truth.
        counts = metrics["finding_counts"]
        self.assertEqual(counts["confirmed"], 1)
        self.assertEqual(counts["suspected"], 1)
        self.assertEqual(counts["needs_review"], 1)
        self.assertEqual(counts["passed"], 1)
        self.assertEqual(counts["not_evaluable"], 1)
        self.assertEqual(counts["false_positive"], 0)
        self.assertEqual(sum(counts.values()), metrics["total_tests"])

    def test_empty_results_returns_zero_filled_finding_counts(self):
        metrics = compute_posture_metrics([])
        self.assertEqual(metrics["confirmed_findings"], 0)
        self.assertEqual(metrics["finding_counts"]["confirmed"], 0)
        self.assertEqual(sum(metrics["finding_counts"].values()), 0)
        # Every expected bucket must be present even on empty input so the
        # UI can bind without guards.
        expected_buckets = {
            "confirmed", "suspected", "needs_review",
            "passed", "not_evaluable", "false_positive",
        }
        self.assertEqual(set(metrics["finding_counts"].keys()), expected_buckets)

    def test_attack_successful_plus_manual_review_does_not_inflate_vulns(self):
        """End-to-end guard: the historically-divergent case is now consistent.

        Same dataset fed into compute_posture_metrics (which scan_runner's
        final posture uses) and is_confirmed_finding (which scan_runner's
        per-case _is_vuln_case uses) must agree on the count.
        """
        results = [
            # This is the problematic case: AI judge said successful but with
            # low confidence so verdict_engine downgraded to manual_review_needed.
            # It must NOT be counted as a vulnerability.
            _flat_result(verdict_status="manual_review_needed", attack_successful=True),
            _flat_result(verdict_status="manual_review_needed", attack_successful=True),
            _flat_result(verdict_status="ai_suspected", attack_successful=True),
        ]

        metrics = compute_posture_metrics(results)
        per_case_vuln_count = sum(1 for r in results if is_confirmed_finding(r))

        self.assertEqual(metrics["confirmed_findings"], 1)
        self.assertEqual(per_case_vuln_count, 1)
        self.assertEqual(metrics["needs_review_count"], 2)


def _fake_attack_result(
    *,
    result_id: str,
    verdict_status: str,
    attack_successful: bool,
    risk_level: str = "none",
    risk_score: float = 0.0,
) -> SimpleNamespace:
    """Minimal stand-in for ``AttackResult`` that ``generate_report`` can walk.

    ``generate_report`` only reads attributes off each result and asks
    ``_loaded_attack_case`` for an optional ``attack_case`` relationship via
    ``result.__dict__.get("attack_case")`` — a ``SimpleNamespace`` satisfies
    both paths without pulling in SQLAlchemy.
    """
    return SimpleNamespace(
        id=result_id,
        template_id="T_FAKE",
        category="prompt_injection",
        technique="unit_test",
        attack_name="fake-attack",
        payload_text="payload",
        target_response="some response",
        attack_successful=attack_successful,
        confidence=0.9 if attack_successful else 0.1,
        risk_level=risk_level,
        risk_score=risk_score,
        evidence="evidence" if attack_successful else None,
        leaked_info=None,
        explanation="explanation",
        remediation=None,
        owasp_id=None,
        analysis_raw={"verdict_status": verdict_status},
    )


def _fake_scan_task(results: list[SimpleNamespace]) -> SimpleNamespace:
    return SimpleNamespace(
        id="scan-fake",
        name="fake-scan",
        target_url="mock://target",
        total_attacks=len(results),
        completed_attacks=len(results),
        results=results,
        target_health=None,
        health_probe_passed=None,
        health_failure_reason=None,
        recent_health_signature=None,
        invalid_response_ratio=None,
    )


class ReportBreakdownConsistencyTests(unittest.TestCase):
    """Guard ``finding_breakdown`` (by verdict_status) against silently
    dropping cases whose ``attack_successful`` flag disagrees with the
    verdict engine. ``finding_breakdown`` and ``finding_counts`` must now
    sum to the same population of cases.
    """

    def _build_report(self, results: list[SimpleNamespace]):
        task = _fake_scan_task(results)
        return generate_report(task)

    def test_breakdown_and_counts_sum_to_total(self):
        """Every case must land in exactly one bucket on both views."""
        results = [
            _fake_attack_result(
                result_id="r1",
                verdict_status="rule_verified",
                attack_successful=True,
                risk_level="high",
                risk_score=8.0,
            ),
            _fake_attack_result(
                result_id="r2",
                verdict_status="manual_verified",
                attack_successful=True,
                risk_level="high",
                risk_score=7.5,
            ),
            _fake_attack_result(
                result_id="r3",
                verdict_status="ai_suspected",
                attack_successful=True,
                risk_level="medium",
                risk_score=5.0,
            ),
            # Key regression case: verdict says "needs human review" but the
            # legacy attack_successful flag is False. The old breakdown
            # logic dropped this case entirely. The new logic must keep it.
            _fake_attack_result(
                result_id="r4",
                verdict_status="manual_review_needed",
                attack_successful=False,
            ),
            _fake_attack_result(
                result_id="r5",
                verdict_status="false_positive",
                attack_successful=False,
            ),
            _fake_attack_result(
                result_id="r6",
                verdict_status="not_evaluable",
                attack_successful=False,
            ),
            _fake_attack_result(
                result_id="r7",
                verdict_status="passed",
                attack_successful=False,
            ),
        ]
        report = self._build_report(results)

        # Per-bucket sanity: each verdict_status contributes exactly 1,
        # including the previously-dropped manual_review_needed+False case.
        self.assertEqual(report.finding_breakdown["rule_verified"], 1)
        self.assertEqual(report.finding_breakdown["manual_verified"], 1)
        self.assertEqual(report.finding_breakdown["ai_suspected"], 1)
        self.assertEqual(report.finding_breakdown["manual_review_needed"], 1)
        self.assertEqual(report.finding_breakdown["false_positive"], 1)
        self.assertEqual(report.finding_breakdown["not_evaluable"], 1)

        # The only verdict_status NOT tracked in finding_breakdown is "passed"
        # (by design — it's the default/clean state), so:
        #   sum(finding_breakdown) + finding_counts["passed"] == total_attacks
        self.assertEqual(
            sum(report.finding_breakdown.values()) + report.finding_counts["passed"],
            report.total_attacks,
        )

        # Cross-view consistency: the six-bucket FindingClass distribution
        # must agree with the raw verdict_status counts.
        # confirmed = rule_verified + manual_verified
        self.assertEqual(
            report.finding_counts["confirmed"],
            report.finding_breakdown["rule_verified"]
            + report.finding_breakdown["manual_verified"],
        )
        self.assertEqual(
            report.finding_counts["suspected"], report.finding_breakdown["ai_suspected"]
        )
        self.assertEqual(
            report.finding_counts["needs_review"],
            report.finding_breakdown["manual_review_needed"],
        )
        self.assertEqual(
            report.finding_counts["false_positive"],
            report.finding_breakdown["false_positive"],
        )
        self.assertEqual(
            report.finding_counts["not_evaluable"],
            report.finding_breakdown["not_evaluable"],
        )
        # Scalar convenience fields track finding_counts.
        self.assertEqual(
            report.confirmed_findings, report.finding_counts["confirmed"]
            + report.finding_counts["suspected"],
        )
        self.assertEqual(
            report.needs_review_count, report.finding_counts["needs_review"]
        )
        self.assertEqual(
            report.false_positive_count, report.finding_counts["false_positive"]
        )

    def test_disagreeing_success_flag_still_lands_in_verdict_bucket(self):
        """A minimal regression guard: a single manual_review_needed case
        with ``attack_successful=False`` used to vanish from the breakdown.
        It must now register in the manual_review_needed bucket and in
        ``finding_counts["needs_review"]``.
        """
        results = [
            _fake_attack_result(
                result_id="only",
                verdict_status="manual_review_needed",
                attack_successful=False,
            ),
        ]
        report = self._build_report(results)

        self.assertEqual(report.finding_breakdown["manual_review_needed"], 1)
        self.assertEqual(report.finding_counts["needs_review"], 1)
        self.assertEqual(report.needs_review_count, 1)
        # And it must NOT leak into the vuln headline.
        self.assertEqual(report.confirmed_findings, 0)

    def test_html_export_headline_uses_confirmed_findings_not_successful_attacks(self):
        """The HTML export's headline "Vulnerabilities" number must match
        the single source of truth (``confirmed_findings``), not the
        legacy raw-AI-judge count ``successful_attacks``.

        Regression for the earlier drift where the HTML template rendered
        ``{{ successful_attacks }}`` under a "Vulnerabilities Found" label,
        producing a number that disagreed with the dashboard, the DB
        column ``scan_tasks.vulnerabilities_found``, and the frontend
        report's "Confirmed Findings" card.
        """
        # 3 manual_review_needed + 1 ai_suspected, all attack_successful=True.
        # successful_attacks = 4, but confirmed_findings must be 1 (only the
        # ai_suspected case is a real finding).
        results = [
            _fake_attack_result(
                result_id=f"mr{i}",
                verdict_status="manual_review_needed",
                attack_successful=True,
            )
            for i in range(3)
        ] + [
            _fake_attack_result(
                result_id="sus",
                verdict_status="ai_suspected",
                attack_successful=True,
                risk_level="medium",
                risk_score=5.0,
            ),
        ]
        report = self._build_report(results)
        self.assertEqual(report.successful_attacks, 4)
        self.assertEqual(report.confirmed_findings, 1)
        self.assertEqual(report.needs_review_count, 3)

        html = render_html_report(report)

        # Headline stat-value shows confirmed_findings (1), NOT
        # successful_attacks (4). The distinctive orange colour of the
        # headline stat lets us pin the assertion without false matches
        # elsewhere in the document.
        self.assertIn('style="color: #f97316;">1</div>', html)
        self.assertNotIn('style="color: #f97316;">4</div>', html)
        # Label updated to match the new semantics.
        self.assertIn("Confirmed Findings", html)
        self.assertNotIn(">Vulnerabilities Found<", html)

        # Full six-bucket split below the headline.
        self.assertIn("<strong>1</strong>confirmed", html)
        self.assertIn("<strong>3</strong>needs review", html)
        self.assertIn("<strong>0</strong>false positive", html)


if __name__ == "__main__":
    unittest.main()
