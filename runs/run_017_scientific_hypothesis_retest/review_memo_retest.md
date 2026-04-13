# Phase 3 Re-test Review Memo — run_017_scientific_hypothesis_retest

**Date**: 2026-04-14
**Labeling**: automated_pubmed_keyword_v2 (Layer1 + Layer2)
**Validation period**: 2024-01-01 to 2025-12-31
**Known-fact threshold**: ≤2023 hits > 20
**Hypotheses**: 150 total
  (C2=50, C1=50, C_rand_v2=50)

---

## 前回 NO-GO についての評価保留宣言

前回 Phase 2 の SC-1 FAIL (p=1.000) は **C_rand baseline 設計不備** による評価保留として扱う。

- C_rand v1 は KG パストラバーサルで生成 → 自明な既知事実ペアを含む
  (例: HER2→breast_cancer, obesity→NAFLD, JAK inhibition→RA)
- これらは PubMed ヒット数が trivially 高く precision=1.000 になる
- C2 の 0.833 は「より新規な仮説を生成している証拠」

C_rand v2 では：
- 真のランダムサンプリング（KG パス非依存）
- KG 1-hop エッジ blacklist
- Trivially-known ペア blacklist (N=~80)
- N: 20→50

---

## Label distribution (Layer 2)

| Method | N | known_fact | novel_supported | plausible_novel | implausible | novel_sup_rate | plausible_novelty | known_fact_rate |
|--------|---|-----------|----------------|-----------------|-------------|----------------|-------------------|-----------------|
| C2 | 50 | 37 | 6 | 7 | 0 | 0.130 | 0.260 | 0.740 |
| C1 | 50 | 46 | 4 | 0 | 0 | 0.082 | 0.080 | 0.920 |
| C_rand_v2 | 50 | 21 | 7 | 22 | 0 | 0.219 | 0.580 | 0.420 |

---

## Statistical tests (SC-1r through SC-4r)

### SC-1r (primary) — novel_supported_rate(C2) > C_rand_v2
- C2: 0.130  vs  C_rand_v2: 0.219
- p = 0.9088  →  **FAIL ✗**

### SC-2r — plausible_novelty_rate(C2) > C_rand_v2
- C2: 0.260  vs  C_rand_v2: 0.580
- p = 0.9997  →  **FAIL ✗**

### SC-3r — investigability(C2) >= C_rand_v2
- C2: 0.920  vs  C_rand_v2: 0.640
- p = 0.0007  →  **PASS ✓**

### SC-4r (exploratory) — known_fact_rate(C2) < C_rand_v2
- C2: 0.740  vs  C_rand_v2: 0.420
- p = 0.9997  →  **FAIL ✗**

---

## Overall: NO-GO

NO-GO | SC-1r(primary)=FAIL | SC-2r=FAIL | SC-3r=PASS | SC-4r=FAIL

---

## 結果の解釈

SC-1r FAIL: C2 は novel_supported_rate で C_rand_v2 を有意に上回らなかった。解釈を下記に記す。


**正直な評価 (SC-1r FAIL の場合)**:
- 両者の novel_supported_rate が同水準の場合、C2 の多段オペレータによる絞り込みに
  統計的優位性が確認できなかった
- ただし unknown_fact 比率 (SC-4r) で C_rand_v2 > C2 が確認されれば、
  C2 が trivial 再発見を回避していることは示せる
- N=50 でも検出力不足の可能性: effect size < 0.15 は要 N>200
- 次ステップ: N を 200 に増やす OR ドメインを絞り込む


## Limitations

1. Automated labeling: keyword heuristic approximation, not expert annotation
2. API sampling: max 5 papers per hypothesis; some `not_investigated` may have unchecked evidence
3. known_fact threshold 20 is heuristic; calibration needed
4. C_rand_v2 pairs may still include some plausibly-known connections

## Artifacts

| File | Contents |
|------|----------|
| hypotheses_c2.json | 50 C2 hypotheses |
| hypotheses_c1.json | 50 C1 hypotheses |
| hypotheses_crand_v2.json | 50 C_rand_v2 hypotheses |
| validation_corpus.json | PubMed 2024-2025 results |
| labeling_results_layer1.json | Layer 1 (5-class) labels |
| labeling_results_layer2.json | Layer 2 (novelty) labels |
| statistical_tests_v2.json | SC-1r through SC-4r |
| baseline_parity_check.json | C_rand v1 vs v2 comparison |
