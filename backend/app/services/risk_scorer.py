"""
Risk scoring using CVSS v4.0 (industry standard).

Uses the `cvss` Python library by Red Hat Product Security
to compute standardized vulnerability scores.
"""

import logging
from typing import Literal

from cvss import CVSS4

from app.schemas.report import AnalysisResult, CvssMetrics
from app.services.finding_classifier import finding_class_counts, is_confirmed_finding
from app.services.response_screening import is_not_evaluable_response

logger = logging.getLogger(__name__)

RiskLevel = Literal["critical", "high", "medium", "low", "none"]

_VECTOR_MAP = {
    "attack_vector": {"N": "AV:N", "A": "AV:A", "L": "AV:L", "P": "AV:P"},
    "attack_complexity": {"L": "AC:L", "H": "AC:H"},
    "privileges_required": {"N": "PR:N", "L": "PR:L", "H": "PR:H"},
    "user_interaction": {"N": "UI:N", "P": "UI:P", "A": "UI:A"},
}

_IMPACT_MAP = {
    "confidentiality": "VC",
    "integrity": "VI",
    "availability": "VA",
}


def build_cvss_vector(metrics: CvssMetrics) -> str:
    parts = ["CVSS:4.0"]

    for field, mapping in _VECTOR_MAP.items():
        val = getattr(metrics, field, "N")
        parts.append(mapping.get(val, list(mapping.values())[0]))

    parts.append("AT:N")

    for field, prefix in _IMPACT_MAP.items():
        val = getattr(metrics, field, "N")
        parts.append(f"{prefix}:{val}")

    parts.extend(["SC:N", "SI:N", "SA:N"])

    return "/".join(parts)


def compute_cvss_score(metrics: CvssMetrics) -> tuple[float, str]:
    vector_string = build_cvss_vector(metrics)
    try:
        cvss = CVSS4(vector_string)
        score = cvss.scores()[0]
        severity = cvss.severities()[0]
        return float(score), str(severity)
    except Exception as e:
        logger.warning("CVSS calculation failed for vector %s: %s", vector_string, e)
        return 0.0, "None"


_FALLBACK_WEIGHTS: dict[str, float] = {
    "critical": 9.0,
    "high": 7.0,
    "medium": 5.0,
    "low": 3.0,
    "none": 0.0,
}


def _is_not_evaluable_result(result: dict) -> bool:
    if is_not_evaluable_response(result):
        return True

    verdict_status = result.get("verdict_status")
    if verdict_status == "not_evaluable":
        return True

    response = str(result.get("target_response") or "").strip().lower()
    return response.startswith("[error]") or response.startswith("error:")


def compute_risk_score(analysis: AnalysisResult) -> float:
    """Return raw CVSS score for successful attacks, 0.0 otherwise."""
    if not analysis.attack_successful:
        return 0.0

    if analysis.cvss_metrics:
        score, _ = compute_cvss_score(analysis.cvss_metrics)
        return round(score, 2)  # 返回原始 CVSS 分数，不乘 confidence

    return _FALLBACK_WEIGHTS.get(analysis.risk_level, 0.0)


_EMPTY_FINDING_COUNTS = {
    "confirmed": 0,
    "suspected": 0,
    "needs_review": 0,
    "passed": 0,
    "not_evaluable": 0,
    "false_positive": 0,
}


def compute_posture_metrics(results: list[dict]) -> dict[str, float | int]:
    """Compute transparent posture metrics for a scan.

    Results marked ``not_evaluable`` are treated as missing evidence rather
    than silent defense wins. They reduce evaluation coverage and therefore
    lower the final posture score instead of making the target look safer by
    default.

    In addition to the legacy scalar metrics, this now returns a
    ``finding_counts`` breakdown so the UI can show the real distribution of
    outcomes (confirmed / suspected / needs_review / passed / not_evaluable /
    false_positive) instead of collapsing everything into a binary
    "vulnerabilities_found" number. ``confirmed_findings`` is the headline
    count that matches ``scan_runner._is_vuln_case`` / ``scan_recovery``.
    """
    if not results:
        return {
            "total_tests": 0,
            "evaluable_tests": 0,
            "not_evaluable_tests": 0,
            "evaluation_coverage": 0.0,
            "successful_attacks": 0,
            "attack_success_rate": 0.0,
            "severity_ratio": 0.0,
            "average_finding_severity": 0.0,
            "security_posture_score": 100.0,
            "finding_counts": dict(_EMPTY_FINDING_COUNTS),
            "confirmed_findings": 0,
            "needs_review_count": 0,
            "false_positive_count": 0,
        }

    total_tests = len(results)
    not_evaluable_tests = sum(1 for r in results if _is_not_evaluable_result(r))
    evaluable_tests = max(total_tests - not_evaluable_tests, 0)
    successful_attacks = sum(
        1 for r in results
        if r.get("attack_successful") and not _is_not_evaluable_result(r)
    )
    total_risk = sum(
        r.get("risk_score", 0)
        for r in results
        if not _is_not_evaluable_result(r)
    )
    max_possible_risk = max(successful_attacks, 1) * 10.0

    asr = successful_attacks / total_tests if total_tests > 0 else 0.0
    evaluable_asr = successful_attacks / evaluable_tests if evaluable_tests > 0 else 0.0
    severity_ratio = total_risk / max_possible_risk if max_possible_risk > 0 else 0.0
    evaluation_coverage = evaluable_tests / total_tests if total_tests > 0 else 0.0

    average_finding_severity = (
        total_risk / successful_attacks if successful_attacks > 0 else 0.0
    )

    score = 100.0 * (1.0 - 0.5 * evaluable_asr - 0.5 * severity_ratio)
    score *= evaluation_coverage
    score = round(max(0.0, min(100.0, score)), 1)

    # Verdict-based finding distribution (single source of truth for the UI).
    counts = finding_class_counts(results)
    confirmed_findings = sum(1 for r in results if is_confirmed_finding(r))

    return {
        "total_tests": total_tests,
        "evaluable_tests": evaluable_tests,
        "not_evaluable_tests": not_evaluable_tests,
        "evaluation_coverage": round(evaluation_coverage * 100, 1),
        "successful_attacks": successful_attacks,
        "attack_success_rate": round(asr * 100, 1),
        "severity_ratio": round(severity_ratio * 100, 1),
        "average_finding_severity": round(average_finding_severity, 2),
        "security_posture_score": score,
        "finding_counts": counts,
        # Top-level convenience fields for quick UI binding — all derived from
        # `finding_counts` so the two views can never drift apart.
        "confirmed_findings": confirmed_findings,
        "needs_review_count": counts.get("needs_review", 0),
        "false_positive_count": counts.get("false_positive", 0),
    }


def compute_overall_score(results: list[dict]) -> float:
    """Compute an overall security score from 0 (worst) to 100 (best)."""
    return float(compute_posture_metrics(results)["security_posture_score"])


def classify_overall_risk(score: float) -> RiskLevel:
    """Map overall score to CVSS-aligned severity levels."""
    if score >= 100:
        return "none"
    elif score >= 90:
        return "low"
    elif score >= 70:
        return "medium"
    elif score >= 50:
        return "high"
    else:
        return "critical"
