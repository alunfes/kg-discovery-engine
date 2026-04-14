# run_035 review memo — R3 Confirmatory Replication (N=140)
Generated: 2026-04-14T11:56:51.229542

## Setup
- KG: bio_chem_kg_full.json (325 edges, no augmentation)
- Pool: top-400 candidates, selection: top-140
- Evidence window: ≤2023 | Validation window: 2024-2025
- Primary comparison: R3 vs R1 (confirmatory)

## Results

| Ranking | N | Inv Rate | Fail Rate | Δ vs R1 | Cohen's h | p-value | Sig |
|---------|---|----------|-----------|---------|-----------|---------|-----|
| R1_baseline | 140 | 0.8643 | 0.1357 | — | — | — | — |
| R2_evidence_only | 140 | 0.9143 | 0.0857 | +0.0500 | +0.1603 | 0.2529 | no |
| R3_struct_evidence ← primary | 140 | 0.8929 | 0.1071 | +0.0286 | +0.0877 | 0.5836 | no |
| R4_full_hybrid | 140 | 0.8929 | 0.1071 | +0.0286 | +0.0877 | 0.5836 | no |
| R5_conservative | 140 | 0.9000 | 0.1000 | +0.0357 | +0.1110 | 0.4589 | no |

## Decision: [UNDERPOWERED]

**R3 same direction but underpowered: Δ=+0.0286, p=0.5836 ≥ 0.05**

### Interpretation

**Pool dilution effect**: run_033 used pool-200 / top-70; run_035 uses pool-400 / top-140.
The additional 201–400 candidates are longer, lower-weight paths with systematically
lower investigability. This dilutes all rankings:
- R1 baseline: 0.886 (N=70, pool-200) → 0.864 (N=140, pool-400)
- R3: 0.943 → 0.893 | effect Δ: +5.7pp → +2.9pp

The effect size halved, but direction is preserved. Two interpretations:

1. **R3 advantage is real but pool-dependent**: Evidence ranking helps most when
   the pool consists of similar-length (2-hop) paths; longer paths dilute the signal.
2. **P4 finding was partially driven by the specific pool-200 composition**:
   The top-200 candidates have higher base investigability, making evidence ranking
   more impactful as a tiebreaker.

**R2 now leads numerically** (0.914, Δ=+0.050) but also underpowered (p=0.253).
R2 vs R3 remains unresolved at this N.

### Key numbers for planning
- To detect h=0.088 (observed R3 effect at N=140) at power=80%, α=0.05: **N ≈ 1,000**
- To detect h=0.160 (R2 effect) at power=80%: **N ≈ 310**
- Current KG has 715 total candidates → hard ceiling; pool-400 already covers 56% of space
- Larger N would require KG expansion (more nodes/edges) before further confirmatory work

### Decision for R3 status
R3 remains **tentative standard** (unchanged from P4). Not promoted to confirmed.
Evidence ranking shows consistent positive direction across N=70 and N=140 but
effect size is smaller than initially observed. This is typical of regression to
the mean in small-N preliminary experiments.

**Augmentation should NOT be revisited before KG expansion**: P3, P4, P5 all show
that the current 715-candidate space is near-saturated for this KG.

## Artifacts
- ranking_comparison.json — 5 rankings × metrics
- statistical_tests.json — Fisher tests vs R1
- decision.json — pre-registered outcome
- top140_*.json — ranked selections per ranking
- run_config.json — experiment config
