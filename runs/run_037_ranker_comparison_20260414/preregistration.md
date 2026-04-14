# run_037 Pre-registration: T2 × Ranker Comparison (R2 vs R3)
*Registered: 2026-04-14 | IMMUTABLE after execution begins*

---

## 1. Research Question

Within the T2 bucketed selection (L2=50, L3=20), does the choice of within-bucket ranker
— R2 (evidence-only) vs R3 (structure 40% + evidence 60%) — affect investigability or
novelty retention?

**Purpose**: Determine the default ranker for P7. P6-A (run_036) used R2 within buckets.
We want to know if R3 — which performed equally to R2 at the global level (run_033) —
also performs equivalently within the T2 bucket structure.

---

## 2. Design

### Conditions

| Label | Selection | Ranker within buckets |
|-------|-----------|----------------------|
| B2_global | Global top-70 (no buckets) | R3 (current standard) |
| T2×R2 | 2-bucket: L2=50, L3=20 | R2 (evidence-only) |
| T2×R3 | 2-bucket: L2=50, L3=20 | R3 (struct 40% + evidence 60%) |

**Note**: B2_global and T2×R2 are already computed in run_036. T2×R3 is new.
Results will be read directly from run_036 artifacts for B2 and T2×R2 conditions.

### Fixed parameters (identical to run_036)

- KG: `src/scientific_hypothesis/bio_chem_kg_full.json` (200 nodes, 325 edges)
- N = 70 (final selection size)
- Seed = 42
- Evidence window: ≤ 2023/12/31
- Validation window: 2024/01/01 – 2025/12/31
- Evidence cache: reused from `runs/run_036_p6a_bucketed/evidence_cache.json`
- PubMed cache: reused from `runs/run_036_p6a_bucketed/pubmed_cache.json`

### Why R3 within a bucket may differ from R2

R3 formula: `score = 0.4 × norm(1/path_length) + 0.6 × norm(e_score_min)`

Within a stratum where all candidates share the same path_length, the structural term
`norm(1/path_length)` becomes a constant and collapses to `0.5` for all candidates.
Therefore within a pure L2 or pure L3 bucket:

```
R3_within_bucket = 0.4 × 0.5 + 0.6 × norm(e_score_min) = 0.20 + 0.6 × norm(e)
```

This is **monotonically equivalent to R2** within a pure stratum — same ranking order.
The experiment tests whether any boundary effects (tie-breaking, normalisation edge cases)
produce observably different selections.

**Pre-registered prediction**: T2×R3 ≈ T2×R2 (within ±1pp investigability, same
novelty_retention within ±0.02). If confirmed, either ranker is acceptable for P7.

---

## 3. Primary Metrics

| Metric | Definition | Threshold for equivalence |
|--------|-----------|--------------------------|
| Investigability | Fraction of top-70 with PubMed 2024-2025 ≥ 1 paper | |Δ(T2×R3 − T2×R2)| ≤ 0.014 (≤ 1/70) |
| Novelty retention | mean_cross_domain_ratio / B2_baseline_cd | |Δ| ≤ 0.02 |

**Note**: No new statistical hypothesis testing. This is a descriptive comparison.
The question is practical equivalence for P7 default ranker selection.

---

## 4. Success Criteria

**Equivalence (expected)**: |Δ_inv| ≤ 0.014 AND |Δ_novelty| ≤ 0.02
→ Either ranker acceptable. **Choose R3 for P7** (maintains consistency with global standard).

**Divergence (unexpected)**: |Δ_inv| > 0.014 OR |Δ_novelty| > 0.02
→ Investigate which ranker is better. Choose whichever produces higher investigability.

---

## 5. Outputs

- `metrics_t2r3.json` — T2×R3 metrics (investigability, novelty, per-stratum)
- `top70_T2R3.json` — selected 70 candidates
- `run_config.json` — experiment configuration
- `review_memo.md` — decision and interpretation

---

## 6. Precedence

This experiment does NOT re-run or modify B2_global or T2×R2 results. Those are
already recorded in run_036 and are read-only here. Only T2×R3 is newly computed.
