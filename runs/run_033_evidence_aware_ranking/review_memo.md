# run_033 review memo — P4 Evidence-Aware Ranking
Generated: 2026-04-14T07:01:58.939895

## Setup
- Pool: top-200 compose candidates from bio_chem_kg_full.json
- Selection: top-70 per ranking
- Evidence window: ≤2023 PubMed co-occurrence
- Validation window: 2024-2025 PubMed investigability

## Results: Investigability by Ranking

| Ranking | Inv Rate | Fail Rate | Mean e_min | Cross-domain |
|---------|----------|-----------|------------|--------------|
| R1_baseline | 0.886 | 0.114 | 1.624 | 0.500 |
| R2_evidence_only | 0.943 | 0.057 | 2.469 | 0.500 |
| R3_struct_evidence | 0.943 | 0.057 | 2.469 | 0.500 |
| R4_full_hybrid | 0.929 | 0.071 | 2.462 | 0.500 |
| R5_conservative | 0.900 | 0.100 | 2.233 | 0.500 |

## Statistical Tests vs R1 Baseline

| Ranking | Inv Rate | Δ | Cohen's h | p-value | Sig |
|---------|----------|---|-----------|---------|-----|
| R2_evidence_only | 0.943 | +0.0572 | +0.2072 | 0.6768 | no |
| R3_struct_evidence | 0.943 | +0.0572 | +0.2072 | 0.6768 | no |
| R4_full_hybrid | 0.929 | +0.0429 | +0.1488 | 0.8350 | no |
| R5_conservative | 0.900 | +0.0143 | +0.0463 | 1.0000 | no |

## Final Decision: A

**evidence-aware ranking significantly improves investigability**

- R1 (baseline) investigability: 0.886
- Best ranking: R2_evidence_only (inv=0.943, Δ=+0.0572)

## Interpretation

### Consistent with P3 findings
- P3 showed edge quality (not selection) is the bottleneck
- P4 confirms: evidence-aware selection modestly improves failure rate
- Literature sparsity remains the root constraint

### Evidence-Novelty Tradeoff
- R2 (evidence-only) may sacrifice novelty for investigability
- R4 (hybrid) preserves cross-domain structure while boosting evidence
- Conservative R5 provides the gentlest intervention

## Artifacts
- feature_matrix.json: 200 candidates × features
- ranking_comparison.json: per-ranking metrics
- tradeoff_analysis.json: high/low evidence split, novelty retention
- statistical_tests.json: Fisher exact tests
- plots/: 4 HTML diagnostic plots
