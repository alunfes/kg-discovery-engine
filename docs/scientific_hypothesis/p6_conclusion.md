# P6 Conclusion: Selection Architecture Redesign
*Completed: 2026-04-14 | Run: run_036 (P6-A)*

---

## 1. Executive Summary

P6 tested whether restructuring the candidate **selection mechanism** — moving from global
top-k to path-length bucketed selection — could break the investigability ceiling that P3–P5
established. The central hypothesis: global top-k structurally excludes long-path candidates
before any evidence ranking can evaluate them.

**Result: Mechanistic hypothesis confirmed. Practical ceiling not broken.**

- Long-path exclusion was real and correctable by bucketing (0% → 50% long-path share).
- However, even with diverse path lengths in the selection, investigability did not exceed B2.
- The ceiling is not in the selection policy. It is in the **KG's cross-domain path geometry**.

---

## 2. P6-A Results (run_036)

### Conditions

| Condition | Description | Inv Rate | Novelty Ret | Long-path | Decision |
|-----------|-------------|----------|-------------|-----------|----------|
| B1 | Global R1 top-70 | 0.886 | 1.000 | 0% | Baseline |
| B2 | Global R3 top-70 | 0.943 | 1.000 | 0% | Tentative standard |
| T1 | 3-bucket: L2=35, L3=25, L4+=10 (pre-registered) | 0.943 | 0.808 ✗ | 50% | STRUCTURE_CONFIRMED_NOVELTY_FAIL |
| **T2** | **2-bucket: L2=50, L3=20 (exploratory)** | **0.929** | **0.905 ✓** | **29%** | **WEAK_SUCCESS** |

### Key Measurements

- **L4+ paths are investigable**: stratum inv = 1.0 (10/10) — these paths reach recent literature.
- **L3 paths**: stratum inv = 0.85–0.88, well above R1 baseline.
- **B2 already reaches B2_inv**: R3's evidence weighting implicitly compensates within L2-dominated pool.

---

## 3. Mechanistic Finding: Structural Exclusion Confirmed

**Finding**: global top-k by (path_length ASC, weight DESC) places all L3/L4+ candidates
below position ~300 in the sort order. With pool sizes of 200–400 used in prior runs
(run_033, run_035), **zero L4+ candidates entered the pool**.

> T1 long_path_share = 50% (35/70 paths are L3/L4+) vs B2 = 0%

This directly confirms P3-A's original diagnosis: selection architecture, not candidate
quality, is the bottleneck.

However, **correcting the structural exclusion did not raise investigability**:

> T1_inv = B2_inv = 0.943. Bucketing changed composition, not rate.

The reason: candidates displaced from the L2 stratum were already investigated. Replacing
investigated L2 paths with investigated L3/L4+ paths yields no net change.

---

## 4. Geometry Ceiling: The Mathematical Constraint

The binding constraint is not selection policy. It is the **cross-domain edge density of the
current KG**.

### The novelty constraint

Each edge in a path contributes either a cross-domain transition (1) or a same-domain
transition (0) to `cross_domain_ratio`. Paths of different lengths have different ratios:

```
L2 paths: cross_domain_ratio = 0.500  (exactly 1 cross-domain edge / 2 total edges)
L3 paths: cross_domain_ratio = 0.333  (1/3 — one cross-domain edge in 3)
L4 paths: cross_domain_ratio = 0.250  (1/4)
```

The novelty constraint `novelty_retention ≥ 0.90` requires:

```
mean_cross_domain_ratio(selected) ≥ 0.90 × B2_mean_cd
                                  ≥ 0.90 × 0.500 = 0.450
```

Maximum L3 quota compatible with this constraint:

```
(50 × 0.500 + L3 × 0.333) / 70 ≥ 0.450
L3 × 0.333 ≥ 0.450 × 70 − 50 × 0.500
L3 ≤ (31.5 − 25.0) / 0.333 = 19.5 → L3_max = 20
```

> **L3 inclusion is capped at 20 by geometry, not by evidence or selection policy.**

L4+ inclusion is infeasible under the novelty constraint: even 1 L4 slot at cross_domain_ratio
= 0.250 pulls the mean below threshold when combined with 20 L3 slots.

### KG candidate space saturation

```
Total cross-domain candidates:  715
  L2: ~300    L3: ~100    L4: ~262    L5: ~53
Unique (subject, object) pairs:  ~90
```

