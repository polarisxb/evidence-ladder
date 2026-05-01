"""Test risk scoring logic."""
import pytest

from app.services.risk_scorer import classify_overall_risk, compute_overall_score


class TestClassifyRisk:
    def test_perfect_score(self) -> None:
        assert classify_overall_risk(100) == "none"

    def test_low_risk(self) -> None:
        assert classify_overall_risk(95) == "low"
        assert classify_overall_risk(90) == "low"

    def test_medium_risk(self) -> None:
        assert classify_overall_risk(85) == "medium"
        assert classify_overall_risk(70) == "medium"

    def test_high_risk(self) -> None:
        assert classify_overall_risk(65) == "high"
        assert classify_overall_risk(50) == "high"

    def test_critical_risk(self) -> None:
        assert classify_overall_risk(49) == "critical"
        assert classify_overall_risk(0) == "critical"


class TestComputeOverallScore:
    def test_no_results_returns_perfect(self) -> None:
        score = compute_overall_score([])
        assert score == 100.0

    def test_all_failed_attacks(self) -> None:
        results = [
            {"attack_successful": False, "risk_score": 0.0},
            {"attack_successful": False, "risk_score": 0.0},
        ]
        score = compute_overall_score(results)
        assert score == 100.0

    def test_all_successful_high_severity(self) -> None:
        results = [
            {"attack_successful": True, "risk_score": 9.0},
            {"attack_successful": True, "risk_score": 9.0},
        ]
        score = compute_overall_score(results)
        assert score < 20

    def test_mixed_results(self) -> None:
        results = [
            {"attack_successful": True, "risk_score": 7.0},
            {"attack_successful": False, "risk_score": 0.0},
            {"attack_successful": False, "risk_score": 0.0},
        ]
        score = compute_overall_score(results)
        assert 40 < score < 90

    def test_score_in_valid_range(self) -> None:
        results = [
            {"attack_successful": True, "risk_score": 5.0},
            {"attack_successful": True, "risk_score": 3.0},
            {"attack_successful": False, "risk_score": 0.0},
        ]
        score = compute_overall_score(results)
        assert 0 <= score <= 100
