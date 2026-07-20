# Evidence-Ladder Experiment: Academic-Rigor Audit

Date: 2026-07-12

## Verdict

The experiment pipeline now passes the implemented integrity invariants, and the
two valid relay configurations show the predicted qualitative thesis shape.
The evidence is still **exploratory, not publication-ready**.

The remaining blockers are experimental-design limitations rather than test
failures:

1. the target and state oracle are deterministic builtins, not a real deployed
   agent;
2. the relay exposes only rolling-looking IDs (`gpt-5.4`, `gpt-5.5`) and returns
   the same aliases in the response, so the actual model revision is unresolved;
3. the suite has 8 attack cases, 4 false attack cases, 1 clean case, and 1 benign
   distractor;
4. there are no human labels, so kappa is correctly `PENDING`;
5. relay token and monetary usage are not propagated through the evaluator, so
   those cells remain incomplete;
6. the current static `ground_truth: bool` schema cannot express a predeclared,
   response-derived canary oracle for a bare relay target.

## Integrity work completed

- Added driver-level tests for frozen-suite hashes, matrix roles and rolling
  aliases, exact cache reuse, nested forbidden-evidence rejection, fixed-response
  re-judging, and recursive black-box isolation.
- Fixed Arm A′ query accounting: one independent re-judge is one extra query,
  with zero target/probe queries.
- Fixed total query accounting to equal target retests + judge calls + probe
  steps, including quartet analyzer calls.
- Changed E1/E2 arbitration to select the strongest available ladder level:
  simultaneous text claim + judge suspicion is E2 while retaining both sources.
- Detected a state-integrity failure when resuming a cached builtin stateful run
  in a new process. The builtin state store is ephemeral, so the cached response
  survived while the state required by the E5 probe did not. Resume now fails
  fast for this configuration.
- Added `scripts/audit_experiment_output.py`, which checks cache/lineage
  cardinality, suite/model identity, forbidden evidence, arm caps and query
  separation, cost breakdown consistency, kappa status, and artifact checksums.
- Focused experiment/evidence suite: **125 passed**.
- Ruff over all changed experiment/evidence source and tests: **passed**.

## Valid runs

All valid runs used:

- frozen suite hash
  `2c5fc2d10cf373d70fa10b8492cf01d55b3bf065d57d3dca238d65e7b6e259a5`;
- builtin stateful target `builtin-stateful.v1`;
- one cached initial response shared by A, A′, and B;
- 5,000 bootstrap resamples, seed `20260712`;
- distinct relay judge and verifier model IDs.

| Configuration | Arm | Judge ASR | Strong ASR | Attack FP | Overturn | Extra queries |
|---|---|---:|---:|---:|---:|---:|
| Judge 5.5 → verifier 5.4 | A | 87.5% | 0% | 75% | 0% | 0 |
|  | A′ | 100% | 0% | 100% | 0% | 1 judge |
|  | B | 50% | 50% | 0% | 37.5% | 0.875 probe |
| Judge 5.4 → verifier 5.5 | A | 100% | 0% | 100% | 0% | 0 |
|  | A′ | 87.5% | 0% | 75% | 0% | 1 judge |
|  | B | 50% | 50% | 0% | 50% | 1 probe |

The J5.5→V5.4 configuration was repeated from scratch. Its aggregate
`results.json` was byte-identical across the two runs. However, exact case-level
judge JSON agreed on only 80% of cases and verifier JSON on 60%; the differences
did not change the aggregate table. This is evidence of output instability even
at temperature zero and should be modeled with repeated trials in a formal
study.

## Critical interpretation

The thesis shape is robust to swapping the two relay models:

- A and A′ report 87.5–100% ASR and 75–100% false-positive rate while producing
  no E3+ evidence.
- Re-judging does not consistently improve results. It worsens A in one role
  assignment and modestly improves it in the reverse assignment.
- B is stable at 50% ASR, 50% strong-evidence ASR, and 0% observed attack false
  positives, using at most one probe per evaluated attack in these runs.
- B's lower ASR is not merely conservative suppression: its four positives are
  E5 state confirmations, while false textual claims are overturned or left
  negative when the initial judge did not raise an actionable claim.

The magnitudes are fixture-dependent. The builtin suite deliberately contains
four true state changes and four false textual claims, so B's 50% ASR is largely
determined by construction. The real contribution of these runs is validating
the judge/re-judge behavior and the arm separation, not estimating a population
effect size.

## Confidence-interval sensitivity

The required percentile bootstrap intervals are retained, but boundary samples
produce misleadingly degenerate intervals. Examples from J5.5→V5.4:

| Cell | Estimate | Bootstrap 95% | Wilson 95% | Jeffreys 95% |
|---|---:|---:|---:|---:|
| A ASR, 7/8 | 87.5% | 62.5–100% | 52.9–97.8% | 54.6–98.6% |
| A′ ASR, 8/8 | 100% | 100–100% | 67.6–100% | 73.8–100% |
| B ASR, 4/8 | 50% | 12.5–87.5% | 21.5–78.5% | 19.9–80.1% |
| A FP, 3/4 | 75% | 25–100% | 30.1–95.4% | 28.4–97.2% |
| A′ FP, 4/4 | 100% | 100–100% | 51.0–100% | 55.5–100% |
| B FP, 0/4 | 0% | 0–0% | 0–49.0% | 0.01–44.5% |

Therefore `[0,0]` and `[1,1]` bootstrap cells must not be read as certainty.
Wilson or Jeffreys intervals should accompany the bootstrap table until the
suite is large enough for the bootstrap to be informative.

## Outcome-definition sensitivity

The current `judge_asr` definition treats any non-overturned E1–E5 finding as a
reported positive, including `manual_review`. A stricter confirmed-only
definition gives A=A′=0 because judge-only arms are capped at E2; this is useful
for evidence confirmation but not as a measure of judge reporting behavior.

Using the judge's explicit `ai_suspected` status instead of the broad
manual-review-positive rule yields:

- J5.5→V5.4 run 1: A 87.5% ASR / 75% FP; A′ 87.5% / 75%.
- J5.5→V5.4 run 2: A 87.5% / 75%; A′ 100% / 100%.
- J5.4→V5.5: A 87.5% / 75%; A′ 87.5% / 75%.
- B remains 50% confirmed ASR and 0% observed FP under all definitions.

Thus the qualitative conclusion is not dependent on counting manual review as
positive, but the exact A/A′ cells are definition-sensitive and must be named
explicitly in the paper.

## Excluded runs

- `relay-gpt55-exploratory-20260712T1307Z`: predates the cost-accounting fix,
  uses the same model for judge and verifier, and fails the new integrity audit.
- `rigor-j54-v55-r1-20260712`: the initial process was interrupted after caching
  responses; resuming in a fresh process lost the builtin state and incorrectly
  overturned true state changes. It is invalid and excluded.

## Required next step for publication evidence

Implement a predeclared dynamic oracle and repeated-execution protocol for a
real target, or use a real agentic target with persistent observable state.
Then run a substantially larger, category-balanced suite with immutable model
revisions, independent model families, repeated trials, and blinded human
labels. Until those conditions are met, the correct claim is:

> The pipeline and qualitative mechanism are validated; the population-level
> effect size is not yet established.
