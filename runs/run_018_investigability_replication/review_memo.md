# Run_018 Investigability Replication — Review Memo

**Date**: 2026-04-14
**Run ID**: run_018_investigability_replication
**Purpose**: Replicate SC-3r (investigability PASS, p=0.0007 in run_017) with N=70
**Pre-registration**: configs/investigability_registry.json
**NOT a rescue of SC-1r** — novel_supported_rate FAIL in run_017 stands unchanged.

---

## 設計

| 項目 | 設定 |
|------|------|
| N per method | 70 (50 from run_017 + 20 new) |
| Total | 210 |
| Primary endpoint | investigability_rate (investigated / total) |
| Statistical test | Fisher's exact test, one-sided |
| Significance level | α = 0.05 (primary), α = 0.10 (secondary) |
| Validation period | 2024-01-01 to 2025-12-31 |
| known_fact threshold | 20 (≤2023 PubMed hits) |
| seed | 42 |

---

## 仮説生成結果

| Method | N | Cross-domain |
|--------|---|-------------|
| C2 (multi-op) | 70 | 70 (100%) |
| C1 (single-op) | 70 | 0 (0%) |
| C_rand_v2 | 70 | ~100% |

---

## PubMed Validation + Labeling

| Method | N | Investigated | Investigability | known_fact | novel_supported | novel_sup_rate |
|--------|---|-------------|----------------|-----------|----------------|----------------|
| C2 (multi-op) | 70 | 64 | 0.914 | 49 | 11 | 0.172 |
| C1 (single-op) | 70 | 68 | 0.971 | 64 | 5 | 0.074 |
| C_rand_v2 | 70 | 42 | 0.600 | 21 | 15 | 0.357 |

---

## 統計検定

### SC_inv_primary (主) — investigability(C2) > C_rand_v2

- C2: **0.914**  vs  C_rand_v2: **0.600**
- p = **0.0000**  →  **PASS ✓**

### SC_inv_secondary — investigability(C2) > C1

- C2: **0.914**  vs  C1: **0.971**
- p = **0.9687**  →  **FAIL ✗** (α=0.10)

### SC_inv_replication — C2 investigability ≥ 0.85

- C2 investigability = **0.914**  (run_017 was 0.920)
- →  **PASS ✓**

---

## 総合判定: **GO**

GO | SC_inv_primary(p<0.05)=PASS | SC_inv_secondary(p<0.10)=FAIL | SC_inv_replication(>=0.85)=PASS

---

## Sensitivity Analysis (exploratory — 主解析結論に影響しない)

| Threshold | C2 inv | C_rand inv | primary p | Result |
|-----------|--------|-----------|-----------|--------|
| 20 | 0.914 | 0.600 | 0.0000 | PASS |
| 50 | 0.914 | 0.600 | 0.0000 | PASS |
| 100 | 0.914 | 0.600 | 0.0000 | PASS |
| 200 | 0.914 | 0.600 | 0.0000 | PASS |


---

## 結果の解釈

**GO**: investigability 仮説が N=70 で再現された。KG multi-op パイプラインは random sampling より有意に investigable な仮説を生成することが確認された。

---

## SC-1r に関する注記

**本実験は SC-1r (novel_supported_rate) の評価を行わない。**

run_017 での SC-1r 結果:
- C2 novel_supported_rate = 0.130
- C_rand_v2 novel_supported_rate = 0.219
- p = 0.9088 → **FAIL (確定)**

SC-1r は本実験の primary endpoint でも secondary endpoint でもない。
novel_supported_rate の数値は記録されるが、判定に使用しない。

---

## Artifacts

| ファイル | 内容 |
|--------|------|
| hypotheses_c2.json | C2 70件 |
| hypotheses_c1.json | C1 70件 |
| hypotheses_crand_v2.json | C_rand_v2 70件 |
| validation_corpus.json | PubMed 2024-2025 結果 |
| labeling_results_layer1.json | Layer 1 (5-class) ラベル |
| labeling_results_layer2.json | Layer 1+2 ラベル |
| statistical_tests.json | SC_inv_primary / secondary / replication |
| sensitivity_analysis.json | threshold 20/50/100/200 での再分析 |
| review_memo.md | 本ファイル |
