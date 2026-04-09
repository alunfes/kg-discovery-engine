# Input Summary — Run 003

**日付**: 2026-04-10

## 入力KGサマリー

### biology KG (拡張版)
- ノード数: 12（Run 002: 8）
- エッジ数: 14（Run 002: 8）
- 追加ノード: ProteinC, EnzymeZ, Reaction3, MetaboliteM
- 追加エッジ: 6件（inhibits/catalyzes/produces 系の strong-relation）

### chemistry KG (拡張版)
- ノード数: 12（Run 002: 8）
- エッジ数: 14（Run 002: 8）
- 追加ノード: CompoundR, CatalystL, ReactionGamma, IntermediateI
- 追加エッジ: 6件（accelerates/yields/facilitates 系の strong-relation）

### bio_chem_bridge KG (新規: Run 003)
- ノード数: 15（bio 6 + chem 6 + bridge 3）
- エッジ数: 21（bio内部 6 + chem内部 6 + cross-domain 9）
- cross-domainエッジ: 9件（binds/catalyzes/activates/precursor_to/inhibits/modulates/analogous_to/related_to/involves）

### noisy biology KG (H2用)
- 30%ノイズ: 14エッジ中 10件保持（ラベルノイズ3件）
- 50%ノイズ: 14エッジ中 7件保持（ラベルノイズ3件）
- ランダムシード: 42（決定論的）

## アライメント (C2 bio+chem)
- bio:enzyme_X ↔ chem:catalyst_M（synonym: enzyme↔catalyst）
- bio:enzyme_Y ↔ chem:catalyst_N（synonym: enzyme↔catalyst）
- bio:protein_A ↔ chem:compound_P（synonym: protein↔compound）
- bio:protein_B ↔ chem:compound_Q（synonym: protein↔compound）
- **合計: 4件アライメント** (Run 002と同じ)

## 変更点サマリー
| ファイル | 変更内容 |
|--------|---------|
| src/kg/toy_data.py | biology/chemistry KG拡張 + build_bio_chem_bridge_kg() + build_noisy_kg() 追加 |
| src/pipeline/run_experiment.py | H2/H3/H4検証ロジック追加、C2_bridge条件追加 |
| src/pipeline/compare_conditions.py | H3評価方式を hypothesis-level に変更 |
