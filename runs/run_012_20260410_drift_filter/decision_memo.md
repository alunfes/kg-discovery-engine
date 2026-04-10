# Decision Memo — Run 012

**Date**: 20260410

## 実験の目的

Run 011で特定されたdrift pattern（contains, is_product_of, is_reverse_of, is_isomer_of等の
化学構造関係）に基づいて、pre-compose filterを実装し、deep cross-domain発見の衛生を改善する。

## 主要な発見

### 候補数変化
- 総候補: 939 → 446 (▼493, 52.5%削減)
- Deep CD候補: 20 → 3 (▼17)

### ラベル分布変化（Deep CD候補）
- drift_heavy: 25.0% → 0.0% (改善)
- promising: 15.0% → 100.0% (改善)
- 除去効率: 29.4% (drift_heavy 5/17 除去)

### Promising候補への影響
- Promising候補損失: **0件**
- 全promising候補（VHL/HIF1A/LDHA カスケード）を保持

## filterの評価

1. `filter_relations` が最も効果的：drift_heavy 5件中 5件を除去
2. 化学構造関係 (contains/is_product_of/is_isomer_of) はdrift主因であり、filter対象として正当
3. `is_reverse_of` は weak_speculative候補（NADH/酸化還元チェーン）も除去するが、これらは
   化学的事実（r_Oxidation → is_reverse_of → r_Reduction）であり機構的仮説ではない

## 次ステップ推薦

1. Deep CD候補の絶対数がさらに少ない場合、`is_reverse_of` をfilterから外してweak_speculative
   を一部戻すことを検討（ただしdrift_heavy率の再確認が必要）
2. filter_generic_intermediatesの効果を独立して測定（現データではintermediate汎用ノードが少ない）
3. `min_strong_ratio` のチューニング（0.40が適切かを検証するために0.30/0.50も試す）
4. Run 013: filterを固定してHypothesis validation（H1''/H3''の再検証、フィルター後の公正テスト）
