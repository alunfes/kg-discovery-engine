# Run 014 Review Memo — Relation Semantics Audit

**Date**: 2026-04-10  
**Run type**: Interpretation layer (no new experiments)

## 目的の達成状況

Run 014の目的は「関係型の解釈層を追加し、5候補の弱点をrelation semanticsの観点で一貫して説明できるようにすること」。

**達成度**: 全成功条件クリア

| 成功条件 | 結果 |
|---|---|
| 5候補の弱点がrelation semanticsで一貫説明できる | ✓ — 全てclass-level relation gapに収束 |
| 「どの候補がなぜweakly_novelか」が明確になる | ✓ — 4次元リスク評価で各候補の弱点を特定 |
| 論文にそのまま入れられるルール表ができる | ✓ — relation_semantics_table.csv + 5 interpretation rules |
| 既存の候補検証結果を覆さない | ✓ — addendumとして追記のみ |

## 主な発見

### 収束パターン: 全弱点がclass-level relation問題に帰着

B-1/B-2の方向問題、C-1のアーティファクト、C-2の区画化問題は表面的には異なって見えるが、
全て同じ根本原因から派生している：

**KGはrelation typeをclass levelで記述しており、instance-level (substrate-specific)な
化学的妥当性を検証しない。**

| 問題 | 候補 | 根本原因 |
|---|---|---|
| `r_OxidationNat → produces → fg_Catechol` が特定基質(AA)に不適用 | B-1, B-2 | reaction_class → fg_class produces |
| `r_Methylation → produces → fg_Piperidine` がdopamineに不適用 | C-1 | reaction_class → fg_class produces |
| 逆方向パス(COX→catechol vs catechol→COX) | B-1, B-2 | 方向性の明示なし |
| 細胞区画をまたぐパス(dopaminergic → serotonergic) | C-2 | cell-type annotationなし |
| `is_substrate_of`の方向的曖昧性 | C-2 | 関係型の意味論的未定義 |

### フィルター精度ギャップの特定

Run 012フィルターは `produces` を `_STRONG_MECHANISTIC` に含めた。
これは正しい（enzymeが特定代謝産物を生成する場合はmechanistically strong）。
しかし、`reaction_class → produces → fg_class` パターンを区別できない。

**C-1がフィルターを通過した理由**:
- `catalyzes`, `undergoes`, `produces` — 全て strong/permitted
- 化学的妥当性（methylation of dopamine → piperidine）は relation type だけでは検証不可能

この発見は、**フィルターの改善方向を具体的に示している**: `produces_specific`（基質特異的）
vs `produces_class`（汎化）を区別するKGアノテーションが必要。

## 論文への直接活用箇所

### Method section
`docs/candidate_interpretation_rules.md` の Rule 1 Table は
そのままMethodのpath interpretation subsectionに使える。

### Discussion
`docs/candidate_self_validation.md` の「Convergent Pattern」段落は
Discussion結論部に流し込める。

### Limitations
`docs/threats_to_validity.md` T5.1-T5.4 は
既存のLimitations節(T1-T4)に続ける形でそのまま使える。

### Case Study
`docs/case_study_notes.md` の「Run 014 Addendum」段落は
Case Study節の末尾結論として使える。

## 次ステップ推薦

1. **Paper writing優先**: Method + Discussion + Limitationsの3節を draft
   - 今回追加した全ドキュメントが直接素材になる状態
   
2. **C-1化学検証**: `r_Methylation → produces → fg_Piperidine` のWikidata出典確認
   - Wikidata Q番号を特定 → synthetic chemistry vs biochemistry を判定

3. **B-1/B-2文献確認**: `r_OxidationNat → produces → fg_Catechol` のAA特異的検証
   - ChEBI/LIPID MAPSでAA酸化産物にcatechol構造が含まれるか確認

4. **LaTeX変換**: `docs/paper_skeleton.md` → LaTeX (Table 2として relation_semantics_table.csv)
