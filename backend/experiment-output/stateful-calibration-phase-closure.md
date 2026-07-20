# Stateful correction calibration: phase closure

## Classification

This phase is closed as **CALIBRATION_NOT_ANALYSIS**.

- Engineering/integration gate: **PASS**
- Thesis evidence: **PENDING**
- Publication readiness: **false**
- Full pilot executed: **no**
- Commit/push/merge performed: **no**

The paid calibration used real provider target/judge/verifier calls, but the
response styles and hidden-state commit policies were deliberately fixed. Its
results validate implementation mechanics and must not be cited as an estimate
of natural model behavior or of the RE-TEST-NOT-RE-JUDGE effect.

## Source identity

- Branch: `feat/mvp-experiment-driver`
- Worktree: `.worktrees/mvp-smoke-audit`
- Base commit: `dbff1b1da965a380be990a2c970b48821bcc2d40`
- Source state: dirty local worktree; frozen by artifact checksums, not by a Git
  commit.

## Frozen runs

### First paid calibration

- Directory: `experiment-output/stateful-paid-gate-j55-v54-block1`
- Integrity: passed, 8/8 cache and lineage records, zero audit errors.
- Outcome: correction gate failed; B corrected 6/8 deliberately induced
  initial errors.
- Defects exposed:
  - initial judge-negative attack cases were not probed;
  - failed state probes could be overridden by E3 quartet evidence.
- This run remains preserved and was not replaced.

### Corrected paid calibration

- Directory: `experiment-output/stateful-paid-gate-j55-v54-block2`
- Integrity: passed, 8/8 cache and lineage records, zero audit errors.
- Initial calibration errors: 4 false positives and 4 false negatives.
- B correct overturn: 4/4.
- B confirmed E3+ upgrade: 4/4.
- B final error: 0/8.
- A and A′ confirmed E3+ upgrade: 0/4.
- B used one restricted local state probe per case and no target retest or
  incremental judge call.

## Usage

| Run | Accounted calls | Provider calls | Tokens |
|---|---:|---:|---:|
| First calibration | 44 | 40 | 158,639 |
| Corrected calibration | 32 | 24 | 90,176 |
| Cumulative | 76 | 64 | 248,815 |

Monetary cost remains `PENDING` because provider tariff data was unavailable.

## Frozen artifact inventory

- `experiments/stateful_paid_gate_suite.json`
- `experiments/stateful_paid_gate_models.json`
- both paid-calibration output directories and their `integrity-audit.json`
- `experiment-output/stateful-paid-gate-analysis.{json,csv,md}`
- `experiment-output/stateful-paid-gate-rerun-analysis.{json,csv,md}`
- `experiment-output/stateful-paid-gate-final-report.md`
- `experiment-output/formal-pilot-superseded-notice.md`
- relevant oracle, target, probe, retest-policy, arbiter, analyzer, audit, suite
  builder, and test files
- `experiment-output/stateful-calibration-phase-closure.sha256`

The SHA-256 manifest is the authoritative freeze record for this uncommitted
local source state. It includes every dirty non-output worktree file except
secret-bearing paths, plus the two raw calibration directories and the closure
reports.

## Superseded historical artifacts

Any earlier `formal-pilot-*` response-canary run using a deterministic
temperature-zero echo fixture is retained only as historical pipeline output.
It is superseded for thesis testing because its gold signal, judge signal, and
B canary evidence were not construct-independent. It must not be combined with
the stateful calibration or cited as confirmatory evidence. The aggregate
analysis and every historical output directory carry an explicit superseded
notice.

## Verification at closure

- Relevant regression tests: 119 passed before closure.
- Final focused oracle/retest/analyzer regression: 52 passed after the
  report-label changes (including 16 analyzer tests).
- Ruff: passed.
- Both integrity audits: passed after report regeneration.
- Reports now identify these runs as **Paid calibration-gate analysis**, not
  formal-pilot analysis.
- The builtin suite is labeled **Builtin dry-run analysis** and the old canary
  suite is labeled **Historical response-canary pilot analysis — superseded**.

## Allowed claims

- Hidden scorer artifacts can be kept out of evaluator, verifier, policy,
  executor, and B-visible inputs.
- The restricted state-probe path can mechanically overturn induced judge
  false positives and confirm induced judge false negatives.
- The gate exposed and verified fixes for two real implementation defects.
- Call, token, provenance, audit, and paired-analysis plumbing operates
  end-to-end.

## Prohibited claims

- Do not report 0/8 as a natural error rate or effect size.
- Do not use the calibration interval as power-analysis input.
- Do not claim real-world prevalence, temporal robustness, model robustness,
  clean utility, benign-distractor safety, or publication-grade evidence.
- Do not call either paid calibration run a formal pilot.

## Next phase

The next phase must be a separately frozen model-driven protocol in which the
target autonomously determines state-changing behavior. It needs initially
correct cases, clean and benign-distractor controls, role swaps, temporal
blocks, naturalistic validation, and a new explicit approval before any paid
execution.
