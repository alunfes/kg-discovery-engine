# 入力データサマリー — Run 001

## 使用KG

### biology KG

| 属性 | 値 |
|------|-----|
| ノード数 | 8 |
| エッジ数 | 8 |
| ドメイン | biology |

**ノード**: ProteinA, ProteinB, EnzymeX, EnzymeY, Reaction1, Reaction2, CellMembrane, Nucleus

**主要な関係**:
- ProteinA --inhibits--> EnzymeX
- ProteinB --activates--> EnzymeX
- EnzymeX --catalyzes--> Reaction1
- Reaction1 --produces--> ProteinB（フィードバックループ）
- ProteinA --binds_to--> CellMembrane --contains--> EnzymeY

### chemistry KG

| 属性 | 値 |
|------|-----|
| ノード数 | 8 |
| エッジ数 | 8 |
| ドメイン | chemistry |

**ノード**: CompoundP, CompoundQ, CatalystM, CatalystN, ReactionAlpha, ReactionBeta, PolymerZ, SolventS

**主要な関係**:
- CompoundP --inhibits--> CatalystM（biologyのProteinA--inhibits-->EnzymeXと構造的に同型）
- CatalystM --accelerates--> ReactionAlpha
- ReactionAlpha --yields--> CompoundQ（フィードバックループ）

## アライメント結果（C2）

biology + chemistry の align（threshold=0.4）でのマッチング：

| 期待 | 実際 |
|------|------|
| bio:enzyme_X ↔ chem:catalyst_M | アライメントなし（ラベルが異なりすぎる） |

**観察**: 現行の文字列Jaccard類似度では、概念的に対応するノード（enzyme ↔ catalyst）がアライメントされなかった。
これは予想内 — v0のシンプルヒューリスティックの限界。
