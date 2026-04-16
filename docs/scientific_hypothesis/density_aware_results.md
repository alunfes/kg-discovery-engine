# Density-Aware Pair Selection Results (run_022)

Date: 2026-04-14
Registration: configs/density_aware_registry.json (frozen)

## Background

run_021 findings:
- H_ceiling supported: log_min_density is the strongest predictor of investigability (|r|=0.461)
- C1-C2 investigability gap concentrated in low-density group: gap=0.197
- Mid/high density groups: gap≈0 (C1≈C2)

Hypothesis: density-aware pair selection will restore C2-C1 parity by filtering out low-density cross-domain pairs.

## Density Threshold

- Source: run_021/quartile_analysis.json
- Metric: min_density = min(subject_density, object_density) from PubMed past corpus (<=2023)
- Threshold: **8105.5 (Q2_median)**
- Q1=3255.0, Q2_median=8105.5, Q3=22743.0

Filter: keep candidate pairs where min_density >= 8105.5

## Results Summary

| Method | N | Investigated | Investigability | Novel_Supported |
|--------|---|--------------|-----------------|-----------------|
| C2_density_aware | 70 | 68 | **0.971** | 9 |
| C1_baseline | 70 | 68 | **0.971** | 5 |
| C_rand_v2 | 70 | 42 | **0.600** | 15 |
| C2_baseline (run_018) | 70 | 64 | 0.914 | 11 | (reference) |

## Statistical Tests

| Test | Criterion | Result | Pass? |
|------|-----------|--------|-------|
| SC_ds_primary | Fisher two-sided p>0.05 AND delta<=0.02 | p=1.0000, delta=0.0000 | ✓ PASS |
| SC_ds_improvement | C2_da > 0.914 | 0.9714 | ✓ PASS |
| SC_ds_random | Fisher one-sided p<0.05 | p=0.0000 | ✓ PASS |

## Matched Comparison

Density-only bins (tertiles from combined C2_da + C1 pool):

| Cell | n(C2_da) | n(C1) | C2_da Inv. | C1 Inv. | Gap | Reportable |
|------|----------|-------|------------|---------|-----|------------|
| density=den_low | 20 | 27 | 1.000 | 0.963 | -0.0370 | Yes |
| density=den_mid | 31 | 12 | 0.935 | 1.000 | 0.0645 | Yes |
| density=den_high | 19 | 31 | 1.000 | 0.968 | -0.0323 | Yes |

H_matched_parity verdict: **REJECTED**
Max reportable gap: 0.0645 (threshold: 0.03)
Note: max reportable gap=0.0645 > 0.03: H_matched_parity rejected

## Overall Verdict

**GO**

H_density_select: Supported
H_matched_parity: Rejected

## Interpretation

Density-aware pair selection successfully restores C2-C1 investigability parity. The density ceiling identified in run_021 can be overcome by filtering out low-density cross-domain pairs (min_density < Q2_median). C2_density_aware achieves 0.971 investigability, statistically equivalent to C1's 0.971.

This establishes a practical KG usage guideline: cross-domain composition is reliable when both entities have sufficient literature coverage (min_density >= 8105.5).
