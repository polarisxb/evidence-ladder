# Builtin dry-run analysis

Status: no-cost builtin dry run. These synthetic results validate schema, isolation, oracle resolution, and analysis plumbing only.

## Integrity and scope

- Suite hash: `ab2d3cb17b6109791135370a54aee9398fe2b8c1f944126d13281abcceb18766`
- Blocks: 1; observations: 48
- Attack observations: 32 (16 dynamic-oracle positives / 16 negatives)
- Clean observations: 8; benign-distractor observations: 8
- Human kappa remains `PENDING`; no human labels were introduced.
- Monetary cost is 0 for this local builtin dry run.
- Model identity: local builtin target/judge/verifier; no provider calls.

## Shared initial judge baseline

- `initial_judge_reported_asr`: 1.000 (32/32); case-clustered 95% interval [1.000, 1.000].
- This baseline is computed once from the shared `initial_evidence_level`; the analyzer rejects any case whose initial evidence differs across A/A′/B.

## Judge-error correction estimands

| Arm | error rate | false-positive rate | false-negative rate | correct overturn | correct upgrade | confirmed E3+ upgrade | introduced error | net errors corrected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 0.500 | 1.000 | 0.000 | 0.000 | PENDING | PENDING | 0.000 | 0/32 (0.000) |
| A_prime | 0.500 | 1.000 | 0.000 | 0.000 | PENDING | PENDING | 0.000 | 0/32 (0.000) |
| B | 0.000 | 0.000 | 0.000 | 1.000 | PENDING | PENDING | 0.000 | 16/32 (0.500) |

## Pooled primary metrics

| Arm | final reported ASR | AI-suspected only | confirmed E3+ only | strong-evidence ASR | attack FP | evidence upgrade | extra queries | target retests | judge queries | actual tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| A_prime | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.000 | 1.000 | PENDING |
| B | 0.500 | 0.500 | 0.500 | 0.500 | 0.000 | 0.500 | 1.000 | 0.000 | 0.000 | 0.000 |

Clustered uncertainty uses 5,000 case-level bootstrap resamples. Wilson and Jeffreys intervals are also included in the JSON/CSV outputs for binary cells, especially boundary cells.

## Call and token accounting

| Component | Calls | Calls with metadata | Calls with tokens | Tokens |
|---|---:|---:|---:|---:|
| Shared initial target | 48 | 0 | 0 | None |
| Shared initial judge | 48 | 0 | 0 | None |
| A incremental | 0 | 0 | 0 | 0 |
| A′ incremental | 48 | 0 | 0 | None |
| B incremental | 48 | 0 | 48 | 0 |
| Total | 192 | 0 | 48 | None |

B's 48 incremental calls split into 0 target retests and 0 judge calls.

## B strong-evidence standalone rate

- Estimate: 0.500 (16/32).
- Wilson 95% interval: [0.336, 0.664].
- Jeffreys 95% interval: [0.333, 0.667].
- Case-clustered bootstrap 95% interval: [0.324, 0.677].
- This is the empirical rate to interpret. B−A and B−A′ strong-evidence rows are definitional because A/A′ are capped at E2 by construction.

## Key paired contrasts

| Contrast | Type | Estimate | case-clustered 95% interval |
|---|---|---:|---:|
| B_minus_A_error_rate | empirical | -0.500 | [-0.667, -0.323] |
| B_minus_A_prime_error_rate | empirical | -0.500 | [-0.676, -0.324] |
| B_minus_A_false_positive_rate | empirical | -1.000 | [-1.000, -1.000] |
| B_minus_A_false_negative_rate | empirical | 0.000 | [0.000, 0.000] |
| A_prime_minus_A_final_reported_asr | empirical | 0.000 | [0.000, 0.000] |
| B_minus_A_final_reported_asr | empirical | -0.500 | [-0.667, -0.333] |
| B_minus_A_strong_evidence_asr | definitional (baseline capped by construction) | 0.500 | [0.323, 0.677] |
| B_minus_A_prime_strong_evidence_asr | definitional (baseline capped by construction) | 0.500 | [0.333, 0.677] |

## Role-swap summary

| Role config | Arm | final reported ASR | AI-suspected only | confirmed E3+ only | strong-evidence ASR | attack FP | evidence upgrade |
|---|---|---:|---:|---:|---:|---:|---:|
| judge-builtin-judge.v1_verifier-builtin-verifier.v1 | A | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 0.000 |
| judge-builtin-judge.v1_verifier-builtin-verifier.v1 | A_prime | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 0.000 |
| judge-builtin-judge.v1_verifier-builtin-verifier.v1 | B | 0.500 | 0.500 | 0.500 | 0.500 | 0.000 | 0.500 |

## Interpretation

The shared initial judge baseline is separated from each arm's final reported-positive rate. This synthetic run exercises schema, oracle, isolation, and analysis paths without provider behavior.

These results are pipeline-validation fixtures only. They are not effect estimates and must not be used for power analysis.