With only ~90 distinct endpoint pairs, any selection of N=70 must draw from a pool where
diversity is structurally bounded. The geometry — not the ranker — determines what novel
discoveries are possible.

---

## 5. P6-B and P6-C Assessment

### P6-B: Augmentation Lane (Architecture C from p6_selection_architecture.md)

Would reserve 15 slots for augmented paths selected separately from original paths.

**Why this is not the primary path forward:**

- run_032 (Policy B): already tested reserved augmented slots. Augmented paths filled the
  lane but did not improve investigability. Result: FAIL.
- The augmentation lane is still subject to the same novelty constraint: each augmented
  L3+ path has cross_domain_ratio ≤ 0.333, so augmented lane size is bounded by the
  same mathematics.
- Evidence gating (P5) improved edge quality but not investigability. Adding R3 ranking
  within the augmented lane addresses ranking but not geometry.

**Conclusion**: P6-B could be tested for completeness but is **not expected to break the
ceiling**. It operates within the same KG geometry.

### P6-C: Depth-Normalized Reranking (Architecture B)

Would replace `1/path_length` structural term with `e_score_min / log2(path_length + 1)`.

**Why this is not the primary path forward:**

- T1 already achieved the same investigability as B2 with 50% long paths included.
  The gap is not in ranking within the pool; it's in the underlying pool geometry.
- Depth normalisation changes which candidates enter the pool but not the underlying
  cross_domain_ratio distribution of L3/L4 candidates.
- The mathematical ceiling derived in §4 applies regardless of ranking function.

**Conclusion**: P6-C is an interesting algorithmic variant but **does not address the
geometric constraint**. The L3_max = 20 bound holds under any ranking.

---

## 6. Final Conclusion: Selection Alone Is Insufficient

The P6 programme has established the following causal chain:

```
P3-A/B: shortest-path selection structurally excludes longer paths
         ↓
P5:     evidence gating improves edge quality but doesn't change selection geometry
         ↓
P6-A:   bucketed selection removes the structural exclusion → confirmed mechanistically
         ↓
P6-A:   but investigability ceiling remains → geometry is the constraint, not selection
         ↓
P6-B/C: within-KG fixes (augmentation lane, depth normalisation) cannot expand geometry
         ↓
P7:     KG expansion is the required intervention
```

> **Reranking and selection architecture improvements alone cannot improve investigability
> beyond the 89–94% range observable in the current 200-node KG.**

The reason is structural: the current KG has ~90 unique endpoint pairs. Once the top-70
selection captures the most investigable endpoint pairs, there is no room for further
improvement through selection or ranking policy.

**The cross-domain edge density of the KG itself must increase.**

---

## 7. Open Questions for P7

| Question | Measurable Target |
|----------|-------------------|
| Does KG expansion increase unique endpoint pairs? | ≥ 200 unique (subject, object) pairs (vs current ~90) |
| Does cross-domain density increase with more nodes? | L3 cross_domain_ratio > 0.400 (vs current 0.333) |
| Does expanded KG break the inv ceiling under T2? | inv > 0.943 at N=70 with T2 selection |
| Is the novelty constraint relaxed by expanded KG? | novelty_retention ≥ 0.90 with L3_quota > 20 |

---

## 8. Recommended Standard for P7

Based on P6-A T2 WEAK_SUCCESS, the **recommended pipeline for P7** is:

- **Selection**: T2 bucketed (L2=50, L3=20), no L4+ slots
- **Ranker**: TBD by run_037 (R2 vs R3 within buckets)
- **Evidence window**: ≤2023 | Validation: 2024–2025
- **Novelty constraint**: cross_domain_ratio ≥ 0.450 (retention ≥ 0.90)

---

## Artifacts

| File | Description |
|------|-------------|
| `runs/run_036_p6a_bucketed/` | Full P6-A run artifacts |
| `runs/run_036_p6a_bucketed/decision.json` | Pre-registered + exploratory outcomes |
| `runs/run_036_p6a_bucketed/metrics_by_condition.json` | 4 metrics × 4 conditions |
| `docs/scientific_hypothesis/p6_selection_architecture.md` | Design rationale (pre-run) |
| `docs/scientific_hypothesis/p7_preregistration.md` | Next phase pre-registration |
