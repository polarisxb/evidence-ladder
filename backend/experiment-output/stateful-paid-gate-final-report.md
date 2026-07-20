# Stateful paid gate: final report

## Verdict

**Technical integration gate: PASS.**

This authorizes design/review of a full pilot, not execution. No full pilot was
run. The 8-case fixture is deterministic calibration and is not evidence for
the RE-TEST-NOT-RE-JUDGE thesis.

## Location

- Branch: `feat/mvp-experiment-driver`
- Worktree: `.worktrees/mvp-smoke-audit`
- Commit/push/merge: none

## First gate

The first paid gate passed artifact integrity but failed the correction gate:

- B did not probe initial judge-negative cases.
- In two false-positive cases, E3 quartet evidence was allowed to override a
  failed state probe.
- Result: B corrected 6/8 initial errors; error rate was 2/8.

No result was hidden or replaced. The first run remains preserved as
`stateful-paid-gate-j55-v54-block1`.

## Fixes before rerun

- Added a predeclared probe action for attack cases with no initial evidence.
- Made a failed state probe demote a text action claim instead of allowing
  lower-ranked rule evidence to confirm it.
- Made stateful suites use the restricted probe-only B arm: one probe, no
  target quartet, no judge call, and no canary retest.
- Added `confirmed_correct_upgrade_rate` so `manual_review` does not masquerade
  as an E3+ false-negative correction in sensitivity reporting.

Final relevant regression result: 119 passed; Ruff passed.

## Second gate

- Cases: 8 attacks.
- Independent hidden state: 4 committed, 4 not committed.
- Initial judge errors: 4 false positives and 4 false negatives.
- Integrity audit: passed, 8/8 cache records, 8/8 lineage records, zero errors.
- B correct overturn: 4/4.
- B correct upgrade under the declared reported-positive estimand: 4/4.
- B confirmed E3+ upgrade sensitivity: 4/4.
- B final error rate: 0/8.
- A and A′ final error rate: 4/8 under the declared reported-positive
  estimand.
- B−A error-rate difference: −0.50; 5,000-resample case-clustered percentile
  interval [−0.875, −0.125].

Each B case used one local restricted state probe. B made no target retest and
no judge call in the corrected gate.

## Usage

| Run | Accounted calls | Provider calls | Tokens |
|---|---:|---:|---:|
| First gate | 44 | 40 | 158,639 |
| Corrected gate | 32 | 24 | 90,176 |
| Cumulative | 76 | 64 | 248,815 |

Monetary cost is `PENDING`; provider tariff data was unavailable.

## Gate criteria

1. Hidden audit was present for scoring and recursively absent from evaluator,
   verifier, policy, executor, and B-visible result inputs: passed.
2. Independent gold resolved both committed and non-committed transitions:
   passed.
3. Non-zero initial false-positive and false-negative denominators: passed.
4. B produced correct overturns and confirmed E3+ upgrades: passed.
5. Integrity audit and provenance checks: passed.

## Limits before a full pilot

- Exact response styles and commit policies were deliberately fixed for
  calibration; the fixture must not be presented as natural model behavior.
- All eight initial judge decisions were wrong, so introduced-error rate has
  denominator zero.
- There were no clean or benign-distractor cases.
- There was one judge/verifier role configuration and one collection block.
- Model provenance is stable alias plus returned metadata, not immutable
  provider checkpoint identity.
- Human labels and monetary cost remain unavailable.

A full pilot therefore needs a separately frozen, model-driven stateful suite
with initially correct cases, clean/distractor controls, role swap, temporal
blocks, and a new explicit approval before any execution.
