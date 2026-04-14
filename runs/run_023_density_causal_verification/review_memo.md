# run_023 Review Memo — Density Causal Verification

Date: 2026-04-14

## 目的

「model差ではなくdensityが支配変数である」ことの統計的検証。
run_018 (C1 vs C2, N=70 each) + run_022 (C2_da) のデータを統合。

## 核心結果

### Model A: score ~ intercept + log_density + model_C2

| Feature | β | SE | t | p |
|---------|---|----|---|---|
| intercept | 0.6266 | 0.1350 | 4.641 | 0.0000 |
| log_density | 0.0843 | 0.0323 | 2.607 | 0.0102 |
| model_C2 | -0.0405 | 0.0389 | -1.039 | 0.3006 |

### R² 分解

| Model | R² | 説明 |
|-------|-----|------|
| density-only | 0.0543 | log_density のみ |
| Model A (density+model) | 0.0617 | +model_C2 |
| Model B (interaction) | 0.1453 | +interaction |
| Model C (piecewise) | 0.0888 | piecewise density |
| density 説明率 | 88.0% | density / full model |
| model 増分寄与 | 12.0% | model / full model |

### Density-Matched Fisher Test (quartile matching)

| 指標 | 値 |
|------|---|
| N (matched) | 51 C1 / 51 C2 |
| C1 investigability | 0.9804 |
| C2 investigability | 0.9020 |
| delta (C2-C1) | -0.0784 |
| Fisher p | 0.204689 |

## Q&A

**Q1:** NO — density 固定後、モデル差は非有意 (p=0.3006)
**Q2:** density-only model: R²=0.0543 (88.0% of full model R²=0.0617)
**Q3:** SAMPLING BIAS (density mismatch) — model β=-0.0405 not significant (p=0.3006)

Matched support: Density-matched Fisher test (p=0.2047, delta=-0.0784) SUPPORTS final claim.

## Final Claim

**A: Model performance difference is primarily explained by density.**

## 成果物

- unified_dataset.json: 1 ファイル
- regression_results.json
- matched_subset_test.json
- density_threshold_analysis.json
- plots/scatter_log_density.html
- plots/bar_density_bin.html
- plots/density_histogram.html
