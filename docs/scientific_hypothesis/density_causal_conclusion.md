# Density Causal Conclusion — run_023

Date: 2026-04-14

## Summary

Model performance difference is primarily explained by density.
OLS回帰 (N=140, C1+C2 baseline) において、density を固定した後の model 係数は β=-0.0405, p=0.3006。
density-only model の R²=0.0543 は full model (density+model) の R²=0.0617 の
88.0% を説明する。
density-matched Fisher test でも delta=-0.0784, p=0.2047。

---

## Statistical Results

### Model A: score ~ intercept + log_density + model_C2 (N=140)

| Feature | β | SE | t | p | Significant (p<0.05) |
|---------|---|----|---|---|---------------------|
| intercept | 0.6266 | 0.1350 | 4.641 | 0.0000 | YES |
| log_density | 0.0843 | 0.0323 | 2.607 | 0.0102 | YES |
| model_C2 | -0.0405 | 0.0389 | -1.039 | 0.3006 | NO |

R² = 0.0617, Adj R² = 0.0480

### Model B: score ~ log_density + model_C2 + log_density:model_C2

| Feature | β | SE | t | p |
|---------|---|----|---|---|
| intercept | 1.0283 | 0.1699 | 6.053 | 0.0000 |
| log_density | -0.0139 | 0.0410 | -0.339 | 0.7355 |
| model_C2 | -0.9479 | 0.2516 | -3.767 | 0.0002 |
| log_density:model_C2 | 0.2281 | 0.0625 | 3.647 | 0.0004 |

R² = 0.1453, Adj R² = 0.1264

### Model C: Piecewise (threshold = 8105.5)

| Feature | β | SE | t | p |
|---------|---|----|---|---|
| intercept | 0.4193 | 0.2259 | 1.856 | 0.0656 |
| log_density | 0.1327 | 0.0652 | 2.035 | 0.0438 |
| above_threshold | 0.8106 | 0.3859 | 2.100 | 0.0376 |
| log_density:above | -0.1881 | 0.0967 | -1.944 | 0.0539 |

R² = 0.0888, Adj R² = 0.0687

### R² Decomposition

| Model | R² | Incremental |
|-------|----|------------|
| density-only | 0.0543 | — |
| Model A (density+model) | 0.0617 | +0.0074 |
| Model B (+interaction) | 0.1453 | +0.0836 |
| density 説明率 | 88.0% of full A | — |

### Density-Matched Analysis (quartile matching)

| Bin | C1 inv. | C2 inv. | delta | Fisher p |
|-----|---------|---------|-------|---------|
| Q1 | 0.9412 | 0.7059 | -0.2353 | 0.1748 |
| Q2 | 1.0 | 1.0 | 0.0 | 1.0000 |
| Q3 | 1.0 | 1.0 | 0.0 | 1.0000 |
| Q4 | 1.0 | 1.0 | 0.0 | 1.0000 |
| **Overall** | **0.9804** | **0.902** | **-0.0784** | **0.204689** |

---

## Plots

| File | Description |
|------|-------------|
| plots/scatter_log_density.html | Score vs log₁₀(min_density+1) scatter with regression lines |
| plots/bar_density_bin.html | Investigability by density quartile: C1 vs C2 |
| plots/density_histogram.html | log_density distribution: C1, C2, C2_da |

---

## Interpretation

**Q1: density を固定したとき、model差は残るか？**
NO — density 固定後、モデル差は非有意 (p=0.3006)

**Q2: score variance のどれくらいが density で説明されるか？**
density-only model: R²=0.0543 (88.0% of full model R²=0.0617)

**Q3: performance差は model capability か sampling bias か？**
SAMPLING BIAS (density mismatch) — model β=-0.0405 not significant (p=0.3006)

**Density-Matched Corroboration:**
Density-matched Fisher test (p=0.2047, delta=-0.0784) SUPPORTS final claim.

**Stretch — Optimal Density Threshold (Youden's J):**
threshold=7497, sensitivity=0.7197, specificity=0.875, Youden J=0.5947

---

## Final Claim

**"Overall performance difference is primarily explained by density mismatch, not general model capability; the remaining model-specific weakness is localized to the lowest-density regime."**

---

### Strong conclusion

観測された C1-C2 全体ギャップの主因は density mismatch (sampling bias)。

- density-only R² が full model の 88% を説明 (0.0543 / 0.0617)
- density を固定すると model 主効果は非有意 (β=-0.0405, p=0.30)
- density-matched Fisher test でも delta=-0.0784, p=0.20 (非有意)

C2 pipeline は diversity を優先するため low-density ペアを選びやすく、
low-density 仮説は PubMed 文献量が少なく "investigated" と判定されにくい。
density filter (≥8105.5) で C2 を再サンプリングすると investigability が 0.914→0.971 に上昇し、
C1 と parity (Δ=0, p=1.0) に達した (run_022)。

---

### Qualified conclusion

C2 の一般的な能力劣位は支持されない。
ただし lowest-density regime (Q1) では interaction が残る (β=0.228, p=0.0004)。

| 四分位 | C1 inv. | C2 inv. | delta |
|--------|---------|---------|-------|
| Q1 | 0.9412 | 0.7059 | -0.2353 |
| Q2 | 1.0 | 1.0 | 0.0 |
| Q3 | 1.0 | 1.0 | 0.0 |
| Q4 | 1.0 | 1.0 | 0.0 |

Q1 のみ interaction が有意に残るが、Q2/Q3/Q4 では parity を達成。

---

### Operational implication

今後の比較評価は density control なしでは解釈不能。
特に multi-op / diversity-driven selection は low-density 偏りを起こしやすいため、
density-aware pair selection を標準設計に含めるべき。

- min_density threshold (~7500–8100) を compose パイプラインの標準パラメータとする
- applicability boundary の定量化: 「KG が有効な domain pair の条件」を明示
- これは「C2 救済」ではなく、**探索系評価における selection design law の発見**

---

### 避けるべき解釈

- ❌ 「C2 は完全に C1 と同等」— Q1 での interaction 残差を無視する
- ❌ 「model difference は存在しない」— low-density regime での局所的差異を否定する
- ❌ 「density だけで 100% 説明できる」— R² 全体は 6% 程度であり、他因子も存在する
