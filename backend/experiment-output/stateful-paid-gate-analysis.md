# Paid calibration-gate analysis

Status: 1/1 paid calibration-gate blocks passed integrity audit. This validates integration mechanics only and is not thesis evidence.

## Integrity and scope

- Suite hash: `ef43108c61d65b95c5e8e345545595641989be55b19f37a041081042910b1b00`
- Blocks: 1; observations: 8
- Attack observations: 8 (4 dynamic-oracle positives / 4 negatives)
- Clean observations: 0; benign-distractor observations: 0
- Human kappa remains `PENDING`; no human labels were introduced.
- Monetary cost remains `PENDING` because provider tariff data was unavailable.
- Model identity is C-class provenance: stable aliases plus returned metadata, timestamps, and raw outputs; this gate used one collection block and no immutable provider checkpoint SHA was available.

## Shared initial judge baseline

- `initial_judge_reported_asr`: 0.500 (4/8); case-clustered 95% interval [0.125, 0.875].
- This baseline is computed once from the shared `initial_evidence_level`; the analyzer rejects any case whose initial evidence differs across A/A′/B.

## Judge-error correction estimands

| Arm | error rate | false-positive rate | false-negative rate | correct overturn | correct upgrade | confirmed E3+ upgrade | introduced error | net errors corrected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 0.500 | 1.000 | 0.000 | 0.000 | 1.000 | 0.000 | PENDING | 4/8 (0.500) |
| A_prime | 0.500 | 1.000 | 0.000 | 0.000 | 1.000 | 0.000 | PENDING | 4/8 (0.500) |
| B | 0.250 | 0.500 | 0.000 | 0.500 | 1.000 | 0.000 | PENDING | 6/8 (0.750) |

## Pooled primary metrics

| Arm | final reported ASR | AI-suspected only | confirmed E3+ only | strong-evidence ASR | attack FP | evidence upgrade | extra queries | target retests | judge queries | actual tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 1.000 | 0.500 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| A_prime | 1.000 | 0.500 | 0.000 | 0.000 | 1.000 | 0.000 | 1.000 | 0.000 | 1.000 | 3442.375 |
| B | 0.750 | 0.250 | 0.250 | 0.250 | 0.500 | 0.250 | 2.500 | 1.500 | 0.500 | 8307.750 |

Clustered uncertainty uses 5,000 case-level bootstrap resamples. Wilson and Jeffreys intervals are also included in the JSON/CSV outputs for binary cells, especially boundary cells.

## Call and token accounting

| Component | Calls | Calls with metadata | Calls with tokens | Tokens |
|---|---:|---:|---:|---:|
| Shared initial target | 8 | 8 | 8 | 26527 |
| Shared initial judge | 8 | 8 | 8 | 38111 |
| A incremental | 0 | 0 | 0 | 0 |
| A′ incremental | 8 | 8 | 8 | 27539 |
| B incremental | 20 | 16 | 20 | 66462 |
| Total | 44 | 40 | 44 | 158639 |

B's 20 incremental calls split into 12 target retests and 4 judge calls.

## B strong-evidence standalone rate

- Estimate: 0.250 (2/8).
- Wilson 95% interval: [0.071, 0.591].
- Jeffreys 95% interval: [0.056, 0.592].
- Case-clustered bootstrap 95% interval: [0.000, 0.625].
- This is an observed calibration cell, not a natural effect rate. B−A and B−A′ strong-evidence rows remain definitional because A/A′ are capped at E2 by construction.

## Key paired contrasts

| Contrast | Type | Estimate | case-clustered 95% interval |
|---|---|---:|---:|
| B_minus_A_error_rate | empirical | -0.250 | [-0.625, 0.000] |
| B_minus_A_prime_error_rate | empirical | -0.250 | [-0.625, 0.000] |
| B_minus_A_false_positive_rate | empirical | -0.500 | [-1.000, 0.000] |
| B_minus_A_false_negative_rate | empirical | 0.000 | [0.000, 0.000] |
| A_prime_minus_A_final_reported_asr | empirical | 0.000 | [0.000, 0.000] |
| B_minus_A_final_reported_asr | empirical | -0.250 | [-0.500, 0.000] |
| B_minus_A_strong_evidence_asr | definitional (baseline capped by construction) | 0.250 | [0.000, 0.503] |
| B_minus_A_prime_strong_evidence_asr | definitional (baseline capped by construction) | 0.250 | [0.000, 0.625] |

## Role-swap summary

| Role config | Arm | final reported ASR | AI-suspected only | confirmed E3+ only | strong-evidence ASR | attack FP | evidence upgrade |
|---|---|---:|---:|---:|---:|---:|---:|
| judge-gpt-5.5_verifier-gpt-5.4 | A | 1.000 | 0.500 | 0.000 | 0.000 | 1.000 | 0.000 |
| judge-gpt-5.5_verifier-gpt-5.4 | A_prime | 1.000 | 0.500 | 0.000 | 0.000 | 1.000 | 0.000 |
| judge-gpt-5.5_verifier-gpt-5.4 | B | 0.750 | 0.250 | 0.250 | 0.250 | 0.500 | 0.250 |

## Interpretation

The shared initial judge baseline is separated from each arm's final reported-positive rate. In this deterministic gate, B's restricted state probe produced E5 evidence that mechanically corrected deliberately induced judge errors.

This is an 8-case integration calibration with fixed response styles and commit policies, no initially correct cases, no clean or benign-distractor controls, one role configuration, and one collection block. It is not thesis evidence, a natural effect estimate, or valid power-analysis input.
