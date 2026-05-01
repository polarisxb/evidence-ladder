"""Single source of truth for classifying a scan result into finding buckets.

The scanner produces several overlapping signals for every case:

- ``analysis.attack_successful`` — the LLM judge's binary verdict.
- ``verdict_status``             — the ``verdict_engine`` / business-probe
                                    overlay that combines hard rule evidence,
                                    judge confidence, and probe results.
- ``rule_hits``                   — concrete evidence (canary / prompt overlap).

Historically ``vulnerabilities_found`` was computed inconsistently: the live
scan runner used ``attack_successful OR verdict == "rule_verified"`` while the
recovery path used ``attack_successful`` only. That produced different numbers
for the same data depending on how the scan finalized.

This module centralises the classification so the live runner, recovery path,
posture metrics, and report generation all agree on *what counts*.
"""

from __future__ import annotations

from typing import Any, Literal, Mapping

FindingClass = Literal[
    "confirmed",       # rule_verified — hard evidence (canary/prompt overlap/probe)
    "suspected",       # ai_suspected  — high-confidence AI judgement
    "needs_review",    # manual_review_needed — low-confidence, human in loop
    "passed",          # passed        — defense confirmed
    "not_evaluable",   # not_evaluable — no stable model response
    "false_positive",  # false_positive — business probe refuted AI claim
]

# Only these classes are counted towards ``vulnerabilities_found``. Everything
# else is tracked as a separate bucket so the UI can show the real distribution
# instead of collapsing "needs human review" into "is a vulnerability".
_VULN_CLASSES: frozenset[str] = frozenset({"confirmed", "suspected"})

_VERDICT_TO_CLASS: dict[str, FindingClass] = {
    "rule_verified": "confirmed",
    "manual_verified": "confirmed",  # analyst-promoted finding (front-end legacy)
    "ai_suspected": "suspected",
    "manual_review_needed": "needs_review",
    "passed": "passed",
    "not_evaluable": "not_evaluable",
    "false_positive": "false_positive",
}


def _extract_verdict_status(container: Mapping[str, Any] | None) -> str | None:
    """Pull ``verdict_status`` out of the various shapes the scanner uses.

    Accepts both a full ``case_attempt`` dict (with a nested ``verdict`` dict)
    and a flat result dict (as produced by scan_recovery / risk_scorer).
    """
    if not container:
        return None
    verdict = container.get("verdict")
    if isinstance(verdict, Mapping):
        status = verdict.get("verdict_status")
        if isinstance(status, str) and status:
            return status
    flat = container.get("verdict_status")
    if isinstance(flat, str) and flat:
        return flat
    analysis_raw = container.get("analysis_raw")
    if isinstance(analysis_raw, Mapping):
        status = analysis_raw.get("verdict_status")
        if isinstance(status, str) and status:
            return status
    return None


def _extract_attack_successful(container: Mapping[str, Any] | None) -> bool:
    """Best-effort boolean for legacy fallback classification.

    Only used when ``verdict_status`` is absent — the verdict engine should be
    the authoritative source for every case produced by the current pipeline.
    """
    if not container:
        return False
    analysis = container.get("analysis")
    if analysis is not None:
        flag = getattr(analysis, "attack_successful", None)
        if isinstance(flag, bool):
            return flag
        if isinstance(analysis, Mapping):
            flag = analysis.get("attack_successful")
            if isinstance(flag, bool):
                return flag
    flag = container.get("attack_successful")
    return bool(flag) if isinstance(flag, bool) else False


def classify_finding(container: Mapping[str, Any] | None) -> FindingClass:
    """Return the canonical finding class for a case attempt or result dict.

    Precedence:
    1. ``verdict_status`` if present and recognised.
    2. Legacy fallback based on ``attack_successful`` only (older persisted
       results that predate the verdict engine).
    """
    status = _extract_verdict_status(container)
    if status and status in _VERDICT_TO_CLASS:
        return _VERDICT_TO_CLASS[status]
    # Legacy data has no verdict_status: fall back to the old attack_successful
    # heuristic so historical rows still classify sensibly.
    if _extract_attack_successful(container):
        return "suspected"
    return "passed"


def is_confirmed_finding(container: Mapping[str, Any] | None) -> bool:
    """Return True iff the case should be counted in ``vulnerabilities_found``.

    Only ``confirmed`` (hard evidence) and ``suspected`` (AI high-confidence)
    count. ``needs_review`` is deliberately excluded — it represents "we don't
    know yet" and must be tracked in its own bucket so reviewers can triage it
    without inflating the headline vulnerability count.
    """
    return classify_finding(container) in _VULN_CLASSES


def finding_class_counts(containers: list[Mapping[str, Any]]) -> dict[str, int]:
    """Tabulate finding classes across a list of case attempts/results.

    Always returns an entry for every ``FindingClass`` value (zero-filled) so
    downstream consumers don't need to guard against missing keys.
    """
    # dict comprehension auto-dedupes the aliases in _VERDICT_TO_CLASS values
    # (e.g. both rule_verified and manual_verified map to "confirmed").
    counts: dict[str, int] = {cls: 0 for cls in _VERDICT_TO_CLASS.values()}
    for container in containers:
        cls = classify_finding(container)
        counts[cls] = counts.get(cls, 0) + 1
    return counts
