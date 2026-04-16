# P3: 新規性-Investigability トレードオフの定量化

**作成日**: 2026-04-14  
**ステータス**: 設計段階（追加実験不要、run_018 既存データの再分析）  
**前提**: run_018 の 210件（C2=70, C1=70, C_rand=70）に investigability ラベル付き

---

## 研究問い

cross-domain 仮説（C2）は bio-only（C1）より investigability が低い（0.914 vs 0.971）。  
この差は「新規性が高すぎる仮説は investigable でない」というトレードオフで説明できるか。  
もしそうなら、investigability が最も高い novelty の「sweet spot」はどこにあるか。

**分析の前提:**
- 新たな実験は不要。run_018 の既存データに novelty score を追加して分析する。
- 追加コスト: novelty score 計算スクリプトの実装のみ。

---

## Novelty Score の定義

### 3つの成分

#### 1. path_length
仮説生成に使った compose パスの hop 数。

| path_length | novelty 寄与 |
|-------------|-------------|
| 2-hop | low (0.0) |
| 3-hop | medium (0.5) |
| 4-hop 以上 | high (1.0) |

根拠: パスが長いほど、直接的な研究関係から遠い仮説が生成される。

#### 2. cross_domain_ratio
パス内の cross-domain エッジ（biology-chemistry 間）の割合。

```
cross_domain_ratio = cross_domain_edges / total_edges_in_path
```

- 値域: 0.0（pure bio-only）〜 1.0（全エッジが cross-domain）
- C1 の仮説: cross_domain_ratio = 0.0
- C2 の仮説: cross_domain_ratio > 0（align で生成された bridge を経由）

#### 3. entity_rarity
パス上のエンティティの PubMed 出現頻度の逆数（希少 entity ほど novel）。

```
entity_rarity = median(1 / pubmed_hit_count(entity)) for all entities in path
```

- pubmed_hit_count は run_018 の validation 時に取得済みのクエリ結果を再利用
- ゼロ除算対策: pubmed_hit_count = 0 のエンティティは hit_count = 0.5 として扱う

**注意:** entity_rarity の計算に追加の PubMed API クエリが必要な場合は省略し、
path_length + cross_domain_ratio の2成分で代替する。

### 統合 Novelty Score

```
combined_novelty = 0.4 * norm(path_length) 
                 + 0.4 * cross_domain_ratio 
                 + 0.2 * norm(entity_rarity)
```

重み付けの根拠:
- path_length と cross_domain_ratio を同等に重視（各 0.4）
- entity_rarity は補助指標として低めに設定（0.2）

重み付けは **P3 分析を開始する前に固定し、変更しない**（事後的な重み調整を防ぐ）。

---

## 分析計画

### Step 1: novelty score の付与

`runs/run_018_investigability_replication/output_candidates.json` の各仮説に対して、
上記の novelty score（3成分 + combined）を計算して付与する。

実装:
- スクリプト: `src/scientific_hypothesis/add_novelty_scores.py`
- 入力: `output_candidates.json` + KG データ (`bio_chem_kg_full.json`)
- 出力: `output_candidates_with_novelty.json`

### Step 2: novelty-investigability の関係を集計

novelty score をビン化して、各ビンの investigability rate を計算する。

```
ビン設定（combined_novelty）:
  [0.0, 0.2): low novelty
  [0.2, 0.4): medium-low novelty
  [0.4, 0.6): medium-high novelty
  [0.6, 0.8): high novelty
  [0.8, 1.0]: very high novelty
```

各ビンで計算:
- N（仮説数）
- investigated 数
- investigability rate
- 95% 信頼区間（Wilson interval）

### Step 3: 条件別（C2/C1/C_rand）の分析

同じビン集計を C2, C1, C_rand 別に行い、3条件の novelty 分布の違いを確認する。

期待: C1 の仮説は low novelty ビンに集中。C2 は medium〜high ビンに分散。

### Step 4: 可視化（テキストベース）

