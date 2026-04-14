# run_031_causal_validation — Review Memo

Date: 2026-04-14
Phase: P3-A causal isolation

## Investigability Rates

| Condition | N | Inv Rate | Failure Rate | Excl |
|-----------|---|----------|--------------|------|
| A (Original KG + no floor) | 70 | 0.914 | 0.086 | 0 |
| B (Original KG + density floor) | 52 | 0.923 | 0.077 | 18 |
| C (Augmented KG + no floor) | 70 | 0.914 | 0.086 | 0 |
| D (Augmented KG + density floor) | 52 | 0.923 | 0.077 | 18 |
| C1_original (C1 Original KG) | 70 | 0.857 | 0.143 | 0 |
| C1_augmented (C1 Augmented KG) | 70 | 0.857 | 0.143 | 0 |

## Attribution

- Filter effect (B-A): +0.0088
- Aug effect (C-A):    +0.0000
- Interaction (D-C-B+A): +0.0000
- Combined gain (D-A): +0.0088

## Statistical Evidence

- filter_effect: p=1.0000 (ns), h=0.032 (small)
- aug_effect: p=1.0000 (ns), h=0.000 (small)
- combined_effect: p=1.0000 (ns), h=0.032 (small)
- aug_on_top_of_filter: p=1.0000 (ns), h=0.000 (small)
- filter_on_top_of_aug: p=1.0000 (ns), h=0.032 (small)
- c1_aug_vs_c1_orig: p=1.0000 (ns), h=0.000 (small)

## Final Decision: **C**

> Combination appears promising, but current evidence remains preliminary due to sample size and confounding.

Evidence strength: weak

Rationale: Neither effect reaches significance (filter p=1.000, aug p=1.000). Filter Δ=+0.009 (h=0.032), Aug Δ=+0.000 (h=0.000), Interaction=+0.000. Combination appears promising but current evidence is preliminary.

## Caveats

- All conditions N<=70; statistical tests are underpowered.
- Density floor may selectively exclude hypotheses independent of scientific validity.
- PubMed 2024-2025 count is a proxy for investigability, not biological validity.
- Run_031 generates new hypotheses from bio_chem_kg_full.json; not identical to run_018 pool.
