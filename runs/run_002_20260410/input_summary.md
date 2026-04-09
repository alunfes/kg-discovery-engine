# Input Summary — Run 002

## KGデータセット (変更なし)

### biology KG
- ノード数: 8 (protein_A, protein_B, enzyme_X, enzyme_Y, reaction_1, reaction_2, cell_membrane, nucleus)
- エッジ数: 8 (inhibits, activates, catalyzes, produces, binds_to, contains, encodes)
- ドメイン: "biology"

### chemistry KG
- ノード数: 8 (compound_P, compound_Q, catalyst_M, catalyst_N, reaction_alpha, reaction_beta, polymer_Z, solvent_S)
- エッジ数: 8 (inhibits, activates, accelerates, yields, dissolves_in, facilitates, produces)
- ドメイン: "chemistry"

## アライメント (変更あり — 今回の主要改善)

### Run 001 vs Run 002 の比較

| 項目 | Run 001 | Run 002 |
|------|---------|---------|
| アライメント数 | 0件 | 4件 |
| マッチング手法 | 文字列Jaccard (CamelCase未対応) | CamelCase分割 + synonym-bridge検出 |

### Run 002 のアライメント結果 (bio → chem)
- bio:protein_A ↔ chem:compound_P (protein↔compound synonym bridge, sim=0.5)
- bio:protein_B ↔ chem:compound_Q (protein↔compound synonym bridge, sim=0.5)
- bio:enzyme_X ↔ chem:catalyst_M (enzyme↔catalyst synonym bridge, sim=0.5)
- bio:enzyme_Y ↔ chem:catalyst_N (enzyme↔catalyst synonym bridge, sim=0.5)

### アライメントが生み出すcross-domainエッジ

`union` 後のマージKGでは、アライメントされたノードが統合され、
chem側のエッジがbioノードに付け替えられる:

- bio:enzyme_X → accelerates → chemistry::chem:reaction_alpha (chem側エッジが付与)
- bio:enzyme_Y → accelerates → chemistry::chem:reaction_beta (chem側エッジが付与)
- chemistry::chem:reaction_alpha → yields → bio:compound_Q (bio:protein_B にアライン)

これにより、bio→chemまたはchem→bioを跨ぐ仮説パスが生成可能になった。

## スコアリング変更

### _score_plausibility (新規: relation種別ボーナス)
- 強い関係 (inhibits/activates/catalyzes/produces/encodes/accelerates/yields/facilitates): 全て強い場合 +0.1
- 弱い関係 (belongs_to/runs_over/contains 等): ボーナスなし

### _score_novelty (Run 001から変更なし — ただし今回初めて発動)
- cross-domain仮説: base 0.8 + bonus 0.2 = 1.0
- same-domain仮説: base 0.8 (known edge は 0.2)
