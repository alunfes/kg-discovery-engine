# オペレータ定義

KGオペレータは `KnowledgeGraph → KnowledgeGraph` または `KnowledgeGraph → List[HypothesisCandidate]` の変換関数。

---

## align

**シグネチャ**: `align(kg1: KG, kg2: KG, threshold: float) → AlignmentMap`

**説明**: 2つのKGのノードをラベル類似度に基づいてマッピングする。

**アルゴリズム**（最小ヒューリスティック版）:
1. 全ノードペアの文字列類似度を計算（Jaccard / overlap係数）
2. threshold以上のペアをアライメント候補とする
3. 1対1マッピングとなるよう貪欲法で選択

**入力**:
- `kg1`, `kg2`: 対象KG
- `threshold`: 類似度閾値（デフォルト 0.5）

**出力**: `{node_id_in_kg1: node_id_in_kg2}` のマッピング辞書

**注意**: 完全一致のみを扱うシンプル版（v0）。類似度計算は将来拡張ポイント。

---

## union

**シグネチャ**: `union(kg1: KG, kg2: KG, alignment: AlignmentMap) → KG`

**説明**: 2つのKGをマージして1つのKGを生成する。

**アルゴリズム**:
1. アライメント済みノードは同一ノードとして扱う
2. 未アライメントノードはそのまま追加
3. 全エッジを統合（重複エッジは1本に）

**出力**: マージされたKG

---

## difference

**シグネチャ**: `difference(kg1: KG, kg2: KG, alignment: AlignmentMap) → KG`

**説明**: kg1に存在してkg2に存在しないノード・エッジを抽出する。

**用途**: ドメイン固有の概念・関係を発見する（kg1のユニーク部分を仮説生成の素材にする）

**出力**: kg1固有の部分KG

---

## compose

**シグネチャ**: `compose(kg: KG) → List[HypothesisCandidate]`

**説明**: KGの推移的関係を辿って仮説を生成する。

**アルゴリズム**:
1. 全ノードペア (A, C) について、A→B→C のパスを探索
2. A→C の直接エッジが存在しない場合、「A と C には関連がある」という仮説候補を生成
3. provenanceにパス情報を記録

**出力**: `HypothesisCandidate` のリスト

**例**:
```
KG: protein_X --inhibits--> enzyme_Y --catalyzes--> reaction_Z
仮説: protein_X は reaction_Z を間接的に制御する可能性がある
```

---

## evaluate

**シグネチャ**: `evaluate(candidates: List[HypothesisCandidate], kg: KG, rubric: EvaluationRubric) → List[ScoredHypothesis]`

**説明**: 仮説候補を評価ルーブリックに基づいてスコアリングする。

**評価次元**: `evaluation_rubric.md` 参照

**出力**: スコア付き仮説のリスト（スコア降順でソート）

---

## analogy-transfer

**シグネチャ**: `analogy_transfer(source_kg: KG, target_kg: KG, alignment: AlignmentMap) → List[HypothesisCandidate]`

**説明**: source_KGの関係パターンをtarget_KGに転写して仮説を生成する。

**ステータス**: **PLACEHOLDER** — v0では未実装。仕様のみ定義。

**アルゴリズム（予定）**:
1. source_KGで特徴的な関係パターンを抽出
2. alignmentを介してtarget_KGの対応ノードを特定
3. パターンを転写した仮説を生成

---

## belief-update

**シグネチャ**: `belief_update(hypotheses: List[ScoredHypothesis], evidence: KG) → List[ScoredHypothesis]`

**説明**: 新しいエビデンスKGに基づいて既存の仮説スコアを更新する（Bayesian的更新）。

**ステータス**: **PLACEHOLDER** — v0では未実装。仕様のみ定義。

**アルゴリズム（予定）**:
1. evidenceKGに仮説を支持/反証するエッジがあるか確認
2. evidence supportスコアを更新
3. 全体スコアを再計算

---

## オペレータ連鎖図

```
[KG_A]  [KG_B]
   |       |
   +--align-+
       |
    [map]
       |
   +---+---+
   |       |
union   difference
   |       |
[KG_merged] [KG_diff]
       |
    compose
       |
[candidates_raw]
       |
   analogy-transfer  ← (optional, placeholder)
       |
   evaluate
       |
[candidates_scored]
       |
   belief-update  ← (optional, placeholder)
       |
[final_output]
```
