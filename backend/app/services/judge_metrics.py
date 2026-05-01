"""Judge calibration metrics computation.

All computations operate on already-loaded sample objects (offline / snapshot_eval mode).
No access to live targets or probe execution.
"""
from __future__ import annotations

from collections import defaultdict

from app.models.judge_calibration_sample import JudgeCalibrationSample
from app.schemas.judge_calibration import (
    JudgeCalibrationBreakdownItem,
    JudgeCalibrationSummary,
    JudgeConfusionMatrix,
    JudgeMisclassificationPreview,
)


def _safe_div(num: int, den: int) -> float | None:
    return round(num / den, 4) if den > 0 else None


def _judge_reportable(sample: JudgeCalibrationSample) -> bool | None:
    judge_output = sample.judge_output or {}
    val = judge_output.get("reportable")
    return bool(val) if val is not None else None


def _gold_reportable(sample: JudgeCalibrationSample) -> bool | None:
    gold = sample.gold_label or {}
    val = gold.get("reportable")
    return bool(val) if val is not None else None


def _judge_verdict(sample: JudgeCalibrationSample) -> str | None:
    return (sample.judge_output or {}).get("verdict_status")


def _gold_verdict(sample: JudgeCalibrationSample) -> str | None:
    return (sample.gold_label or {}).get("verdict_status")


def _mismatch_type(sample: JudgeCalibrationSample) -> str | None:
    jr = _judge_reportable(sample)
    gr = _gold_reportable(sample)
    if jr is None or gr is None:
        return None
    if jr is True and gr is False:
        return "false_positive"
    if jr is False and gr is True:
        return "false_negative"
    jv = _judge_verdict(sample)
    gv = _gold_verdict(sample)
    if jv != gv:
        return "verdict_drift"
    return None


def _confusion(labeled: list[JudgeCalibrationSample]) -> tuple[int, int, int, int]:
    """Return (TP, FP, TN, FN) counts for the reportable label.

    A sample is a TP/TN/FP/FN iff both judge and gold have a concrete
    reportable value — samples with nulls are skipped. Kept as a separate
    helper from rate computation so callers that need the raw counts (e.g.
    the confusion matrix card on the Calibration page) can reuse it.
    """
    tp = fp = fn = tn = 0
    for s in labeled:
        jr = _judge_reportable(s)
        gr = _gold_reportable(s)
        if jr is None or gr is None:
            continue
        if jr and gr:
            tp += 1
        elif jr and not gr:
            fp += 1
        elif not jr and gr:
            fn += 1
        else:
            tn += 1
    return tp, fp, tn, fn


def _precision_recall_fpr(labeled: list[JudgeCalibrationSample]) -> tuple[float | None, float | None, float | None]:
    """Return (precision, recall, false_positive_rate) for reportable label."""
    tp, fp, tn, fn = _confusion(labeled)
    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    fpr = _safe_div(fp, fp + tn)
    return precision, recall, fpr


def _overturn_rate(labeled: list[JudgeCalibrationSample]) -> float | None:
    overturned = sum(
        1 for s in labeled
        if _judge_verdict(s) != _gold_verdict(s)
        and _judge_verdict(s) is not None
        and _gold_verdict(s) is not None
    )
    comparable = sum(
        1 for s in labeled
        if _judge_verdict(s) is not None and _gold_verdict(s) is not None
    )
    return _safe_div(overturned, comparable)


def _breakdown_by(
    labeled: list[JudgeCalibrationSample],
    key_fn,
) -> list[JudgeCalibrationBreakdownItem]:
    buckets: dict[str, list[JudgeCalibrationSample]] = defaultdict(list)
    for s in labeled:
        k = key_fn(s) or "unknown"
        buckets[k].append(s)
    items = []
    for k, bucket in sorted(buckets.items()):
        precision, recall, fpr = _precision_recall_fpr(bucket)
        items.append(JudgeCalibrationBreakdownItem(
            key=k,
            sample_count=len(bucket),
            precision=precision,
            false_positive_rate=fpr,
            recall=recall,
        ))
    return items


def compute_calibration_metrics(
    samples: list[JudgeCalibrationSample],
) -> JudgeCalibrationSummary:
    labeled = [s for s in samples if s.gold_label]
    precision, recall, fpr = _precision_recall_fpr(labeled)
    overturn = _overturn_rate(labeled)
    tp, fp, tn, fn = _confusion(labeled)
    confusion = JudgeConfusionMatrix(
        true_positive=tp,
        false_positive=fp,
        true_negative=tn,
        false_negative=fn,
        evaluated=tp + fp + tn + fn,
    )

    misclassified: list[JudgeMisclassificationPreview] = []
    for s in labeled:
        mt = _mismatch_type(s)
        if mt:
            snapshot = s.judge_input_snapshot or {}
            scan_id = snapshot.get("scan_id")
            misclassified.append(JudgeMisclassificationPreview(
                sample_id=s.id,
                attack_case_id=s.attack_case_id,
                scan_id=scan_id if isinstance(scan_id, str) else None,
                judge_verdict=_judge_verdict(s),
                gold_verdict=_gold_verdict(s),
                judge_reportable=_judge_reportable(s),
                gold_reportable=_gold_reportable(s),
                mismatch_type=mt,
            ))

    return JudgeCalibrationSummary(
        sample_count=len(samples),
        labeled_count=len(labeled),
        judge_precision_at_gold=precision,
        judge_recall_at_gold=recall,
        judge_false_positive_rate=fpr,
        manual_review_overturn_rate=overturn,
        confusion_matrix=confusion,
        by_category=_breakdown_by(
            labeled,
            lambda s: (s.judge_input_snapshot or {}).get("category"),
        ),
        by_source_type=_breakdown_by(labeled, lambda s: s.source_type),
        by_target_type=_breakdown_by(
            labeled,
            lambda s: (s.judge_input_snapshot or {}).get("target_type"),
        ),
        by_judge_version=_breakdown_by(
            labeled,
            lambda s: (s.judge_output or {}).get("judge_version"),
        ),
        by_business_verification_status=_breakdown_by(
            labeled,
            lambda s: (s.judge_input_snapshot or {}).get("business_verification_status"),
        ),
        misclassified_samples=misclassified[:50],
    )
