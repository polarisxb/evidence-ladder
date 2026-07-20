# Historical response-canary pilot: before/after fixes — SUPERSEDED

This document is retained for defect provenance only. The temperature-zero
canary-echo fixture is construct-invalid for thesis testing; none of the
reported rates should be used as confirmatory evidence or power-analysis input.

The existing six blocks were reanalyzed without new model calls. All source
lineages, caches, manifests, and integrity-audit artifacts were retained.

## A1 — overturn semantics

- Before: `overturn_rate` read a nonexistent `lineage.overturned` key.
- After: an overturn is counted only when
  `outcome.final_verdict == "overturned"`.
- Numerical result: unchanged at `0/144` for every arm, because the retained
  artifacts contain no `overturned` final verdicts:
  - A: 240 `manual_review`;
  - A′: 240 `manual_review`;
  - B: 173 `manual_review`, 67 `confirmed`.

The unchanged value is now data-derived rather than silently forced to zero.

## A2 — initial judge versus final reported-positive metrics

The ambiguous `judge_asr` field was removed.

| Metric | A | A′ | B |
|---|---:|---:|---:|
| Old ambiguous `judge_asr` | 46.5% | 45.1% | 47.9% |
| New `final_reported_asr` | 100.0% | 100.0% | 100.0% |
| `ai_suspected_only` sensitivity | 46.5% | 45.1% | 0.0% |
| `confirmed_e3_plus_only` sensitivity | 0.0% | 0.0% | 46.5% |
| Strong-evidence ASR | 0.0% | 0.0% | 46.5% |
| Primary-estimand attack FP | 100.0% | 100.0% | 100.0% |

The shared baseline is now reported once:

- `initial_judge_reported_asr = 67/144 = 46.5%`;
- Wilson 95% interval: 38.6%–54.7%;
- Jeffreys 95% interval: 38.5%–54.7%;
- case-clustered bootstrap 95% interval: 28.0%–64.8%.

The analyzer now rejects any case whose `initial_evidence_level` differs
across A/A′/B.

The attack-FP change from 0% to 100% is expected: the old implementation used
“any final evidence” as a proxy, while the preregistered primary estimand
counts `manual_review` and `ai_suspected` as reported-positive. This exposes
the current fixture's inability to measure judge-error correction.

## A3 — definitional strong-evidence contrasts

The B−A and B−A′ strong-evidence differences remain numerically 46.5
percentage points, but are now labeled:

> definitional (baseline capped by construction)

They are not presented as empirical between-arm treatment effects.

The empirical standalone B rate is now explicit:

- `B_strong_evidence_asr_standalone = 67/144 = 46.5%`;
- Wilson 95% interval: 38.6%–54.7%;
- Jeffreys 95% interval: 38.5%–54.7%;
- case-clustered bootstrap 95% interval: 27.5%–65.0%.

The empirical final-reported contrasts are both zero:

- A′−A: 0.0 percentage points, clustered interval `[0.0, 0.0]`;
- B−A: 0.0 percentage points, clustered interval `[0.0, 0.0]`.

## Verification

- New focused tests: 10 passed.
- Combined relevant regression suite: 148 passed.
- Ruff: passed.
- No paid calls were made for this reanalysis.
- No commit, push, or merge was performed.
