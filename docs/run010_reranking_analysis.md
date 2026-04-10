# Run 010 Re-ranking Analysis — H4 Rubric Revision

**Date**: 2026-04-10  
**Condition**: C (sparse-bridge cross-domain, 536 nodes)  
**Reuses**: Run 009 KG (no new data construction)

## 実験設計

Run 009のCondition C KGを再利用し、P4 multi/deep pipelineの全候補(939件)に対して
3方式のランキングを適用・比較する。

| 方式 | 設定 | 概要 |
|------|------|------|
| naive | `provenance_aware=False, revised=False` | 固定traceability=0.7 |
| old_aware | `provenance_aware=True, revised=False` | 旧深さ逆比例ペナルティ |
| revised_aware | `revised_traceability=True` | 品質ベースペナルティ（Run 010新設計） |

## 候補統計

| 統計 | 値 |
|------|----|
| 総候補数（P4） | 939 |
| Deep候補 (≥3-hop) | 520 (55%) |
| Cross-domain候補 | 42 |
| Deep cross-domain | 20 |

## 3方式Top-20 Jaccard比較

| ペア | Jaccard |
|------|---------|
| naive vs old_aware | 1.000 |
| naive vs revised | 0.429 |
| old_aware vs revised | 0.429 |

**解釈**: 旧awareとnaiveは完全一致（Jaccard=1.0）— 実質的に同じランキング。
revisedは大きく異なり、top-20の42%が入れ替わった（new_entries=8）。

## Deep候補の順位変動（revised vs naive）

| 移動 | 全Deep | Deep Cross-Domain |
|------|--------|------------------|
| 昇格 | 309 | 14 |
| 降格 | 209 | 6 |
| 不変 | 2 | 0 |

**deep候補の純昇格**: +100件（309-209）  
**deep cross-domainの純昇格**: +8件（14-6）

## H4 Verdict

| 方式 | H4判定 | 根拠 |
|------|--------|------|
| old_aware | **FAIL** | naive=awareで実質同一；deep降格 |
| revised_aware | **PASS** | 309昇格 > 209降格；cross-domain14昇格 |

## Top-20深さ分布

| Bucket | Naive | Revised |
|--------|-------|---------|
| 2-hop | 20 | 20 |
| 3-hop+ | 0 | 0 |

**注記**: Top-20はいずれの方式でも2-hopのみ。2-hop strong-chain候補（activates/inhibitsチェーン）
のスコアが3-hop以上を圧倒している。revisedはdeep候補の**相対順位**を改善するが、
top-20に引き上げるには pre-compose drift filter（Run 012）でdeep candidateの品質を
向上させる必要がある。

## Cross-domainのTop-20入り

| 方式 | Cross-domain in top-20 |
|------|------------------------|
| naive | 0 |
| revised | 0 |

## 主要な発見

1. **H4 FAIL→PASS**: 旧ルーブリックの設計問題を修正し、revisedでH4を反転させた
2. **大幅な順位変動**: Jaccard 0.429 — revisedは実質的に異なるランキングを生成
3. **Top-20はまだ2-hop**: Deep候補の品質改善（drift filter）なしにはtop-k進出困難
4. **Cross-domain deep候補は昇格**: 14/20のdeep cross-domain候補がnaive比で上昇
5. **旧awareとnaiveは同一**: 旧provenance-aware rankingは実質的にnaiveと等価

## 次ステップへの示唆

- Run 012: pre-compose drift filter実装 → deep候補の品質向上 → top-20進出テスト
- revised_traceability=Trueをデフォルトとして採用
- Cross-domain top-kへの昇格は drift filter後に再検証
