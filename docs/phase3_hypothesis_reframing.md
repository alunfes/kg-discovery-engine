# Phase 3: 仮説の再定式化

## Phase 2の結論（Source of Truth）

| 仮説 | Phase 2結果 | 解釈 |
|------|-----------|------|
| H1 | FAIL (6 Run通じて) | toy dataの橋梁構造が既に豊かでmulti-opの普遍的優位性なし |
| H2 | 部分支持 | ノイジー条件下でevaluator頑健性を確認（劣化 < 20%）|
| H3 | ボーナス依存PASS | cross-domainボーナス除去→ratio=1.0（内在的新規性未証明）|
| H4 | 条件付き支持 | mixed-hop KGでSpearman改善（engineered条件）|

## 再定式化の根拠

Phase 2の根本問題:
1. toy dataのbio↔chemブリッジが既に「bridge-rich」 → H1が飽和
2. noveltyボーナスがH3を設計で担保していた（tautological）
3. H4の証明が人工的なmixed-hop KGに依存（実データで一般化未確認）

---

## H1' の定式化

### 原仮説 (H1)
> multi-op pipelineはsingle-op composeより常に10%以上高スコアを生成する

### 再定式化 (H1')
> **multi-op pipelineはsparse-bridge条件または同一ドメイン内でのみ、single-opが到達できない仮説候補を生成する（普遍的ではない）**

### 操作的定義

```
H1'_evidence = (
    unique_to_multi_op_count(C) > 0  AND
    unique_to_multi_op_count(A) == 0 AND
    unique_to_multi_op_count(B) == 0
)
```

説明:
- `unique_to_multi_op_count`: multi-opが生成し、single-opが生成しない(subject, object)ペア数
- 条件C（sparse bridge）でのみ確認できれば、bridge依存性を部分支持

### 評価3軸
1. **Quality** (Cohen's d): スコア分布の差
2. **Reachability** (unique_count): single-opに到達不能な候補数  
3. **Uniqueness** (contribution_rate): multi-op候補中のunique割合

---

## H3' の定式化

### 原仮説 (H3)
> cross-domain操作はsame-domain操作より20%以上noveltyが高い（ボーナス込み）

### 再定式化 (H3')
> **cross-domain操作はdomain距離が構造的に意味のある場合にのみ、同一ドメイン操作と比較して真の新規性を生む**

### 操作的定義

No-bonus approach:
```
H3'_evidence = (
    cross_domain_novelty_no_bonus > same_domain_novelty AND
    structural_distance_detected  # hop数または別プロキシで確認
)
```

### 構造的距離のプロキシ候補
1. **Mean hop count**: cross-domainパスの平均ホップ数 > same-domain平均
2. **Relation type heterogeneity**: cross-domainパスが使うrelation種別の多様性
3. **Domain mixing ratio**: パス中にドメイン境界を渡る割合

---

## 評価フレームワーク変更点

Phase 2 → Phase 3:

| 項目 | Phase 2 | Phase 3 |
|------|---------|---------|
| 主要指標 | mean_total, Cohen's d | unique_to_multi_op（最重要）|
| noveltyボーナス | True（H3 PASS要因）| False（常にFalse）|
| グラフ構造 | toy data (合成) | Wikidata-derived (実体) |
| 条件設計 | C1/C2/C3固定 | A/B/C/D (bridge density変化)|
| H1の閾値 | +10%スコア差 | unique_to_multi > 0 |

---

## Phase 3 Run 1 の実験設計

### 4条件

```
A: bio-only (bridge_density=0)     → multi-op degenerate, unique=0 expected
B: chem-only (bridge_density=0)    → same
C: bio+chem sparse (≈5%)           → alignment creates implicit bridges
D: bio+chem dense (≈15%)           → explicit bridges dominate
```

### H1'の予測（Phase 3開始前）

```
Predicted:
  unique_A = 0, unique_B = 0   (same-domain, no cross-domain gain)
  unique_C > 0                  (alignment finds implicit bridges)
  unique_D ≥ unique_C           (dense bridges + alignment = more paths)
```

### H3'の予測

```
Predicted:
  cross_hops_C > same_hops_C   (cross-domain paths longer in sparse bridge)
  novelty_cross ≈ novelty_same  (no bonus, pure structural signal)
```