matplotlib は使用しない（Python 標準ライブラリのみ）。  
以下の形式で出力する:

**ASCII テーブル形式:**
```
novelty_bin | N  | investigated | inv_rate | 95%CI
[0.0, 0.2)  | 42 | 41           | 0.976    | [0.878, 0.997]
[0.2, 0.4)  | 68 | 63           | 0.926    | [0.836, 0.972]
...
```

**HTML 形式（ブラウザで確認用）:**
- 各ビンを横棒グラフで表現（HTML + CSS のみ、JavaScript なし）
- 出力先: `runs/run_018_investigability_replication/novelty_analysis.html`

### Step 5: Sweet Spot の特定

investigability rate が最も高いビンを「sweet spot」として特定する。

```
sweet_spot = argmax(investigability_rate) for bins with N >= 10
```

N < 10 のビンは統計的に不安定なため除外。

---

## 仮説と期待される結果

### 仮説: 逆U字型の関係

| Novelty | 予測 investigability | 理由 |
|---------|-------------------|------|
| 低 | 高（0.97+） | 既知の関係に近く、既存研究が豊富 |
| 中 | 最高（sweet spot） | 研究者が注目しているが、まだ未確定の領域 |
| 高 | 低（0.60〜） | 研究フロンティアを超えており、文献がほぼない |

**C1 が C2 より investigability が高い理由の説明:**
- C1（bio-only）の仮説は low〜medium novelty に集中
- C2（cross-domain）の仮説は medium〜high novelty に分散し、high novelty ゾーンが investigability を下げている

### 代替仮説: 関係がない

novelty と investigability に系統的な関係がない場合（フラットな分布）:
- C1 > C2 の差は novelty ではなく文献密度の構造的偏り（biology > chemistry）で説明される
- この場合、P1 の novelty_ceiling 条件は効果がない可能性が高い

---

## 「次に何を最適化すべきか」への接続

### P1 への接続

P3 の分析結果が P1 の `novelty_ceiling` 条件の T_high を決定する。

- sweet spot の上限（例: combined_novelty < 0.6）を T_high として使用
- P3 完了 → T_high を config に記録 → P1 novelty_ceiling を実装

P3 が完了するまで P1 の `novelty_ceiling` 条件は着手しない。

### 誘導戦略の提案

sweet spot が確認された場合、以下の方向性を提案できる:

1. **Novelty ターゲティング**: compose オペレータに「target novelty range」パラメータを追加
2. **Novelty フィルタリング**: 生成後に sweet spot 外の仮説を除外（P1 の novelty_ceiling と同じアプローチ）
3. **Operator 設計への反映**: align の bridge 深度を制限し、novelty を意図的に medium に誘導

---

## Pre-registration の必要性

**P3 は分析計画を事前登録することを推奨する（実験前ではなく分析前）。**

理由:
- novelty score の重み付け（0.4/0.4/0.2）を事後に変更してはならない
- ビン設定を結果に合わせて調整してはならない
- sweet spot の定義（argmax with N >= 10）を事後に変えてはならない

**登録すべき内容:**
1. novelty score の計算式と重み付け
2. ビン設定
3. sweet spot の定義と判定基準
4. N < 10 ビンの除外ルール

**登録タイミング:** `add_novelty_scores.py` を実装完了後、スクリプトを実行する前。

---

## 実装スコープ

| 作業 | 難易度 | 優先度 |
|------|-------|-------|
| novelty score 計算スクリプト | 低〜中 | 最優先（P1 novelty_ceiling の前提） |
| HTML 可視化 | 低 | 高 |
| P3 事前登録 | なし（文書作成のみ） | 最優先（スクリプト実行前） |
| entity_rarity 計算（追加 PubMed query が必要な場合） | 中 | 低（2成分で代替可） |

---

## やらないこと

- 追加実験（run_018 の 210件で十分）
- matplotlib やサードパーティライブラリの使用
- novelty score の重み付けを結果を見て調整する
- P3 結果が期待と異なった場合に「別の novelty 定義」を試す（1回限り）
