# run_034 review memo — P5 Evidence-Gated KG Augmentation
Generated: 2026-04-14T11:24:52.703101

## Setup
- Evidence window: ≤2023 (gate + feature extraction)
- Validation window: 2024-2025
- Ranking: R3 (Struct 40% + Evidence 60%)
- Pool: top-200, selection: top-70

## WS1: Evidence Gate Results

| Source | Target | e_score | pop_adj | first_seen | Pass |
|--------|--------|---------|---------|------------|------|
| mtor_inhibition | ampk_pathway | 1.000 | 0.0045 | 2023 | ✓ |
| vegfr_target | glioblastoma | 2.288 | 0.0086 | 2010 | ✓ |
| hdac_inhibition | huntingtons | 1.146 | 0.0027 | 2010 | ✓ |
| pi3k_akt | tumor_angiogenesis | 1.643 | 0.0038 | 2010 | ✓ |
| autophagy | huntingtons | 2.715 | 0.0144 | 2010 | ✓ |
| sildenafil | ampk_pathway | 0.301 | 0.0002 | 2023 | ✗ |
| ampk_pathway | huntingtons | 0.602 | 0.0006 | 2023 | ✗ |
| lithium_carbonate | huntingtons | 0.477 | 0.0002 | 2010 | ✗ |
| nrf2_activation | tumor_angiogenesis | 0.000 | 0.0000 | 2023 | ✗ |
| metformin | huntingtons | 1.342 | 0.0010 | 2010 | ✗ |

**Gate PASS: 5 / 10 edges**

## Results: Investigability by Condition

| Condition | Description | Inv Rate | Fail Rate | Novelty Ret | Diversity |
|-----------|-------------|----------|-----------|-------------|-----------|
| A | No augmentation | 0.9429 | 0.0571 | 1.0000 | 0.9714 |
| B | Ungated aug | 0.9429 | 0.0571 | 1.0000 | 0.9571 |
| C | Evidence-gated aug | 0.9429 | 0.0571 | 1.0000 | 0.9714 |

## Statistical Tests

| Comparison | Δ | Cohen's h | p-value | Significant |
|------------|---|-----------|---------|-------------|
| C_vs_A | +0.0000 | +0.0000 | 1.0000 | no |
| C_vs_B | +0.0000 | +0.0000 | 1.0000 | no |
| B_vs_A | +0.0000 | +0.0000 | 1.0000 | no |

## Support Rate (augmented-edge paths in top-70)

- Condition B: 1 aug paths in top-70, support rate=1.0
- Condition C: 1 aug paths in top-70, support rate=1.0

## Decision: [FAIL]

**C ≤ B or C ≤ A — evidence gate does not rescue augmentation**

- inv_A=0.9429, inv_B=0.9429, inv_C=0.9429
- Δ(C–A)=+0.0000, Δ(C–B)=+0.0000, Δ(B–A)=+0.0000
- Novelty acceptable: True
- Diversity acceptable: True

## Interpretation

### Gate quality
5/10 candidate augmented edges passed the evidence gate, confirming the
pre-registration hypothesis that the original augmented KG contained
literature-sparse edges. The failing edges include nrf2_activation→tumor_angiogenesis
(0 PubMed hits), and metformin→huntingtons which fails on popularity-adjustment
despite 21 raw hits (metformin has 30,821 solo papers — the co-occurrence is
incidental). The gate correctly distinguished biologically specific from
spurious co-occurrences.

### Why A = B = C (the structural dominance problem)
All three conditions produced identical investigability (0.943), identical to
run_033 R3. The decisive finding from augmented-path counts:
- B selected only 1 augmented-edge path in top-70 (out of 884 candidates)
- C selected only 1 augmented-edge path in top-70 (out of 835 candidates)

The 2-hop original KG paths dominate R3 selection even after evidence weighting.
Augmented edges open new paths but those paths are typically longer (≥3 hops),
and R3's structural component (40% × 1/path_length) penalises them enough that
they cannot compete with the dense pool of short original paths.

### Revised P3 diagnosis
P3 concluded "augmented edges are literature-sparse → investigability low."
P5 shows that even **evidence-rich** augmented edges (autophagy→huntingtons
e=2.715, vegfr_target→glioblastoma e=2.288) do not enter the top-70 in
meaningful numbers. The root cause is **selection pressure from 2-hop paths**,
not evidence quality.

Evidence gating is correct hygiene (it ensures what augmentation we do add is
supported), but it does not fix the fundamental problem of structural displacement.

### Support rate insight
The 1 augmented path that reached top-70 in both B and C had support_rate=1.0,
consistent with the gate working as intended. However, n=1 is too small to
draw conclusions about the gate's effect on aug-path quality.

### Diversity
C=A=0.971 > B=0.957. The ungated augmentation (B) slightly hurt diversity by
pushing one marginal path in that shared an endpoint with existing top paths.
Gating to 5 edges recovered baseline diversity.

## Conclusion

**Decision: FAIL** (pre-registered criteria).

Augmentation + evidence gate neither harms nor helps investigability.
The strategy does not improve over the no-augmentation baseline.

### Implication for P6+
The augmentation programme should be suspended as a primary strategy:
- No amount of evidence quality in augmented edges overcomes selection pressure
- Future gains must come from KG structural expansion (more nodes, not more edges)
  or from selection policy changes that explicitly allocate quota to longer paths
- If augmentation is revisited, a **mandatory augmented-path quota** (as tested
  in run_032 Policy B: 15 reserved slots) is the correct mechanism, not evidence gating

### Narrative
Evidence gating worked as intended but was insufficient. The gate correctly
identified which augmented edges have real literature support (5/10 passed).
However, even well-supported augmented paths remain structurally disadvantaged
and are displaced by the abundant 2-hop original paths that dominate the top-200 pool.
The failure mode is structural, not evidential.

## Artifacts
- gate_results.json — per-edge gate scores and pass/fail
- metrics_by_condition.json — 4 metrics × 3 conditions
- statistical_tests.json — pairwise Fisher tests
- decision.json — pre-registered decision outcome
- top70_condition_A/B/C.json — ranked selections
- run_config.json — experiment configuration
- preregistration.md — pre-registered hypotheses and criteria
