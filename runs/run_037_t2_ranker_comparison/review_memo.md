# run_037 review memo — T2×R2 vs T2×R3 Ranker Comparison
Generated: 2026-04-14T13:09:45.972980

## Setup
- Bucket structure: T2 (L2=50, L3=20, L4+=0) fixed from run_036
- T2_R2: evidence-only (e_score_min DESC) within each bucket
- T2_R3: R3 global-pool normalization (0.4×struct + 0.6×evid) within each bucket
- Evidence cache: run_036 (695 entries, full 715-candidate coverage)
- Pubmed cache: run_036 (343 entries)

## Pre-registered Prediction

**H_null (pre-registered)**: T2_R2 = T2_R3 (mathematical equivalence)

Within a homogeneous path-length stratum, 1/path_length is constant → R3 structural
term is constant → R3 rank = R2 rank within each bucket.

## Results

| Condition | N | Inv Rate | Novelty Ret | Selection Overlap |
|-----------|---|----------|-------------|-------------------|
| T2_R2 | 70 | 0.9286 | 0.9048 | — |
| T2_R3 | 70 | 0.9286 | 0.9048 | 1.0000 |

## Prediction: ✓ CONFIRMED

- Jaccard(T2_R2, T2_R3) = 1.0000  (expected: 1.0000)
- Inv rate delta: +0.0000  (expected: 0.0000)
- Novelty retention delta: +0.0000  (expected: 0.0000)

## Decision: Use R2 as default ranker for P7

Mathematical equivalence confirmed empirically. R2 (evidence-only) is preferred
because:
1. Simpler: no structural normalization required
2. More interpretable: pure evidence signal
3. Equivalent to R3 within homogeneous path-length strata

**For P7's L4+ stratum** (containing mixed path_length=4 and 5): R2 ≠ R3
(different 1/path_length values within the stratum). A separate comparison
will be run within P7 to determine the better within-stratum ranker for L4+.

## Artifacts
- top70_T2_R2.json — T2 selection with R2
- top70_T2_R3.json — T2 selection with R3
- results.json — metrics + prediction outcome
- run_config.json — experiment configuration
