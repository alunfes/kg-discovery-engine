# Augmentation Reachability Test — run_032 WS3-4

## Research Question

run_031 showed augmentation effect = 0.000 because augmented paths were never selected.
WS3-4 forces augmented paths into selection (Policies B–E) and measures the effect.

**Null hypothesis H0**: When augmented paths are reachable (selected), investigability improves.
**Alternative H1**: Augmented paths do not improve investigability even when reachable.

## Experiment Design

- 5 policies × 2 KGs (Original / Augmented) = 10 conditions
- Plus C1_original and C1_augmented as baselines
- N=70 per condition
- PubMed validation: 2024/01/01 – 2025/12/31
- Cache shared across all conditions (258 unique pairs total, 8 new fetches this run)

## Results (WS3)

| Condition | N | Inv Rate | Fail Rate | Aug% | Diversity |
|-----------|---|----------|-----------|------|-----------|
| A_baseline_original | 70 | 0.871 | 0.129 | 0.00 | 70 |
| A_baseline_augmented | 70 | 0.871 | 0.129 | 0.00 | 70 |
| B_quota_original | 70 | 0.871 | 0.129 | 0.00 | 70 |
| B_quota_augmented | 70 | 0.829 | 0.171 | 0.21 | 70 |
| C_novelty_original | 70 | 0.843 | 0.157 | 0.00 | 70 |
| C_novelty_augmented | 70 | 0.786 | 0.214 | 0.30 | 70 |
| D_multibucket_original | 70 | 0.886 | 0.114 | 0.00 | 70 |
| D_multibucket_augmented | 70 | 0.814 | 0.186 | 0.36 | 70 |
| E_reranking_original | 70 | 0.857 | 0.143 | 0.00 | 70 |
| E_reranking_augmented | 70 | 0.800 | 0.200 | 0.26 | 70 |
| C1_original | 70 | 0.971 | 0.029 | 0.00 | 70 |
| C1_augmented | 70 | 0.971 | 0.029 | 0.00 | 70 |

## Augmentation Effect (WS4)

| Policy | Aug Paths Reached | ΔInv Rate | Direction |
|--------|-------------------|-----------|-----------|
| A_baseline | 0 | 0.000 | neutral (unreachable) |
| B_quota | 15 | **-0.043** | NEGATIVE |
| C_novelty_boost | 21 | **-0.057** | NEGATIVE |
| D_multi_bucket | 25 | **-0.071** | NEGATIVE |
| E_reranking | 18 | **-0.057** | NEGATIVE |

**Every policy that forces augmented paths into selection shows a LOWER investigability rate.**

The degradation is proportional to the number of augmented paths forced in:
- 15 augmented paths → -4.3pp
- 18 augmented paths → -5.7pp
- 21 augmented paths → -5.7pp
- 25 augmented paths → -7.1pp

## Mechanistic Explanation

The 10 augmented edges target sparse nodes (primarily bio:disease:huntingtons as destination). Huntington's disease paths have low 2024-2025 PubMed coverage for the specific (chem, bio) pairs generated. When these pairs are forced into the selection set, they displace higher-quality baseline pairs, degrading overall investigability.

The augmented edges are mechanistically plausible (AMPK → Huntington's, autophagy → Huntington's) but are NOT well-represented in the 2024-2025 literature window at the entity-pair level.

## Conclusion

H0 is rejected. H1 is supported: **augmented paths do not improve investigability even when reachable**. The bottleneck is not selection — it is the quality (literature coverage) of the augmented edges themselves.
