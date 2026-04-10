# Run 011 質的レビュー — Deep Cross-Domain候補20件

**Date**: 2026-04-10  
**Source**: Run 010 output_candidates_reranked.json (Condition C, P4 pipeline)  
**対象**: path_length ≥ 3 かつ is_cross_domain = True の候補

## ラベル分布

| ラベル | 件数 | 割合 |
|--------|------|------|
| promising | 3 | 15% |
| weak_speculative | 12 | 60% |
| drift_heavy | 5 | 25% |

## Promising候補（3件）

いずれも VHL/HIF1A/LDHA 制御カスケードを軸にした候補。

| ID | パス | Hop数 |
|----|------|-------|
| H0618 | g_VHL→encodes→VHL→inhibits→HIF1A→activates→LDHA→requires_cofactor→NADH→undergoes→r_Oxidation | 5 |
| H0293 | VHL→inhibits→HIF1A→activates→LDHA→requires_cofactor→NADH→undergoes→r_Oxidation | 4 |
| H0517 | g_HIF1A→encodes→HIF1A→activates→LDHA→requires_cofactor→NADH→undergoes→r_Oxidation | 4 |

**科学的妥当性**: VHL腫瘍抑制因子はHIF1Aを制御し、HIF1AはLDHA（乳酸脱水素酵素A）を
活性化してWarburg効果を促進する。LDHAはNADHコファクターを必要とし、NADHの酸化は
グルコース代謝と密接に関連する。これらは実験的に検証可能な生物学的仮説を形成する。

## Drift Heavy候補（5件）の共通パターン

### パターン1: 化学構造関係チェーン
```
bio:m_AMP → is_product_of → chem:ATP → contains → chem:Ribose → is_precursor_of → chem:Deoxyribose
bio:m_AMP → is_product_of → chem:ATP → is_isomer_of → chem:GTP → contains → chem:Guanine
```
`is_product_of`, `contains`, `is_isomer_of` は分子構造・化学反応の記述であり、
生物学的機構的仮説を生まない。化学KGの構造情報がcomposeで単純展開されたもの。

### パターン2: アミノ酸連続前駆体チェーン
```
bio:m_3PG → is_precursor_of → bio:aa_Ser → is_precursor_of → bio:aa_Gly → contains → chem:fg_Amino
bio:PGAM1 → catalyzes → bio:m_3PG → is_precursor_of → bio:aa_Ser → is_precursor_of → bio:aa_Gly → contains → chem:fg_Amino
```
`is_precursor_of` の連続出現（アミノ酸生合成チェーン）+ `contains`（官能基）。
3PG→Ser→Gly→アミノ基/カルボキシ基 というパターンの変形が多数生成されている。

## Drift Triggerの特徴（このデータセット固有の知見）

Run 009/008で想定していたdrift pattern（relates_to, associated_with等の汎用connector）は
このデータセットには出現しなかった。代わりに：

| 関係タイプ | ドメイン | 問題 | 件数 |
|----------|---------|------|------|
| contains | 化学 | 分子構成成分 → 構造的事実のみ | 4 |
| is_product_of | 化学/代謝 | 代謝産物関係 → 方向性なし | 2 |
| is_reverse_of | 化学反応 | 反応逆方向 → 機構的意味なし | 1 |
| is_isomer_of | 化学 | 異性体関係 → 構造的事実 | 1 |

**is_precursor_of の連続出現**がbigram最頻パターン（生合成チェーンの繰り返し）。

## Run 012への推薦フィルター

詳細は `runs/run_011_20260410_qualitative_review/filter_recommendations.md` 参照。

### 最優先フィルター（効果大）
```python
_FILTER_RELATIONS_CORE = frozenset({
    "contains", "is_product_of", "is_reverse_of", "is_isomer_of",
})
```
これで drift_heavy 5件の大部分を除去できると推定。

### 補完フィルター（is_precursor_of重複ガード）
- 同じ関係タイプの連続出現を検出してパスを棄却
- 実装: `_has_consecutive_repeat()` をcompose内部に追加

### 期待効果
- Drift_heavy: 25% → <10%
- Promising: 15% → >40%（品質の高い候補が残る）
- Deep cross-domain候補の総数は減るが、シグナル品質が向上

## 結論

- 20件中3件(15%)が科学的に意味のある仮説を含む
- 5件(25%)はsemantic driftが支配的（structural/chemical expansion）
- 12件(60%)は弱いが完全にナンセンスではない
- Drift原因は想定外の化学構造関係（containsなど）とアミノ酸前駆体チェーン
- Run 012のpre-compose filterで品質向上が見込める
