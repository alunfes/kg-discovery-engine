# run_036 Pre-registration: P6-A Bucketed Selection by Path Length
*Registered: 2026-04-14 — before any feature extraction or validation API calls*

---

## 1. Hypothesis

**H_P6A**: path-length bucketed selection improves investigability over global top-k selection
while maintaining novelty retention, by removing the structural disadvantage that
2-hop paths impose on longer paths.

The goal is NOT to rescue augmentation. It is to test whether global top-k selection
was structurally penalising longer paths regardless of their evidence quality.

---

## 2. Motivation

From P3/P4/P5/run_035:
- Pool-400 composition: L2=208 (52%), L3=192 (48%), L4+=0 (0%)
- Global top-k with R3 selects mostly L2 paths; L3 candidates are included only via
  their evidence score tiebreaking against a saturated L2 pool
- No L4+ candidates have ever appeared in the top-70 in any prior run
- run_035 showed R2 (evidence-only, no structural penalty) outperforms R3 numerically
  (R2: 0.914 > R3: 0.893 at N=140), suggesting the 1/path_length structural term
  may be suppressing longer paths with high evidence scores

**Key structural fact** (verified before registration):
- Total KG candidates: 715 (L2=208, L3=245, L4=173, L5=89)
- Pool-400 (run_033/035 pre-sort): ALL L2 (208) + first 192 L3; L4/L5 = 0
- To include L4+ candidates, pool must exceed 453 → incompatible with pool-400 constraint

**Resolution**: P6-A uses all 715 candidates as the source pool (not pre-truncated).
This is not a pool SIZE change; it is removal of the pre-sort truncation that
was silently excluding L4+ candidates from all prior runs. All 3 conditions use
the same 715-candidate source — pool is controlled, not an experimental variable.

---

## 3. Conditions

| Label | Selection | Ranker | Description |
|-------|-----------|--------|-------------|
| **B1** | global top-70 | R1 | Current baseline (replicates run_033 B at full pool) |
| **B2** | global top-70 | R3 | Tentative standard (replicates run_033 R3 at full pool) |
| **T1** | bucketed top-70 | R2 | P6-A: bucketed by path length, evidence-only ranker |

**Why R2 for T1 (not R3)?**
- run_035 showed R2 had larger numerical effect than R3 (h=0.160 vs h=0.088)
- R3's structural term (0.4 × 1/path_length) penalises longer paths — contradicts the
  goal of testing whether bucketing removes structural disadvantage
- R2 isolates the selection hypothesis: within each length stratum, which paths are
  most evidence-supported? No length penalty inside the bucket.

**Why R1/R3 for B1/B2?**
- B1 (R1) = current operational baseline before any ranking improvement
- B2 (R3) = current tentative standard; direct comparison point for P6-A
- Using R2 for both T1 and B would make T1 vs B1/B2 confounded by ranker change;
  keeping B1=R1 and B2=R3 preserves the comparison to the established standards

---

## 4. Bucket Configuration (pre-fixed, immutable after registration)

**Total: top-70**

| Stratum | Path length | Quota | Available (of 715 total) |
|---------|-------------|-------|--------------------------|
| L2 | 2 | 35 | 208 |
| L3 | 3 | 25 | 245 |
| L4+ | ≥4 | 10 | 262 (173 L4 + 89 L5) |

**Quota shortfall protocol** (if a stratum has fewer candidates than quota):
- Take all available candidates from that stratum
- Redistribute remaining slots to the next-lower stratum (L3 absorbs L4+ shortfall, L2 absorbs L3 shortfall)
- Document any redistribution in results; do not silently fill from other strata

With 208 L2, 245 L3, 262 L4+ available, no shortfall is expected.

**Selection within each stratum**: R2 (evidence-only = e_score_min descending).
No tiebreaking by path_length or weight within a stratum.

---

## 5. Primary Outcome

**Investigability rate** = fraction of top-70 hypotheses with PubMed 2024-2025 support.

Pre-specified success criteria:
- **Strong success**: T1_inv > B2_inv AND T1_inv > B1_inv AND novelty_retention ≥ 0.90
- **Weak success**: T1_inv > B1_inv AND T1_inv ≈ B2_inv (±2pp) AND novelty_retention ≥ 0.90
- **Structure confirmed**: T1_inv ≤ B2_inv → global R3 not improvable by bucketing alone
- **Fail**: T1_inv ≤ B1_inv (bucketing actively hurts vs. even the naive baseline)

---

## 6. Four Required Metrics

### 6.1 Investigability
`investigability_rate = N_investigated / 70`
Threshold: > 0.893 (B2 reference from run_035 N=140)

### 6.2 Novelty retention
`novelty_retention = mean_cross_domain_ratio_T1 / mean_cross_domain_ratio_B2`
Threshold: ≥ 0.90 (hard constraint per P6 spec)

### 6.3 Support rate / validation hit rate
`support_rate = N_investigated / 70` (same as investigability for overall;
  broken out per stratum for L2/L3/L4+ to show which paths contribute)

### 6.4 Long-path share
`long_path_share = N_paths_with_length_≥3 / 70`
Hypothesis: T1 >> B1 ≈ B2 (structural advantage confirmed if T1 long_path_share > B2 by ≥30%)
This is the mechanistic test — if bucketing works, longer paths appear in top-70.

---

## 7. Statistical Analysis

- Fisher's exact test (two-tailed): T1 vs B2, T1 vs B1, B2 vs B1
- Effect size: Cohen's h
- Significance: α = 0.05 (indicative; N=70 has ~30% power for h=0.21)
- Secondary: stratum-level investigability (L2, L3, L4+ separately)

---

## 8. Evidence and Validation Windows

- Evidence features: PubMed co-occurrence ≤2023 (no leakage)
- Validation: PubMed 2024-2025 (disjoint window)
- Evidence cache: reuse from run_035 (526 entries) + any new L4/L5 path edges

---

## 9. What This Run Does NOT Do

- Does NOT add augmentation edges
- Does NOT change the KG
- Does NOT modify ranking functions (R1, R2, R3 used as-is)
- Does NOT add a domain-aware or operator-aware bucketing layer
- Does NOT change N from the established top-70 standard
