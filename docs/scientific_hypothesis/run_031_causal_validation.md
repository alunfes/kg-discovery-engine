# run_031_causal_validation — P3-A Causal Isolation Results

**Date**: 2026-04-14  
**Phase**: P3-A  
**Experiment**: 4-condition 2×2 factorial causal isolation

---

## Objective

Determine whether P3-A improvements are explained by:
1. Density floor alone (filter effect)
2. KG augmentation alone (augmentation effect)
3. Their combination (interaction)

---

## Setup

| Parameter | Value |
|-----------|-------|
| Seed | 42 |
| tau_floor | 3500 |
| Target N per condition | 70 |
| KG original | bio_chem_kg_full.json (200 nodes, 325 edges) |
| KG augmented | bio_chem_kg_augmented.json (200 nodes, 335 edges, +10 edges) |
| PubMed validation window | 2024-01-01 – 2025-12-31 |

### Augmented KG (+10 edges)

| Source | Relation | Target | Weight |
|--------|----------|--------|--------|
| chem:mechanism:mtor_inhibition | activates | bio:pathway:ampk_pathway | 0.75 |
| chem:drug:sildenafil | activates | bio:pathway:ampk_pathway | 0.60 |
| bio:pathway:ampk_pathway | may_treat | bio:disease:huntingtons | 0.60 |
| chem:target:vegfr_target | targeted_in | bio:disease:glioblastoma | 0.75 |
| chem:mechanism:hdac_inhibition | may_treat | bio:disease:huntingtons | 0.65 |
| bio:pathway:pi3k_akt | promotes | bio:process:tumor_angiogenesis | 0.80 |
| chem:drug:lithium_carbonate | may_treat | bio:disease:huntingtons | 0.60 |
| bio:pathway:autophagy | reduces | bio:disease:huntingtons | 0.75 |
| chem:mechanism:nrf2_activation | modulates | bio:process:tumor_angiogenesis | 0.55 |
| chem:drug:metformin | may_treat | bio:disease:huntingtons | 0.50 |

---

## Results

### Condition Metrics

| Condition | N | N Retained | N Excluded | Inv Rate | Fail Rate |
|-----------|---|-----------|-----------|----------|-----------|
| A (Orig KG, no floor) | 70 | 70 | 0 | 0.914 | 0.086 |
| B (Orig KG + floor) | 52 | 52 | 18 | 0.923 | 0.077 |
| C (Aug KG, no floor) | 70 | 70 | 0 | 0.914 | 0.086 |
| D (Aug KG + floor) | 52 | 52 | 18 | 0.923 | 0.077 |
| C1_original | 70 | 70 | 0 | 0.857 | 0.143 |
| C1_augmented | 70 | 70 | 0 | 0.857 | 0.143 |

### Attribution Decomposition

| Effect | Formula | Value |
|--------|---------|-------|
| Filter effect | B − A | +0.0088 |
| Augmentation effect | C − A | **0.0000** |
| Interaction | D − C − B + A | **0.0000** |
| Combined gain | D − A | +0.0088 |

### Statistical Tests

| Comparison | p-value | Significance | Cohen's h | Effect |
|------------|---------|-------------|-----------|--------|
| Filter effect (B vs A) | 1.000 | ns | 0.032 | small |
| Aug effect (C vs A) | 1.000 | ns | 0.000 | — |
| Combined (D vs A) | 1.000 | ns | 0.032 | small |
| C1 aug vs C1 orig | 1.000 | ns | 0.000 | — |

### Density Floor Exclusion

- Condition B: 18/70 (25.7%) excluded below tau_floor=3500
- Condition D: 18/70 (25.7%) excluded (same pairs as B)
- Mean excluded density: below 3500 by definition

### Mechanism Check

| Metric | Value |
|--------|-------|
| Common hypothesis pairs (A ∩ C) | 70 / 70 (100%) |
| New hypotheses in C not in A | 0 |
| A-failures that became C-successes | 0 |
| Aug edge contributed to path | 0 |

---

## Key Finding

**The augmented KG generates identical top-70 hypotheses as the original KG.**

The 10 new edges create longer/lower-weight paths that rank below the top-70 cutoff under the current compose_cross_domain pipeline (shortest-path-first selection). As a result:
- C = A identically (same (subject, object) pairs)
- D = B identically (same pairs after filtering)
- Augmentation effect = 0.000 by construction

---

## Density Band Analysis (A condition)

| Band | N | Inv Rate | Fail Rate |
|------|---|---------|----------|
| strict Q1 (≤4975) | 28 | 0.821 | 0.179 |
| expanded low (≤7635) | 38 | 0.842 | 0.158 |
| threshold adjacent (2800-4200) | 12 | 0.833 | 0.167 |
| above floor (≥3500) | 52 | 0.923 | 0.077 |

The density floor does isolate a higher-failure-rate subpopulation: above-floor investigability (92.3%) vs Q1 (82.1%), confirming the density-quality correlation from run_021.

---

## Final Decision: **C**

> Combination appears promising, but current evidence remains preliminary due to sample size and confounding.

**Evidence strength**: weak  
**Primary blocker**: Augmentation effect = 0.000 because current pipeline selection (shortest path, top-70) does not reach the new augmented paths. A revised selection policy (e.g., diversity-aware or augmented-path-priority) is required to test the augmentation hypothesis properly.

---

## Limitations

1. **Selection bias in pipeline**: The top-N shortest-path selection causes augmented KG to produce identical results. The new edges add *structural connectivity* but not within the top-70 priority range.
2. **Small sample sizes**: N=52 for filtered conditions; N=6 failures in A. All statistical tests are severely underpowered.
3. **PubMed proxy**: investigability (2024-2025 papers) ≠ scientific validity; recent work may be unpublished.
4. **Run_031 ≠ run_018 pool**: These are new hypotheses generated from bio_chem_kg_full.json, not the original run_018 corpus. Direct comparisons to prior failure rates require caution.

---

## Next Steps (P3-B)

1. **Augmented-path-priority selection**: Prefer paths that traverse new augmentation edges over purely shortest-path selection
2. **Larger N**: Generate N=150+ per condition to achieve statistical power
3. **Run_021 pool retest**: Apply conditions B/D to the original run_018 (C2) hypothesis pool to isolate filter effect on known failures
4. **Incremental augmentation**: Test 5-edge vs 10-edge vs 20-edge augmentation to find inflection point
