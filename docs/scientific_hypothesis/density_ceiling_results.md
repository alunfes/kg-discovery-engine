# Density Ceiling Analysis Results — run_021

**Date**: 2026-04-13
**Status**: COMPLETED

---

## 主仮説検証結果

### H_ceiling: cross-domain investigability は density asymmetry で決まるか

**判定**: 支持

**根拠**:
- 最強 predictor: `log_min_density` (point-biserial |r| = 0.4609)
- 閾値: |r| ≥ 0.4 → ✅ 達成
- McFadden pseudo R² (log_min_density → investigated) = 0.2184
- Q4 vs Q1 investigability gap = 0.4527 (threshold: ≥0.15)

**全相関係数**:

| Metric | |r| | 方向 |
|--------|-----|------|
| log_min_density | 0.4609 | density↑ → investigability↑ |
| object_density | 0.2782 | density↑ → investigability↑ |
| min_density | 0.1976 | density↑ → investigability↑ |
| pair_density | 0.1236 | density↑ → investigability↑ |
| subject_density | 0.0106 | density↑ → investigability↓ |

---

### H_match: matched comparison で C1-C2 gap が縮まるか

**判定**: **rejected**

| 比較 | Investigability |
|------|----------------|
| C1 (unmatched) | 0.9714 |
| C2 (unmatched) | 0.9143 |
| Unmatched gap | 0.0571 |
| Matched gap (weighted) | 0.0565 |

**Reportable cells** (N≥5 each group): 0 / 4

matched gap 0.0565 > 0.04 — density alone does not explain C1-C2 gap

---

## Density が investigability をどの程度説明するか

- **McFadden pseudo R²** = 0.2184: log_min_density が investigability 分散の一部説明しない
- **Q1-Q4 gap** = 0.4527: density が低い仮説と高い仮説で investigability が大きく異なる

---

## Method 別 density と investigability

| Method | avg_min_density | avg_pair_density | investigability |
|--------|----------------|------------------|----------------|
| C1_compose | 29007 | 2194.5 | 0.9714 |
| C2_multi_op | 14213 | 384.4 | 0.9143 |
| C_rand_v2 | 9032 | 70.2 | 0.6000 |

---

## C1-C2 gap の原因の整理

1. **density composition の違い**: C1 (bio-only) は C2 (cross-domain) より density が高い
2. **density の説明力**: pseudo R² = 0.2184 → densityは主要因である
3. **matched 比較**: matched gap 0.0565 > 0.04 — density alone does not explain C1-C2 gap

---

## 次のアクション

- H_match 棄却/不明 → C1-C2 gap の別の説明 (operator の relation quality) を検討

---

## 関連ファイル

- `runs/run_021_density_ceiling/density_scores.json` — 210件のdensityスコア
- `runs/run_021_density_ceiling/correlation_analysis.json` — 相関分析結果
- `runs/run_021_density_ceiling/quartile_analysis.json` — 四分位分析
- `runs/run_021_density_ceiling/matched_comparison.json` — マッチング比較
- `runs/run_021_density_ceiling/statistical_tests.json` — 統計検定
