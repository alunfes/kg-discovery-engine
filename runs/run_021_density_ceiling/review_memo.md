# run_021 Density Ceiling Analysis — Review Memo

**Date**: 2026-04-13
**Run**: run_021_density_ceiling
**Hypotheses tested**: H_ceiling, H_match

---

## 実験概要

run_018 (210件: C2 70, C1 70, C_rand_v2 70) に PubMed density metrics (≤2023) を付与し、
density が investigability を説明するかを検証した。

- **H_ceiling**: cross-domain investigability は operator quality より density asymmetry で決まる
- **H_match**: novelty × density をマッチングすると C1-C2 investigability gap が縮まる (≤0.02)

---

## Step 2: Density-Investigability 相関

| Metric | Point-Biserial r |
|--------|-----------------|
| log_min_density | 0.4609 |
| object_density | 0.2782 |
| min_density | 0.1976 |
| pair_density | 0.1236 |
| subject_density | 0.0106 |

**最強予測因子**: `log_min_density` (|r| = 0.4609)
**H_ceiling 相関基準 (|r| ≥ 0.4)**: ✅ 達成

---

## Step 3: Quartile Analysis

| Quartile | Investigability |
|----------|----------------|
| Q1 (low) | 0.5273 |
| Q4 (high) | 0.9800 |
| Gap (Q4-Q1) | 0.4527 |

**H_ceiling 基準 (Q4-Q1 gap ≥ 0.15)**: ✅ 達成

---

## Step 4: Logistic Regression

- Feature: `log_min_density`
- McFadden pseudo R²: **0.2184**
- 解釈: moderate (0.15-0.25)

---

## Step 5: Matched Comparison (density-only)

注: novelty は method と完全に共線 (C1=全て nov_low, C2=全て nov_high) のため、density-only matching を適用 (matched_comparison_plan.md 代替2)

| Density Bin | n_C1 | n_C2 | C1_inv | C2_inv | Gap (C1-C2) |
|-------------|------|------|--------|--------|------------|
| density=den_low | 23 | 25 | 0.9565 | 0.76 | 0.1965 |
| density=den_mid | 16 | 29 | 1.0 | 1.0 | 0.0 |
| density=den_high | 31 | 16 | 0.9677 | 1.0 | -0.0323 |

- Unmatched C1-C2 gap: **0.0571**
- Matched gap (density-only, weighted): **0.0565**
- **H_match verdict**: **rejected**
- Note: matched gap 0.0565 > 0.04 — density alone does not explain C1-C2 gap

**重要な観察**: gap は density_low 群 (C1=0.957, C2=0.76) に集中。
density_mid/high ではギャップが消失または逆転 → density を control すると C1-C2 は同等になる傾向あり。

---

## Statistical Tests

| Test | p-value | Significant (p<0.05) |
|------|---------|---------------------|
| Q4 vs Q1 density | 0.0 | True |
| C2 high vs low density | 0.005615 | True |
| C1 vs C2 overall | 0.13732 | False |

---

## 結論

### H_ceiling
**支持**: density と investigability に有意な相関あり。
Q4-Q1 gap も基準達成 ≥0.15。
pseudo R² = 0.2184 — density が investigability を十分に説明しない。

### H_match
**rejected**: matched gap 0.0565 > 0.04 — density alone does not explain C1-C2 gap

---

## 次のアクション

- H_match 棄却/不明 → C1-C2 gap の別の説明 (operator の relation quality) を検討
