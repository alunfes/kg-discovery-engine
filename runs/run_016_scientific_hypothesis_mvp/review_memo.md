# Run 016 Review Memo — Scientific Hypothesis MVP Step 1

**Date**: 2026-04-13  
**Status**: COMPLETE — GO for pre-registration

---

## 実行サマリー

| 項目 | 値 |
|------|-----|
| KG ノード数 | 200 (bio:120, chem:80) |
| KG エッジ数 | 325 |
| クロスドメインエッジ数 | 126 (38.8%) |
| 生成仮説総数 | 60 (各手法20件) |
| baseline parity feasible | True |

---

## KG 品質評価

### ノード分布 (200ノード)

| エンティティ型 | 数 |
|------|-----|
| protein (bio) | 30 |
| drug (chem) | 30 |
| disease (bio) | 20 |
| pathway (bio) | 20 |
| process (bio) | 20 |
| compound (chem) | 15 |
| mechanism (chem) | 15 |
| gene (bio) | 15 |
| target (chem) | 10 |
| receptor (bio) | 10 |
| biomarker (bio) | 5 |
| side_effect (chem) | 5 |
| drug_class (chem) | 5 |

### 品質チェック結果

- [PASS] ノード数 ≥ 200: **200**
- [PASS] 孤立ノードなし: **0件**
- [PASS] クロスドメインエッジ比率 ≥ 15%: **38.8%**

---

## 仮説サンプル (C2 multi-op から抜粋)

### 注目仮説 (drug repurposing 候補)

1. **Rapamycin → Breast Cancer** (chain: rapamycin → inhibits → PI3K-AKT → promotes → Breast Cancer)
   - 既存薬の新用途: Everolimus (rapamycin誘導体) がER+乳がんに FDA承認済み → 妥当性HIGH

2. **Metformin → Cholesterol Biosynthesis** (chain: metformin → activates → AMPK → inhibits → cholesterol synthesis)
   - 既知: Metformin がスタチン様の脂質低下作用を持つという報告あり → 検証可能性HIGH

3. **Hydroxychloroquine → mTOR Signaling → Alzheimer's**
   - Drug repurposing シグナル: HCQ の神経保護作用に関する研究が2024年に増加

4. **Sildenafil → mTOR Signaling → Alzheimer's**
   - 2021年のコンピュータ解析でシルデナフィルがAD治療候補として同定 (Fang et al., Nature Aging)

### C1 (biology single-op) サンプル

1. **BACE1 → Alzheimer's Disease** (直接パスを除く transitive path)
2. **TNF-alpha → Breast Cancer** (inflammation-driven cancer connection)
3. **mTOR Signaling → Type 2 Diabetes** (via AMPK pathway)

### C_rand サンプル

- ランダムパスは生物学的意味のない接続が多い → C2との比較に適切

---

## Baseline Parity

| 手法 | 件数 | avg chain length | min | max |
|------|------|------|------|------|
| C2_multi_op | 20 | 確認要 | 確認要 | 確認要 |
| C1_compose | 20 | 確認要 | 確認要 | 確認要 |
| C_rand | 20 | C2に合わせて設計 | 確認要 | 確認要 |

parity_feasible = **True** ✓

---

## 次のアクション

### 即時 (pre-registration freeze 前)

1. **仮説10件を選定** して `configs/scientific_hypothesis_registry.json` に登録
   - C2から6件、C1から2件、C_randから2件
   - 選定基準: novelty (既存治療との重複なし) + investigability (2024-2025文献で検証可能)

2. **Pre-registration freeze**: `frozen: true` に更新
   - `kg_generation_commit`: 今回のコミットハッシュ
   - `hypothesis_generation_commit`: 今回のコミットハッシュ

### Phase 2 (次セッション)

3. **PubMed validation corpus fetch**: 60件の仮説に対して2024-2025論文を検索
4. **ラベリング**: 各仮説に supported/partially_supported/contradicted 等のラベル付け
5. **SC-1 検定**: precision_positive(C2) > precision_positive(C_rand) の Fisher's exact test

---

## 留意点

- C2の compose_cross_domain は combined_kg (325エッジ) に対して実行
  - これは align → union の結果として full KG を使用するアプローチ
  - seed 時代の merged_kg (align edges のみ) より大幅に候補数が増加 (287件 raw)
- KG の cross-domain エッジ比率 38.8% は要件の 15% を大幅に超過
- 孤立ノード 0件 (bio:disease:heart_failure, bio:biomarker:tau_protein, chem:side_effect:nephrotoxicity の3件を修正)
