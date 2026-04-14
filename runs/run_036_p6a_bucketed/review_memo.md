# run_036 review memo — P6-A Bucketed Selection by Path Length
Generated: 2026-04-14T12:38:34.822082

## Setup
- Source pool: all 715 cross-domain candidates (no pre-sort truncation)
- Buckets (T1): L2=35, L3=25, L4+=10 → top-70
- Buckets (T2, post-hoc): L2=50, L3=20, L4+=0 → top-70
- Ranker: R2 (evidence-only, no length penalty) inside each bucket
- Baselines: B1=R1 global top-70, B2=R3 global top-70
- Evidence window: ≤2023 | Validation: 2024-2025

## Metric 1: Investigability

| Condition | N | Inv Rate | Fail Rate |
|-----------|---|----------|-----------|
| B1 | 70 | 0.8857 | 0.1143 |
| B2 | 70 | 0.9429 | 0.0571 |
| T1 | 70 | 0.9429 | 0.0571 |
| T2 | 70 | 0.9286 | 0.0714 |

## Metric 2: Novelty Retention

- B2 baseline cross_domain_ratio: 0.5000
- T1 cross_domain_ratio: 0.4040, novelty_retention: 0.8080  (✗ FAIL)
- T2 cross_domain_ratio: 0.4524, novelty_retention: 0.9048  (✓ OK)

## Metric 3: Support Rate by Stratum

| Condition | Stratum | N | Inv Rate |
|-----------|---------|---|---------|
| B1 | L2 | 0 | — |
| B1 | L3 | 0 | — |
| B1 | L4+ | 0 | — |
| B2 | L2 | 0 | — |
| B2 | L3 | 0 | — |
| B2 | L4+ | 0 | — |
| T1 | L2 | 35 | 0.9714 |
| T1 | L3 | 25 | 0.88 |
| T1 | L4+ | 10 | 1.0 |
| T2 | L2 | 50 | 0.96 |
| T2 | L3 | 20 | 0.85 |
| T2 | L4+ | 0 | — |

## Metric 4: Long-Path Share (≥3-hop / 70)

| Condition | Long-path share | By length |
|-----------|----------------|-----------|
| B1 | 0.0000 (0/70) | L2=70 |
| B2 | 0.0000 (0/70) | L2=70 |
| T1 | 0.5000 (35/70) | L2=35, L3=25, L4=9, L5=1 |
| T2 | 0.2857 (20/70) | L2=50, L3=20 |

## Statistical Tests (Fisher exact vs baseline)

| Comparison | Δ | Cohen's h | p-value | Sig |
|------------|---|-----------|---------|-----|
| T1_vs_B2 | +0.0000 | +0.0000 | 1.0000 | no |
| T1_vs_B1 | +0.0572 | +0.2072 | 0.3660 | no |
| B2_vs_B1 | +0.0572 | +0.2072 | 0.3660 | no |
| T2_vs_B2 | -0.0143 | -0.0584 | 1.0000 | no |
| T2_vs_B1 | +0.0429 | +0.1488 | 0.5619 | no |
| T2_vs_T1 | -0.0143 | -0.0584 | 1.0000 | no |

## Decision (T1, pre-registered): [STRUCTURE_CONFIRMED_NOVELTY_FAIL]

**T1 > B1 but T1 ≤ B2 — bucketing beats naive baseline but can't match evidence ranking; structural exclusion real but R3 already compensates via evidence weighting [WARNING: novelty_retention=0.808 < 0.90]**

- T1_inv=0.9429, B2_inv=0.9429, B1_inv=0.8857
- Δ(T1–B2)=+0.0000, Δ(T1–B1)=+0.0572
- Novelty retention: 0.8080 (FAIL)
- Long-path gain (T1–B2): +0.5000

## Decision (T2, post-hoc exploratory): [WEAK_SUCCESS]

**T2 > B1 AND T2 ≈ B2 — 2-bucket matches standard with novelty OK**

- T2_inv=0.9286, B2_inv=0.9429, B1_inv=0.8857
- Δ(T2–B2)=-0.0143, Δ(T2–B1)=+0.0429
- Novelty retention: 0.9048 (OK)

## Interpretation

