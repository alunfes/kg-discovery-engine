# Phase 5: Labeling Protocol

## 目的

生成された仮説に対して、将来 corpus（validation period: 2024-01-01〜2025-12-31）の文献を照合し、  
5分類ラベルを付与するための手順と判定基準を定義する。

---

## 1. 5ラベルの具体定義

### `supported`

**定義**: validation corpus 内の 1 本以上の文献が、仮説の中心的な関係（subject–relation–object）を  
**直接の研究対象として実験的・臨床的・計算的に確認**している。

**必要条件**:
- 文献が対象の関係を「結論」または「主要知見」として記述している
- 仮説の subject と object が文献中で同じ概念として扱われている（表現ゆれは許容、別概念は不可）
- 仮説の relation 方向が文献と一致している（A→B vs B→A は別仮説として扱う）

**例**:
- 仮説: "compound_metformin inhibits complex_I_of_mitochondria"
- 文献: "Metformin inhibits mitochondrial Complex I activity, contributing to its anti-diabetic effect"
- → `supported`

---

### `partially_supported`

**定義**: validation corpus に関連する知見はあるが、仮説の全条件を満たしていない。以下のいずれか:

1. 仮説の一部の条件のみ確認（例：A→B は確認されたが B→C は未確認で A→C が仮説）
2. 間接的証拠のみ（例：関連する異なる化合物での実験結果）
3. 仮説より粒度が粗い・細かい文献（例：化合物クラス全体での報告 vs 特定化合物の仮説）
4. in vitro のみで in vivo は未確認（仮説が病態に言及している場合）

**例**:
- 仮説: "compound_X inhibits protein_Y in disease_Z"
- 文献: "compound_X analogue inhibits protein_Y" （同一化合物ではない）
- → `partially_supported`

---

### `contradicted`

**定義**: validation corpus に、仮説の中心的な関係を**明示的に否定する**文献がある。

**必要条件**:
- 文献が当該関係の不在・逆方向・有意でないことを「結論」として記述している
- 技術的限界による「検出できなかった」ではなく、「存在しない」「効果がない」という知見

**例**:
- 仮説: "compound_Y activates pathway_Z"
- 文献: "compound_Y showed no activation of pathway_Z in multiple assays"
- → `contradicted`

---

### `investigated_but_inconclusive`

**定義**: validation corpus で仮説の関係が実験・調査されたが、支持も否定も明確にされなかった。

1. Replication failure（他グループが再現できなかった）
2. Mixed results（複数文献で矛盾する結果）
3. 統計的有意差なし（p > 0.05 だが検出力も低い）
4. 効果の方向は示唆されるが定量的に不十分

**例**:
- 仮説: "gene_A regulates protein_B expression"
- 文献1: "gene_A knockdown showed 1.3x increase in protein_B (p=0.08)"
- → `investigated_but_inconclusive`

---

### `not_investigated`

**定義**: validation corpus で仮説の keyword・概念が**検索で登場しない**、または登場しても仮説の検証は試みられていない。

**注意**: これは仮説の「失敗」ではない。以下のどれかを意味する:
- 仮説が先進的で研究コミュニティがまだ到達していない
- corpus 期間（2024-2025）が短すぎる
- corpus のカバレッジが不完全

**例**:
- 仮説: "enzyme_X catalyzes novel reaction in pathway_Y" （既存文献にない仮説）
- 検索結果: 関連論文なし
- → `not_investigated`

---

## 2. ラベリング手順

### Step 1: キーワード抽出（自動）

`scripts/run_scientific_hypothesis_evaluation.py` が各仮説から検索クエリを自動生成:

```python
query = f"{subject_label} AND {object_label} AND {relation_keyword}"
# 例: "metformin AND complex_I AND inhibit*"
```

### Step 2: 候補文献の絞り込み（半自動）

validation corpus の JSONL を `query` でフィルタリングし、候補文献リストを生成（最大 20 件/仮説）。  
フィルタリングは単純な文字列マッチ（lower-case, stemming なし、ただし `*` をワイルドカード扱い）。

### Step 3: 人手ラベリング（手動）

labeler が候補文献の title + abstract を読み、5分類の中から 1 つを選択。  
判定根拠となる文献の PMID/arXiv ID を最大 3 件記録する。

**判断フロー**:
```
候補文献が存在するか？
├── No → not_investigated
└── Yes → 仮説の中心的関係が研究対象になっているか？
            ├── No → not_investigated
            └── Yes → 結論が明確か？
                        ├── 明確に支持 → supported
                        ├── 部分的支持 → partially_supported
                        ├── 明確に否定 → contradicted
                        └── 不明瞭・矛盾 → investigated_but_inconclusive
```

### Step 4: ラベルの記録

`runs/run_sci_NNN_YYYYMMDD/labels.json` に保存:

```json
{
  "hypothesis_id": "C2_001",
  "label": "supported",
  "confidence": "high",
  "supporting_refs": ["PMID:38012345", "arXiv:2402.01234"],
  "labeler": "primary",
  "notes": "Direct replication of the proposed inhibition"
}
```

---

## 3. 「同一仮説」の判定基準

同一仮説とは、以下の3条件をすべて満たすもの:

1. **subject が同一概念**: 表現ゆれは許容（"metformin" = "Metformin" = "DMNH" は同一、"metformin" ≠ "phenformin"）
2. **object が同一概念**: 同上
3. **relation の方向と意味が同一**: "inhibits" = "blocks" = "suppresses"（synonymous relation）、ただし "inhibits" ≠ "activates"

