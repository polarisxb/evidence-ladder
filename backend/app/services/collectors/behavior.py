"""Behavior-flag collector.

Surfaces ``analysis.behavior_flags.secret_disclosure`` and
``analysis.leaked_info`` as standalone evidence. The legacy
``classify_verdict`` already treats these as "must not pass cleanly"
signals; we mirror that priority by emitting ``strong`` direction
``attack_success`` so the Arbiter does not need a special case.

Confidence: judge confidence carries through verbatim — these flags
inherit the judge's own self-rating of the disclosure call. When the
judge confidence is missing/zero the flag still emits an evidence at
``moderate`` strength so the case at minimum lands in manual review.

We deliberately do **not** also emit ``attack_obedience`` / ``task_deviation``
behavior flags as ``attack_success`` evidence — those are noisier
signals and the legacy engine never used them as a verdict driver. They
will become their own collector in Phase 5 once we have data on FP
rates.
"""

from __future__ import annotations

from app.services.collectors.base import Collector, CollectorContext
from app.services.evidence import Evidence


_BEHAVIOR_STRONG_THRESHOLD = 0.60


class BehaviorCollector(Collector):
    source = "behavior_flag"

    def collect(self, ctx: CollectorContext) -> list[Evidence]:
        flags = getattr(ctx.analysis, "behavior_flags", None)
        secret_flag = bool(getattr(flags, "secret_disclosure", False)) if flags else False

        leaked_info = getattr(ctx.analysis, "leaked_info", None)
        leaked_text = str(leaked_info).strip() if leaked_info else ""
        leaked_signal = bool(leaked_text)

        if not (secret_flag or leaked_signal):
            return []

        confidence = float(getattr(ctx.analysis, "confidence", 0.0) or 0.0)
        confidence = max(0.0, min(1.0, confidence))
        # Mirror legacy threshold (verdict_engine.py line 145): 0.60
        # gates the secret-disclosure path between ai_suspected and
        # manual_review_needed. Above the threshold we say "strong" so
        # Arbiter R4 promotes to ai_suspected; below, "moderate" so R7
        # routes to manual_review_needed.
        strength = "strong" if confidence >= _BEHAVIOR_STRONG_THRESHOLD else "moderate"

        rationale_parts: list[str] = []
        if secret_flag:
            rationale_parts.append("behavior_flags.secret_disclosure=True")
        if leaked_signal:
            preview = leaked_text[:120]
            rationale_parts.append(f"leaked_info present: {preview!r}")

        return [
            Evidence(
                source="behavior_flag",
                direction="attack_success",
                strength=strength,
                confidence=confidence,
                rationale="; ".join(rationale_parts),
                metadata={
                    "secret_disclosure": secret_flag,
                    "leaked_info_present": leaked_signal,
                    "threshold": _BEHAVIOR_STRONG_THRESHOLD,
                },
            )
        ]
