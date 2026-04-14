# run_032_selection_redesign — Review Memo

Date: 2026-04-14

## Summary

WS1 (Compose Diagnostics) proved augmented paths are displaced by shortest-path selection.
WS2 implemented 5 selection policies (A=Baseline, B=Quota, C=Novelty, D=Multi-bucket, E=Reranking).
WS3 ran 10 conditions (5 policies × 2 KGs) + 2 C1 baselines.
WS4 measured augmentation effect within each policy.
WS5 interpreted results and chose Final Decision.

## Condition Results

| Condition | N | Inv Rate | Fail Rate | Aug% | Diversity |
|-----------|---|----------|-----------|------|-----------|
| A_baseline_original | 70 | 0.886 | 0.114 | 0.00 | 70 |
| A_baseline_augmented | 70 | 0.886 | 0.114 | 0.00 | 70 |
| B_augmentation_quota_original | 70 | 0.886 | 0.114 | 0.00 | 70 |
| B_augmentation_quota_augmented | 70 | 0.829 | 0.171 | 0.21 | 70 |
| C_novelty_boost_original | 70 | 0.843 | 0.157 | 0.00 | 70 |
| C_novelty_boost_augmented | 70 | 0.786 | 0.214 | 0.30 | 70 |
| D_multi_bucket_original | 70 | 0.886 | 0.114 | 0.00 | 70 |
| D_multi_bucket_augmented | 70 | 0.814 | 0.186 | 0.36 | 70 |
| E_reranking_layer_original | 70 | 0.871 | 0.129 | 0.00 | 70 |
| E_reranking_layer_augmented | 70 | 0.814 | 0.186 | 0.26 | 70 |
| C1_original | 70 | 0.971 | 0.029 | 0.00 | 70 |
| C1_augmented | 70 | 0.971 | 0.029 | 0.00 | 70 |

## Augmentation Effect (WS4)

| Policy | Aug Reachable | ΔInv Rate | ΔAug% |
|--------|---------------|-----------|-------|
| A_baseline | False | +0.0000 | +0.0000 |
| B_augmentation_quota | True | -0.0571 | +0.2143 |
| C_novelty_boost | True | -0.0572 | +0.3000 |
| D_multi_bucket | True | -0.0714 | +0.3571 |
| E_reranking_layer | True | -0.0571 | +0.2571 |

## Interpretation (WS5)

**Q1** (augmentation effective when reachable): False
**Q2** (best policy): A_baseline
**Q3** (shortest-path dominance confirmed): True
**Q4** (max aug inclusion rate): 35.70%

## Final Decision

**Decision B**: augmentation remains ineffective even when reachable