### T1 (pre-registered, 3-bucket: L2=35, L3=25, L4+=10)

**Outcome: STRUCTURE_CONFIRMED_NOVELTY_FAIL**

T1 demonstrates that bucketed selection *does* change which paths enter the top-70 — the
long-path share jumped from 0% to 50% (35/70 are now L3/L4+ paths). This confirms the
mechanistic hypothesis: global top-k was structurally excluding longer paths.

However, two findings emerged that limit T1's practical value:

1. **Novelty constraint violated**: T1 novelty_retention = 0.808 < 0.90 (hard constraint).
   The root cause is structural: a 3-hop path always contributes only 1/3 ≈ 0.333
   cross-domain edges, vs. 1/2 = 0.500 for 2-hop paths. With 35 longer-path slots (L3=25,
   L4+=10), the mean cross_domain_ratio drops from 0.50 to 0.40, failing the threshold.
   This is a **mathematical consequence of path geometry**, not a data quality issue.

2. **Investigability ceiling**: T1_inv = B2_inv = 0.9429. Bucketing did not improve
   investigability even though L4+ paths had stratum investigability of 1.0 (10/10). The
   reason: L4+ selected only 10 paths while dropping 10 high-quality L2 paths that were
   already investigated. Net effect: zero change.

**L4+ finding**: All 10 L4+ slots were filled (262 available). L4+ stratum inv=1.0 — these
paths ARE investigable. But including 10 L4+ paths at the cost of L2 slots yields no gain.

### T2 (post-hoc exploratory, 2-bucket: L2=50, L3=20)

**Outcome: WEAK_SUCCESS** ✓

T2 addresses T1's novelty failure by capping L3 at 20 slots (the mathematical upper bound
for novelty_retention ≥ 0.90 is L3 ≤ 20 with L3 cross_domain_ratio = 0.333).

Key finding: T2 achieves the pre-registered weak success criterion:
- T2_inv = 0.9286 > B1_inv = 0.8857 ✓
- T2_inv ≈ B2_inv (Δ = −0.014, within ±2pp) ✓
- novelty_retention = 0.905 ≥ 0.90 ✓
- long_path_share = 0.286 (20/70 L3 paths now present, vs 0% in B2) ✓

**Interpretation**: Including 20 evidence-supported L3 paths maintains investigability at
near-baseline while introducing path-length diversity. This is not a productivity gain
(inv does not exceed B2) but a **composition improvement**: the same investigability
rate is achieved with 29% of slots contributed by longer-path hypotheses.

### Overall Conclusion for P6-A

- **Mechanistic hypothesis confirmed**: global top-k structurally excludes longer paths
  (T1 long_path_share = 50% vs B2 = 0%, confirming the structural exclusion diagnosis).
- **Practical result (T2)**: WEAK_SUCCESS. 2-bucket (L2=50, L3=20) achieves weak success
  with novelty constraint satisfied. This is the most aggressive L3 inclusion compatible
  with novelty_retention ≥ 0.90.
- **L4+ finding**: L4+ paths are individually investigable (inv=1.0) but including them
  forces novelty_retention below 0.90. L4+ inclusion is incompatible with the novelty
  constraint given the current KG's path geometry.
- **R3 note**: B2 (global R3 top-70) achieves the same investigability as T1 with better
  novelty. R3's evidence weighting already implicitly compensates for structural exclusion
  within the L2-dominated pool. Bucketing adds path diversity but not investigability gain.

### Recommendation for P6-B / P7

- P6-B (Augmentation Lane): Given T2 weak success, augmentation lane with L3-style
  paths (1 cross-domain edge per path) might be tested. But the novelty constraint will
  likely limit augmented slots to ≤ 20 as well.
- P7 (KG expansion): The ceiling analysis holds — with 715 candidates and 90 unique
  endpoint pairs, the investigation space is saturated. KG expansion remains the primary
  lever for structural improvement beyond the 89–94% investigability range.

## Artifacts
- top70_B1.json, top70_B2.json, top70_T1.json, top70_T2.json — ranked selections
- metrics_by_condition.json — 4 metrics × 4 conditions
- statistical_tests.json — pairwise Fisher tests
- decision.json — pre-registered + exploratory outcomes
- run_config.json — experiment configuration
