# Stateful correction redesign: paid-run gate

## Status

Schema, hidden-oracle isolation, correctness estimands, audit support, and a
no-cost builtin dry run are complete. No paid target, judge, verifier, or relay
calls were made during this redesign.

## Implemented

- `hidden_state_transition` ground-truth oracle with `temperature > 0` gate.
- Sealed `GroundTruthArtifact` retained in the initial-pass cache for scoring.
- Hidden audit extraction and removal before evaluator/verifier/retest inputs.
- Independent builtin hidden-state reader and separate B-visible probe channel.
- Error, false-positive, false-negative, correct-overturn, correct-upgrade,
  introduced-error, and net-error-correction estimands.
- Paired B−A and B−A′ error-rate contrasts with 5,000 case-clustered bootstrap.
- Audit support for validating exported truth against sealed artifacts.
- 48-case no-cost fixture: 32 attacks, 8 clean, 8 benign distractors; attack
  oracle outcomes are balanced 16 committed / 16 not committed.

## Verification

- Relevant retest/experiment tests: 110 passed.
- Analyzer-specific tests: 13 passed.
- Hidden-oracle audit test: passed.
- Suite-builder tests: 2 passed.
- Ruff: passed for all changed redesign files.
- Dry-run integrity audit: passed, 48/48 cache and lineage records, zero errors.

## No-cost dry-run result

This is synthetic pipeline validation, not evidence for the thesis.

| Arm | Error | FP | FN | Correct overturn | Correct upgrade | Introduced error |
|---|---:|---:|---:|---:|---:|---:|
| A | 50% | 100% | 0% | 0% | unavailable | 0% |
| A′ | 50% | 100% | 0% | 0% | unavailable | 0% |
| B | 0% | 0% | 0% | 100% | unavailable | 0% |

B corrected 16/16 initial errors and introduced 0; paired B−A error difference
was −50 percentage points. The builtin judge emitted no false negatives, so the
correct-upgrade path is covered by unit tests but not by this dry run.

## Old pilot reanalysis

Using the new correctness estimands on the existing six paid blocks:

- A, A′, and B error rate: 50% each.
- A, A′, and B false-positive rate: 100% each.
- B−A and B−A′ error difference: 0.

This confirms the old response-canary fixture cannot support a judge-error
correction claim.

## Paid-run recommendation

Do not jump directly to a full formal pilot. First run a small provider-backed
stateful integration block that deliberately contains both initial-judge false
positives and false negatives, then require:

1. hidden audit artifact present and stripped from every evaluator/B input;
2. independent gold resolving both committed and non-committed transitions;
3. non-zero denominators for correct-overturn and correct-upgrade;
4. integrity audit pass before any expansion.

Only after that gate should the full multi-block paid pilot run.
