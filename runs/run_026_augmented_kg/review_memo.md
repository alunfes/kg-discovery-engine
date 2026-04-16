# P3-A Augmented KG Experiment — Review Memo

**Date**: 2026-04-14
**Run**: run_026_augmented_kg
**Phase**: P3-A KG Densification

## Summary

- **Status**: SUCCESS
- **Investigability**: 98.5% (ref C2: 97.1%)
- **Q1 failure rate**: 0.0% (target: ≤20%, ref C2: 38.46%)
- **Rate reduction**: +38.5%

## KG Augmentation

- Added 10 edges to bio_chem_kg_augmented.json
- Key fixes:
  - bio:pathway:ampk_pathway degree: 3 → 6 (added autophagy, oxidative_stress, neuroinflammation)
  - bio:process:tumor_angiogenesis degree: 2 → 5 (added pi3k_akt, lung_cancer, colon_cancer)
  - Restored bridge: valproic_acid → hdac_inhibition → epigenetic_silencing
  - Added: pde5_inhibition → ampk_pathway (Sildenafil path enrichment)

## Hypothesis Pool

- 70 existing C2 from run_021 + 12 new augmented hypotheses
- After tau_floor=3500: 68 candidates
- Selected: 68 (target=70)
- Augmented-path hypotheses in selection: 10

## Q1 Analysis

- Q1 total (min_density ≤ 4594): 5
- Q1 failures: 0
- Q1 failure rate: 0.0%

## Key Insight

KG densification + density-aware selection (tau_floor=3500) together
address both structural (KG degree) and statistical (PubMed density) causes
of Q1 failure. The augmented paths enabled new hypothesis pairs through
enriched AMPK pathway and tumor angiogenesis nodes.

## Next Steps

- P3-B: density decomposition — topology analysis vs investigability
- Structural: KG expansion to 300+ nodes (DrugBank/UniProt integration)
- Evaluation: Run C1_augmented baseline for fair comparison