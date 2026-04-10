# Run 012 Filter Plan — Review-Driven Drift Suppression

**Date**: 2026-04-10  
**Status**: Implemented

## 背景

Run 011の質的レビュー（20件のdeep cross-domain候補）で以下が判明した:

| ラベル | 件数 | 割合 |
|--------|------|------|
| promising | 3 | 15% |
| weak_speculative | 12 | 60% |
| drift_heavy | 5 | 25% |

Driftの主因は従来想定していた汎用connector（relates_to等）ではなく、
**化学構造関係**（contains, is_product_of等）とアミノ酸生合成チェーンの連続出現だった。

## Filter設計

### Filter 1: `filter_relations` (最優先)

```python
_FILTER_RELATIONS = frozenset({
    "contains",        # 分子構成成分 — 構造的事実のみ
    "is_product_of",   # 代謝産物関係 — 方向性なし
    "is_reverse_of",   # 反応逆方向 — 機構的意味なし
    "is_isomer_of",    # 異性体関係 — 構造的事実
})
```

これらはRun 011のdrift_heavy 5件全てに含まれる関係タイプ。
機構的発見に不向きな関係クラスの抑制であり、汎用的なnoiseリダクションではない。

### Filter 2: `guard_consecutive_repeat=True`

同じ関係タイプが連続するパスを拒否。
`is_precursor_of → is_precursor_of` （アミノ酸生合成チェーン）を主たる対象とする。

### Filter 3: `min_strong_ratio=0.40`

depth≥3のパスで `_STRONG_MECHANISTIC` の比率が40%未満なら拒否。
強relation = {inhibits, activates, catalyzes, produces, encodes, accelerates, yields, facilitates}

### Filter 4: `filter_generic_intermediates=True`

中間ノードに汎用ラベル（process, system, entity, substance, compound）が含まれるパスを拒否。

## 実装方針

- `compose()` の新パラメータとして実装（backward compatible）
- デフォルト値: 全filterをOFF（既存動作を変えない）
- Run 012ランナーでfilterを有効化

## 期待効果

Run 011ラベル付き20件の事前分析（filterパラメータ適用時の生存/除去予測）:

| ラベル | Before | 予測 After | 変化 |
|--------|--------|-----------|------|
| promising | 3 (15%) | 3 (維持) | 損失なし |
| drift_heavy | 5 (25%) | 0 (除去) | 全件除去 |
| weak_speculative (is_reverse_of含む) | 8 | 2 (一部除去) | is_reverse_of除去 |

## 注意事項

- `is_reverse_of` のfilterはweak_speculative候補（NADH→r_Oxidation→r_Reduction）も除去する
- これらはr_Reduction（化学的還元）への展開であり、機構的仮説ではなく化学的事実
- over-pruneリスク: filter後deep CD候補が5件程度に減少する見込み
- promsiing損失がある場合はトレードオフを明示的に文書化する（実際は損失なし）
