# H4 Rubric Revision — Run 010 設計書

## 問題の特定（Run 009 FAIL原因）

`_score_traceability()` の旧実装:
```
1-hop: 1.0
2-hop: 0.7
3-hop: 0.5
4-hop: 0.25
5-hop: 0.2
```

パス長が長いほどスコアが下がる設計。これはH4の検証において構造的バイアスを生んでいた。  
deep compose（3-hop+）で生成された候補は、品質によらずスコアが低くなるため、
provenance-aware rankingは常に「deep候補を降格させる」動作になる。

## 修正の設計思想

**長さを罰するのではなく、チェーンの弱さを罰する。**

良いdeep pathとは：
- 各関係が機能的・機構的に明確（inhibits, activates, catalyzes等）
- 中間ノードが汎用的でなく、具体的なエンティティ
- 同じ関係タイプが連続出現しない（コピー貼り付けではない）

悪いdeep pathとは：
- 弱い関係（relates_to, associated_with等）で構成される
- 同じ関係タイプが連続する（hub nodeを繰り返し通過）
- 汎用ラベル（process, system, entity等）の中間ノードを経由

## 修正後のスコアリング（revised_traceability=True）

**ベーススコア: 1.0**

ペナルティ:
1. **Low-specificity relation penalty**: `-0.1` per relation in:
   `{relates_to, associated_with, part_of, has_part, interacts_with, is_a, connected_to, involves, related_to}`
2. **Consecutive repeated relation penalty**: `-0.15` per pair of consecutive identical relations
3. **Generic intermediate node penalty**: `-0.05` per intermediate node whose label matches:
   `{process, system, entity, substance, compound}`

**Floor: 0.1**（完全にゼロにはしない）

## 実装

`src/eval/scorer.py` に追加:

- `_LOW_SPEC_TRACE_RELATIONS` (frozenset)
- `_WEAK_INTERMEDIATE_LABELS` (frozenset)  
- `_score_traceability_revised(candidate, kg)` — ペナルティベース実装
- `EvaluationRubric.revised_traceability: bool = False` — フラグ追加
- `_score_traceability()` でdispatch

## フラグ切り替え

```python
# 旧ルーブリック（パス長直接罰）
rubric = EvaluationRubric(provenance_aware=True, revised_traceability=False)

# 修正ルーブリック（品質ベース罰）
rubric = EvaluationRubric(provenance_aware=False, revised_traceability=True)
```

## 検証結果（Run 010）

| 指標 | 旧aware | 修正 |
|------|---------|------|
| H4 verdict | FAIL | **PASS** |
| Deep promoted vs naive | N/A | 309 |
| Deep demoted vs naive | N/A | 209 |
| Deep cross-domain promoted | N/A | 14 |
| Top-20 Jaccard (naive vs scheme) | 1.0 | 0.429 |

修正ルーブリックは深い候補の相対順位を改善し、H4をFAIL→PASSに反転させた。
ただし、top-20はまだ2-hop候補が占める（2-hopの strong chain score が高すぎる）。
これはdrift filterを実装してquality deepを増やすことで改善できる（Run 012課題）。