**Method 間の重複**: 同一仮説が複数 method から生成された場合:
- C2 の仮説を「正」として採用
- 他 method の同一仮説を除外し、除外数を報告
- ラベルは採用仮説（C2）に付与

**C2 内の重複**: 同一 subject-relation-object が C2 内で複数生成された場合、スコアが高い方を残す。

---

## 4. 近縁表現・粒度違いの扱い

### 粒度の違い

| 仮説の粒度 | 文献の粒度 | ラベル |
|-----------|----------|--------|
| 特定化合物 | 同一化合物クラス全体 | `partially_supported` |
| 化合物クラス全体 | 特定化合物 | `partially_supported` |
| in vitro 想定 | in vivo 確認 | `supported`（より強い証拠） |
| 分子レベル | 細胞レベル | `partially_supported` |

### Relation の近縁表現

以下の relation グループは「同一 relation」として扱う（synonym grouping）:

```python
RELATION_SYNONYMS = {
    "inhibits": {"blocks", "suppresses", "reduces", "downregulates", "antagonizes"},
    "activates": {"induces", "upregulates", "promotes", "stimulates", "agonizes"},
    "binds_to": {"interacts_with", "associates_with", "complexes_with"},
    "catalyzes": {"converts", "transforms", "mediates_reaction"},
    "treats": {"ameliorates", "reduces_symptoms_of", "therapeutic_for"},
}
```

---

## 5. Ambiguity Handling Rule

**原則**: 曖昧な場合は保守的にダウングレードする（conservative downgrade）。

| 状況 | ルール |
|------|--------|
| `supported` か `partially_supported` か迷う | `partially_supported` を選ぶ |
| `partially_supported` か `not_investigated` か迷う | `not_investigated` を選ぶ |
| `contradicted` か `investigated_but_inconclusive` か迷う | `investigated_but_inconclusive` を選ぶ |
| 文献が見つかったが読む時間がない | ラベルを付けず `pending` として残す（後で処理） |

**理由**: conservative downgrade は precision の underestimate につながるが、method 間で系統的に適用されるため相対比較は有効。overestimate よりも安全。

---

## 6. Double Review と Adjudication

### Double Review サンプリング

全仮説の **20%** を second labeler が独立ラベリングする（`scientific_hypothesis_registry.json` で設定）。  
サンプリングは method・label の層別なし、単純ランダム（seed = 42）。

### Inter-labeler Agreement の測定

Cohen's κ を計算し報告する:
- κ ≥ 0.70: 許容可能な一致度
- 0.50 ≤ κ < 0.70: labeling protocol の改訂を検討
- κ < 0.50: protocol 改訂後に再ラベリング

**MVP では**: second labeler が確保できない場合、同一 labeler が 2 週間間隔で再ラベリングし自己一致率を測定する（self-agreement）。

### Adjudication Rule

primary と secondary が不一致の場合:

1. **conservative downgrade ルールを適用**: より保守的なラベルを採用
2. **例外**: 両者の判断に根拠文献の相違がある場合は文献を照合し決定
3. **解決不能な場合**: `adjudicated_uncertain` フラグを付け、感度分析に含める

---

## 7. ラベリング例

### Example 1

**仮説**: `C2_012: compound_aspirin inhibits enzyme_COX2 in disease_inflammation`  
**検索クエリ**: `aspirin AND COX2 AND inhibit*`  
**候補文献**: PMID:38001234 "Aspirin acetylates and irreversibly inhibits COX-2, blocking prostaglandin synthesis in inflammatory conditions"  
**ラベル**: `supported`  
**根拠**: 仮説の全要素（aspirin, COX2 inhibition, inflammation context）が直接確認されている

---

### Example 2

**仮説**: `C1_compose_007: protein_AMPK activates pathway_autophagy in disease_neurodegeneration`  
**検索クエリ**: `AMPK AND autophagy AND neurodegeneration`  
**候補文献**: PMID:38005678 "AMPK activation promotes autophagy in hepatic cells"（肝細胞の研究、神経変性ではない）  
**ラベル**: `partially_supported`  
**理由**: AMPK→autophagy 部分は支持されているが、neurodegeneration の文脈が欠如

---

### Example 3

**仮説**: `C_rand_023: compound_resveratrol inhibits protein_NF_kB in disease_cancer`  
**検索クエリ**: `resveratrol AND NF-kB AND inhibit*`  
**候補文献**: PMID:38009012 "Resveratrol failed to inhibit NF-κB activity in multiple cancer cell lines (n=8, p=0.43)"  
**ラベル**: `contradicted`  
**根拠**: 明示的に否定する実験結果

---

### Example 4

**仮説**: `C2_031: enzyme_FAS catalyzes reaction_novel_lipid_synthesis in disease_obesity`  
**検索クエリ**: `FAS AND lipid synthesis AND obesity`  
**候補文献**: なし（2024-2025 期間の文献でヒットなし）  
**ラベル**: `not_investigated`  
**注記**: 仮説が先進的か corpus が薄いかは不明。追加 corpus での再検証を推奨。

---

## 8. ラベリング作業の工数見積もり

| タスク | 工数（MVP: 80仮説） |
|--------|-------------------|
| キーワード検索（自動） | 〜10分 |
| 候補文献絞り込み確認 | 〜30分 |
| 人手ラベリング（80件 × 5分/件） | 〜400分（6.5時間） |
| Double review（16件 × 5分/件） | 〜80分 |
| Adjudication（不一致分 × 10分/件） | 〜50分（5件想定） |
| **合計** | **〜9時間（1-2日）** |
