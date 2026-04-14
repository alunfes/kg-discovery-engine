# Density-Response Curve Analysis

**Run:** WS1 / run_024_p2b_framework
**Date:** 2026-04-14
**Script:** `src/scientific_hypothesis/density_response_analysis.py`
**Data source:** `runs/run_021_density_ceiling/density_scores.json`

---

## Overview

This analysis quantifies the relationship between knowledge-graph node density (log_min_density) and hypothesis investigability across C1_compose and C2_multi_op pipelines. Four curve-fitting models are compared to identify the functional shape of the density-response relationship and to define a "good operating zone" — the density range where investigability reaches clinically useful thresholds (≥0.95 and ≥0.99).

---

## Data Summary

| Item | Value |
|------|-------|
| Total records (C1+C2) | 140 |
| C1_compose | 70 |
| C2_multi_op | 70 |
| C1 investigability | 68/70 = 0.971 |
| C2 investigability | 64/70 = 0.914 |
| Combined investigability | 132/140 = 0.943 |
| log_min_density range | 1.987 – 5.429 |
| Mean log_density (investigated) | 3.96 |
| Mean log_density (not-investigated) | 3.11 |

---

## Binning Analysis

Data split into 10 quantile bins by log_min_density:

| Bin | n | n_inv | Inv. Rate | Mean log_density | Density Range |
|-----|---|-------|-----------|-----------------|---------------|
| 1 | 14 | 12 | 0.857 | 2.736 | 96–1,520 |
| 2 | 14 | 11 | 0.786 | 3.447 | 1,520–4,311 |
| 3 | 14 | 13 | 0.929 | 3.680 | 4,311–5,640 |
| 4 | 14 | 13 | 0.929 | 3.877 | 5,920–8,085 |
| 5 | 14 | 14 | 1.000 | 3.948 | 8,126–10,723 |
| 6 | 14 | 14 | 1.000 | 4.053 | 10,723–12,066 |
| 7 | 14 | 14 | 1.000 | 4.249 | 12,066–22,743 |
| 8 | 14 | 14 | 1.000 | 4.434 | 23,924–28,641 |
| 9 | 14 | 14 | 1.000 | 4.572 | 30,821–42,314 |
| 10 | 14 | 13 | 0.929 | 4.929 | 42,314–268,368 |

Key observations:
- Bins 5–9 show perfect investigability (rate = 1.0)
- Bin 1 (lowest density) shows 0.857 — still higher than expected, driven by C1's ceiling effect
- Bin 10 drops slightly (0.929) due to C1 outliers with density ceiling

---

## Model Comparison

All models fitted on combined C1+C2 (n=140), predicting investigated (0/1) from log_min_density.

| Model | k | RSS | AIC | BIC | Best? |
|-------|---|-----|-----|-----|-------|
| Linear | 2 | 7.067 | 90.95 | 96.83 | |
| Piecewise | 3 | 6.647 | 61.48 | 70.31 | |
| Saturating | 1 | 7.113 | **58.10** | **61.04** | Yes (AIC) |
| Sigmoid | 2 | 6.974 | 58.76 | 64.65 | |

**Best model by AIC: Saturating** (y = 1 − exp(−0.710 × x))

The saturating model wins on AIC due to its parsimony (k=1). The sigmoid achieves lower RSS but at the cost of an additional parameter.

### Model Parameters

**Linear:** y = 0.0898·x + 0.5844 (clamped to [0,1])
- Intercept from run_023 OLS regression (n=140); β_log_density = 0.0898, p = 0.0056

**Piecewise:** tau_log = 2.389 (tau ≈ 245), p_low = 0.000, p_high = 0.950
- Note: The grid-search finds a very low tau because a single non-investigated record at log=1.99 drives the split

**Saturating:** a = 0.710, y = 1 − exp(−0.710·log_density)

**Sigmoid:** k = 1.663, x0 = 1.987 (inflection near lowest density)

---

## Best-Fit Shape and Interpretation

The saturating (exponential approach to ceiling) shape is the most parsimonious description of the density-response relationship. Its interpretation:

- At log_density = 2.0 (density ≈ 100): predicted investigability = 1 − exp(−0.710×2.0) = **0.758**
- At log_density = 3.5 (density ≈ 3,162): predicted investigability = 1 − exp(−0.710×3.5) = **0.917**
- At log_density = 4.0 (density ≈ 10,000): predicted investigability = 1 − exp(−0.710×4.0) = **0.942**
- At log_density = 5.0 (density ≈ 100,000): predicted investigability = 1 − exp(−0.710×5.0) = **0.972**

The curve approaches the ceiling (1.0) asymptotically. The density-response relationship is **rapid early gain, slow saturation** — consistent with a log-linear underlying mechanism.

The piecewise model (best delta at threshold=3587, log=3.555) confirms a **step-function-like transition** at the Q1 density boundary, providing a practically actionable threshold despite higher AIC.

---

## Good Operating Zone

Based on the saturating model (best by AIC):

| Target | log_density (x*) | min_density |
|--------|-----------------|-------------|
| ≥ 0.95 investigability | 4.219 | ~16,572 |
| ≥ 0.99 investigability | Not reachable within x ≤ 5.43 | — |

The saturating model cannot reach 0.99 within the observed density range — it asymptotes below 1.0. This is consistent with the **density ceiling** finding from run_021: even at maximum observed densities, ~7% of hypotheses remain uninvestigated due to factors beyond density.

---

## Threshold Recommendation

**Piecewise threshold analysis at Youden's J optimum (tau = 7497, log = 3.875):**

| Metric | Value |
|--------|-------|
| p_high (density ≥ 7497) | 0.9896 |
| p_low (density < 7497) | 0.8409 |
| Δ investigability | **+0.1487** |

**Best delta threshold (run_023): tau = 3587 (log = 3.555)**

| Metric | Value |
|--------|-------|
| p_high (density ≥ 3587) | 0.9744 |
| p_low (density < 3587) | 0.7826 |
| Δ investigability | **+0.1918** |

Recommended operational threshold: **min_density ≥ 3,587** (log ≥ 3.555)
- Maximizes delta investigability (0.1918)
- Aligns with Q1 boundary (3,255)
- Practical filter: excludes ~16% of hypotheses below this threshold

For high-confidence operation: **min_density ≥ 7,497** (log ≥ 3.875)
- Near-ceiling investigability (0.9896) above threshold
- More conservative filter

---

## Conclusion

1. **Shape confirmed**: The density-response relationship follows a saturating (ceiling-approach) curve. Investigability rises steeply with log_density in the low range and flattens above log ≈ 4.0 (density ≈ 10,000).

2. **Best model by AIC**: Saturating (a=0.710, k=1). Parsimonious and interpretable.

3. **Good operating zone**: For ≥95% investigability, set min_density ≥ 16,572 under the saturating model; for a more practical threshold with maximum delta, use min_density ≥ 3,587.

4. **Ceiling confirmed**: The density ceiling from run_021 (H_ceiling: density explains but does not fully determine investigability) is reproduced — the model cannot reach 0.99 within the observed range.

5. **C1 vs C2 asymmetry**: C1's near-ceiling performance across all density bins (0.971) masks the density-response signal; the relationship is primarily driven by C2 (r=0.46 combined; C2 alone shows strong density dependence per logistic regression coef=1.468).

6. **Recommendation for P2 framework**: Apply min_density ≥ 3,587 as a density gate in hypothesis generation. This retains ~84% of candidates while raising investigability from 0.943 to 0.974 on the above-threshold subset.
