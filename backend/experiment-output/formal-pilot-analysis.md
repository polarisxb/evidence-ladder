# Historical response-canary pilot analysis — superseded

Status: 6/6 historical blocks passed integrity audit. Retained for pipeline provenance only; the fixture is construct-invalid for thesis testing.

## Integrity and scope

- Suite hash: `2dfef6f5461d8c4375070558cd7edb9b6a3ede1e4d46b8509d55d49ffd6ce748`
- Blocks: 6; observations: 240
- Attack observations: 144 (72 dynamic-oracle positives / 72 negatives)
- Clean observations: 48; benign-distractor observations: 48
- Human kappa remains `PENDING`; no human labels were introduced.
- Monetary cost remains `PENDING` because provider tariff data was unavailable.
- Model identity is C-class provenance: stable aliases plus returned metadata, timestamps, raw outputs, and temporal blocks; the historical fixture is superseded independently of model provenance.

## Shared initial judge baseline

- `initial_judge_reported_asr`: 0.465 (67/144); case-clustered 95% interval [0.280, 0.648].
- This baseline is computed once from the shared `initial_evidence_level`; the analyzer rejects any case whose initial evidence differs across A/A′/B.

## Judge-error correction estimands

| Arm | error rate | false-positive rate | false-negative rate | correct overturn | correct upgrade | confirmed E3+ upgrade | introduced error | net errors corrected |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 0.500 | 1.000 | 0.000 | PENDING | 1.000 | 0.000 | 0.518 | -67/144 (-0.465) |
| A_prime | 0.500 | 1.000 | 0.000 | PENDING | 1.000 | 0.000 | 0.518 | -67/144 (-0.465) |
| B | 0.500 | 1.000 | 0.000 | PENDING | 1.000 | 0.000 | 0.518 | -67/144 (-0.465) |

## Pooled primary metrics

| Arm | final reported ASR | AI-suspected only | confirmed E3+ only | strong-evidence ASR | attack FP | evidence upgrade | extra queries | target retests | judge queries | actual tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 1.000 | 0.465 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| A_prime | 1.000 | 0.451 | 0.000 | 0.000 | 1.000 | 0.035 | 1.000 | 0.000 | 1.000 | 4115.944 |
| B | 1.000 | 0.000 | 0.465 | 0.465 | 1.000 | 0.479 | 2.521 | 1.882 | 0.639 | 10464.653 |

Clustered uncertainty uses 5,000 case-level bootstrap resamples. Wilson and Jeffreys intervals are also included in the JSON/CSV outputs for binary cells, especially boundary cells.

## Call and token accounting

| Component | Calls | Calls with metadata | Calls with tokens | Tokens |
|---|---:|---:|---:|---:|
| Shared initial target | 240 | 240 | 240 | 807649 |
| Shared initial judge | 240 | 240 | 240 | 991605 |
| A incremental | 0 | 0 | 0 | 0 |
| A′ incremental | 240 | 240 | 240 | 992384 |
| B incremental | 363 | 363 | 363 | 1506910 |
| Total | 1083 | 1083 | 1083 | 4298548 |

B's 363 incremental calls split into 271 target retests and 92 judge calls.

## B strong-evidence standalone rate

- Estimate: 0.465 (67/144).
- Wilson 95% interval: [0.386, 0.547].
- Jeffreys 95% interval: [0.385, 0.547].
- Case-clustered bootstrap 95% interval: [0.275, 0.650].
- This is a historical pipeline diagnostic, not thesis evidence. B−A and B−A′ strong-evidence rows are also definitional because A/A′ are capped at E2 by construction.

## Key paired contrasts

| Contrast | Type | Estimate | case-clustered 95% interval |
|---|---|---:|---:|
| B_minus_A_error_rate | empirical | 0.000 | [0.000, 0.000] |
| B_minus_A_prime_error_rate | empirical | 0.000 | [0.000, 0.000] |
| B_minus_A_false_positive_rate | empirical | 0.000 | [0.000, 0.000] |
| B_minus_A_false_negative_rate | empirical | 0.000 | [0.000, 0.000] |
| A_prime_minus_A_final_reported_asr | empirical | 0.000 | [0.000, 0.000] |
| B_minus_A_final_reported_asr | empirical | 0.000 | [0.000, 0.000] |
| B_minus_A_strong_evidence_asr | definitional (baseline capped by construction) | 0.465 | [0.278, 0.650] |
| B_minus_A_prime_strong_evidence_asr | definitional (baseline capped by construction) | 0.465 | [0.278, 0.650] |

## Role-swap summary

| Role config | Arm | final reported ASR | AI-suspected only | confirmed E3+ only | strong-evidence ASR | attack FP | evidence upgrade |
|---|---|---:|---:|---:|---:|---:|---:|
| judge-gpt-5.4_verifier-gpt-5.5 | A | 1.000 | 0.472 | 0.000 | 0.000 | 1.000 | 0.000 |
| judge-gpt-5.4_verifier-gpt-5.5 | A_prime | 1.000 | 0.486 | 0.000 | 0.000 | 1.000 | 0.042 |
| judge-gpt-5.4_verifier-gpt-5.5 | B | 1.000 | 0.000 | 0.472 | 0.472 | 1.000 | 0.472 |
| judge-gpt-5.5_verifier-gpt-5.4 | A | 1.000 | 0.458 | 0.000 | 0.000 | 1.000 | 0.000 |
| judge-gpt-5.5_verifier-gpt-5.4 | A_prime | 1.000 | 0.417 | 0.000 | 0.000 | 1.000 | 0.028 |
| judge-gpt-5.5_verifier-gpt-5.4 | B | 1.000 | 0.000 | 0.458 | 0.458 | 1.000 | 0.486 |

## Interpretation

The shared initial response and arm accounting remain useful for pipeline regression. However, the deterministic temperature-zero fixture instructed canary echoing, so ground truth, judge-visible behavior, and B's response-canary evidence depended on substantially the same signal.

These historical results are superseded for thesis testing. They may document orchestration, temporal blocks, role swaps, provenance, and reporting mechanics, but they are not independent evidence of judge-error correction and must not be used for power analysis.
