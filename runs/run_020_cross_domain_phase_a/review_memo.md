# Run_020 P1 Phase A — Review Memo

**Date**: 2026-04-14
**Run ID**: run_020_cross_domain_phase_a
**Purpose**: P1 Phase A — bridge_quality / alignment_precision conditions
**Go/No-Go**: **NO-GO**

---

## 設計

| 項目 | 設定 |
|------|------|
| Pool | 70 C2 hypotheses from run_018 |
| Target N per condition | 30 (actual N may be lower for underpowered conditions) |
| T_high (novelty ceiling) | 0.75 (from P3 run_019) |
| Primary success criterion | investigability ≥ 0.95 for bridge_quality OR alignment_precision |
| Statistical test | Fisher's exact one-sided (condition > baseline) |
| Validation period | 2024-01-01 to 2025-12-31 |
| known_fact threshold | 20 (≤2023 PubMed hits) |
| seed | 42 |

---

## 条件設計

| 条件 | フィルタ |
|------|---------|
| C2_baseline | フィルタなし (pool first 30) |
| C2_bridge_quality | Bridge confidence ≥ 0.7 (broad semantic synonyms) |
| C2_alignment_precision | Bridge confidence ≥ 0.8 (strict token-overlap only) |
| C2_novelty_ceiling | combined_novelty ≤ 0.75 (from run_019) |
| C2_combined | Bridge ≥ 0.7 AND novelty ≤ 0.75 |

**注意**: C2_novelty_ceiling の N が少ない理由:
run_018 pool の mean combined_novelty = 0.833 > T_high=0.75 のため、
70 件中 ~8 件しか条件を満たさない。構造的制約。

---

## 結果

| 条件 | N | Investigated | Investigability | novel_sup | p vs baseline |
|------|---|-------------|----------------|-----------|---------------|
| C2_baseline | 30 | 28 | 0.933 | 4 | — |
| C2_bridge_quality | 30 | 27 | 0.900 | 5 | 0.8234 |
| C2_alignment_precision | 11 | 10 | 0.909 | 3 | 0.8297 |
| C2_novelty_ceiling | 8 | 8 | 1.000 ✓ | 0 | 0.6188 |
| C2_combined | 6 | 6 | 1.000 ✓ | 0 | 0.6905 |

参考: C1 investigability = 0.971, C2_baseline (run_018) = 0.914

---

## 総合判定: **NO-GO**

全条件で investigability ≤ 0.92 → align ではなく文献密度の構造的問題 → P2 優先度下げ

---

## 解釈

### bridge_quality 条件
Pool の broad synonym dict を適用することで、より信頼性の高い
cross-domain bridge を持つ仮説を優先的に選択。

### alignment_precision 条件
Token-overlap のみの strict 判定。実際に N が少ない場合は、
この KG では strict alignment が困難であることを示す。

### novelty_ceiling 条件
run_018 pool の novelty スコア分布上、T_high=0.75 以下の仮説が少ない。
これは KG multi-op が高 novelty 仮説を生成しやすい特性のため。

---

## Go/No-Go 基準

- **GO**: bridge_quality または alignment_precision で investigability ≥ 0.95
  → Phase B (provenance_quality) に進む価値あり
- **NO-GO**: 全条件で investigability ≤ 0.92
  → align ではなく文献密度の構造的問題 → P2 優先度を下げる

---

## Artifacts

| ファイル | 内容 |
|--------|------|
| hypotheses_c2_baseline.json | C2 baseline 30件 |
| hypotheses_c2_bridge_quality.json | Bridge quality 条件 |
| hypotheses_c2_alignment_precision.json | Alignment precision 条件 |
| hypotheses_c2_novelty_ceiling.json | Novelty ceiling 条件 |
| hypotheses_c2_combined.json | Combined 条件 |
| unique_hypotheses.json | 全ユニーク仮説 (PubMed 検索用) |
| validation_corpus.json | PubMed 2024-2025 結果 |
| labeling_results.json | Layer 1+2 ラベル (全ユニーク) |
| condition_labels.json | 各条件のラベル |
| statistical_tests.json | Fisher検定 + Go/No-Go |
| bridge_confidence_stats.json | Bridge confidence 分布 |
| run_config.json | 実験設定 |
| review_memo.md | 本ファイル |
