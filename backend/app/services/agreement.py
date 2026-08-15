"""Inter-rater agreement metrics for judge reliability reporting.

Pure, dependency-free helpers used to quantify how *reproducible* / *trustworthy*
the evaluation layer is — the core evidence a measurement paper needs:

* ``observed_agreement`` — raw fraction of labels that match.
* ``cohen_kappa`` — agreement corrected for chance (two raters).

Typical uses:
* judge-vs-judge: run the same fixed set of (payload, response) pairs through the
  judge twice and measure stability (ideally with ``judge_deterministic=True``);
* judge-vs-human: compare judge labels against a human-annotated gold set.
"""
from collections import Counter
from collections.abc import Sequence


def observed_agreement(a: Sequence[object], b: Sequence[object]) -> float:
    if len(a) != len(b):
        raise ValueError("label sequences must have equal length")
    if not a:
        raise ValueError("label sequences must be non-empty")
    matches = sum(1 for x, y in zip(a, b) if x == y)
    return matches / len(a)


def cohen_kappa(a: Sequence[object], b: Sequence[object]) -> float:
    """Cohen's kappa for two raters over the same items.

    Returns 1.0 for perfect agreement; 0.0 for chance-level. When both raters
    use a single constant label (no variance) kappa is undefined — we return
    1.0 if they fully agree, else 0.0.
    """
    if len(a) != len(b):
        raise ValueError("label sequences must have equal length")
    n = len(a)
    if n == 0:
        raise ValueError("label sequences must be non-empty")

    po = observed_agreement(a, b)
    count_a = Counter(a)
    count_b = Counter(b)
    labels = set(count_a) | set(count_b)
    pe = sum((count_a.get(k, 0) / n) * (count_b.get(k, 0) / n) for k in labels)

    if pe == 1.0:
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1.0 - pe)


def agreement_report(a: Sequence[object], b: Sequence[object]) -> dict:
    """Convenience bundle: n, observed agreement and Cohen's kappa."""
    return {
        "n": len(a),
        "observed_agreement": observed_agreement(a, b),
        "cohen_kappa": cohen_kappa(a, b),
    }
