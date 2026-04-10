# Before/After Comparison — Run 009 vs Run 012

**Date**: 20260410
**Baseline**: Run 009 Condition C P4 + Run 011 qualitative labels (20 deep cross-domain)
**Filtered**: Run 012 (pre-compose drift filter)

## Metric 1: 候補総数

| | 候補総数 |
|---|---|
| Run 009 (baseline) | 939 |
| Run 012 (filtered) | 446 |
| 削減数 | 493 (52.5%) |

## Metric 2: Deep Cross-Domain候補数 (≥3-hop かつ cross-domain)

| | Deep CD候補数 |
|---|---|
| Run 009 (baseline) | 20 |
| Run 012 (filtered) | 3 |
| 削減数 | 17 |

## Metric 3: Promising / Weak_Speculative / Drift_Heavy 分布

| ラベル | Run 011 (before) | Run 012 (after) | 変化 |
|--------|-----------------|-----------------|------|
| promising | 3 (15.0%) | 3 (100.0%) | ↑ |
| weak_speculative | 12 (60.0%) | 0 (0.0%) | ↓ |
| drift_heavy | 5 (25.0%) | 0 (0.0%) | ↓ |
| **合計** | **20** | **3** | |

## Metric 4: Top-20の構成

### Depth分布

| Bucket | Baseline | Filtered |
|--------|----------|---------|
| 2-hop | 20 | 20 |\n
| Cross-domain in top-20 | 0 | 0 |

## Metric 5: Top-20 Mean Quality Score

| | Mean Score |
|---|---|
| Baseline | 0.78 |
| Filtered | 0.78 |

## Metric 6: Filterによって消えた候補の内訳

Deep Cross-Domain候補の除去分析:
- 除去総数: 17
- By label:
  - promising: 0
  - weak_speculative: 12
  - drift_heavy: 5

除去された候補の詳細:

| ID | ラベル | 除去理由 |
|----|--------|---------|
| H0268 | weak_speculative | weak_strong_ratio=0.33<0.4 |\n| H0275 | weak_speculative | filter_relations: ['is_reverse_of']; weak_strong_ratio=0.25<0.4 |\n| H0300 | weak_speculative | filter_relations: ['is_reverse_of'] |\n| H0344 | weak_speculative | filter_relations: ['is_reverse_of']; weak_strong_ratio=0.33<0.4 |\n| H0348 | weak_speculative | filter_relations: ['contains']; consecutive_repeat; weak_strong_ratio=0.25<0.4 |\n| H0349 | weak_speculative | filter_relations: ['contains']; consecutive_repeat; weak_strong_ratio=0.25<0.4 |\n| H0356 | weak_speculative | filter_relations: ['contains']; consecutive_repeat; weak_strong_ratio=0.25<0.4 |\n| H0357 | weak_speculative | filter_relations: ['contains']; consecutive_repeat; weak_strong_ratio=0.25<0.4 |\n| H0378 | drift_heavy | filter_relations: ['is_reverse_of']; weak_strong_ratio=0.0<0.4 |\n| H0401 | weak_speculative | filter_relations: ['is_reverse_of']; weak_strong_ratio=0.33<0.4 |\n| H0407 | drift_heavy | filter_relations: ['is_product_of', 'contains']; weak_strong_ratio=0.0<0.4 |\n| H0408 | drift_heavy | filter_relations: ['is_product_of', 'is_isomer_of', 'contains']; weak_strong_ratio=0.0<0.4 |\n| H0428 | drift_heavy | filter_relations: ['contains']; consecutive_repeat; weak_strong_ratio=0.0<0.4 |\n| H0429 | drift_heavy | filter_relations: ['contains']; consecutive_repeat; weak_strong_ratio=0.0<0.4 |\n| H0524 | weak_speculative | filter_relations: ['is_reverse_of'] |\n| H0633 | weak_speculative | weak_strong_ratio=0.33<0.4 |\n| H0644 | weak_speculative | filter_relations: ['is_reverse_of']; weak_strong_ratio=0.25<0.4 |\n

## Metric 7: Promising候補の損失

**0件** のpromising候補を失った。
（損失なし — 全promising候補が保持された）

## Metric 8: Drift_Heavy候補の除去

**5件** のdrift_heavy候補を除去した（before: 5件）。

## Metric 9: 除去効率

drift_heavy除去数 / total除去数 = 5/17 = **29.4%**

5/17 removed candidates were drift_heavy

## 成功条件判定

| 条件 | 目標 | 結果 | 判定 |
|------|------|------|------|
| drift_heavy率 | 25% → <15% | 0.0% | PASS |
| promising率 | 15% → >25% | 100.0% | PASS |
| deep CD候補が大幅崩れない | ≥3件 | 3件 | PASS |
