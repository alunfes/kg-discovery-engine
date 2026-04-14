# run_037 Pre-registration: T2×R2 vs T2×R3 Ranker Comparison
*Registered: 2026-04-14 — before any feature extraction or validation API calls*

---

## 1. Purpose

Determine the **default ranker for P7** by comparing R2 (evidence-only) and R3
(struct 40% + evidence 60%) within the T2 bucket structure (L2=50, L3=20, L4+=0).

This is a ranker comparison, not a new selection architecture. T2 buckets are fixed
from run_036 (post-hoc T2 WEAK_SUCCESS result).

---

## 2. Mathematical Pre-Registered Prediction

**Prediction: T2×R2_inv = T2×R3_inv (identical results)**

Rationale: Within a homogeneous path-length stratum, R3's structural term is constant:

```
R3 score = 0.4 × norm(1/path_length) + 0.6 × norm(e_score_min)
         = 0.4 × C_stratum + 0.6 × norm(e_score_min)
```

Where `C_stratum` = `norm_all(1/path_length)` is the same constant for ALL candidates
within a stratum (since they all have the same path_length). Therefore:

- Within L2 stratum (all path_length=2): rank by R3 ≡ rank by R2 (evidence only)
- Within L3 stratum (all path_length=3): rank by R3 ≡ rank by R2 (evidence only)

This is a mathematical identity, not an empirical claim. Verifying it empirically
confirms that the bucket implementation correctly enforces path_length homogeneity.

**Implication for P7**: For P7's L4+ bucket (containing mixed path_length=4 and 5),
R2 ≠ R3 (different structural terms per candidate). A separate P7-internal comparison
will be needed to determine which ranker is better for the heterogeneous L4+ stratum.

---

## 3. Conditions

| Label | Bucket Structure | Within-bucket Ranker | Description |
|-------|-----------------|---------------------|-------------|
| **T2_R2** | L2=50, L3=20, L4+=0 | R2 (e_score_min DESC) | Evidence-only (current T2) |
| **T2_R3** | L2=50, L3=20, L4+=0 | R3 (0.4×struct + 0.6×evid) | Structure+evidence |

All other parameters identical to run_036 T2.

---

## 4. Hypotheses

**H_null (pre-registered)**: T2_R2_inv = T2_R3_inv
  (Mathematical equivalence within homogeneous strata; expected outcome)

**H_alt (would falsify our analysis)**: T2_R2_inv ≠ T2_R3_inv
  (Would indicate a bug in implementation OR non-integer path lengths OR
   different normalization scope — any of these requires investigation)

---

## 5. Primary Outcome

- **Investigability rate**: N_investigated / 70 for each condition
- **Novelty retention**: mean_cross_domain_ratio / B2_baseline (0.50)
- **Selection overlap**: Jaccard(T2_R2_candidates, T2_R3_candidates) — expected = 1.0

Secondary: if T2_R2 ≠ T2_R3, inspect which candidates differ and why.

---

## 6. Decision

| Result | Decision |
|--------|----------|
| T2_R2 = T2_R3 (H_null confirmed) | Use R2 for P7 (simpler, equivalent to R3 in homogeneous strata) |
| T2_R2 ≠ T2_R3 (H_alt) | Investigate the discrepancy; do not proceed to P7 until resolved |

**Why R2 if equal**: R2 is simpler (no structural term to normalize), more interpretable
(pure evidence signal), and sufficient. If R2 = R3 within homogeneous strata, there is no
reason to use the more complex R3.

**For P7's L4+ stratum**: Pre-specify that R3 will be tested separately within the L4+
bucket, since path_length 4 and 5 co-exist and the structural term will differ.

---

## 7. Caches

- Evidence: reuse run_036 evidence_cache.json (695 entries, full 715-candidate coverage)
- Pubmed: reuse run_036 pubmed_cache.json (343 entries)
- No new API calls expected

---

## 8. What This Run Does NOT Do

- Does NOT change the bucket structure (T2 fixed from run_036)
- Does NOT evaluate L4+ paths (T2 has L4+=0)
- Does NOT change N from top-70
- Does NOT constitute a new architecture test
