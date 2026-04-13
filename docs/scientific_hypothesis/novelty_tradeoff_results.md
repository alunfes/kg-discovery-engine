# P3: Novelty-Investigability Tradeoff — Results

**Date**: 2026-04-14  
**Run**: run_019_novelty_tradeoff_analysis  
**Data**: run_018_investigability_replication (N=210)

---

## 1. 逆U字パターンの有無

**結果: 逆U字なし。**

Novelty が高いほど investigability は低下する単調減少パターンを観察。  
Fisher 検定（高 novelty ≥0.6 vs 低 novelty <0.4）: p = 0.997（非有意）。

| Novelty ビン | Overall inv. rate | n |
|-------------|------------------|---|
| 0.0–0.2 | 1.000 | 2 |
| 0.2–0.4 | 0.952 | 21 |
| 0.4–0.6 | 0.978 | 45 |
| 0.6–0.8 | 0.840 | 75 |
| 0.8–1.0 | 0.672 | 67 |

逆U字は支持されないが、**novelty ceiling**（0.8 超で investigability が急落）は明確に存在。

---

## 2. Sweet Spot の範囲

**Sweet spot: combined_novelty 0.4–0.8**

- Novelty 0.4–0.6 ビン: investigability 0.978（overall）
- Novelty 0.6–0.8 ビン: investigability 0.840（overall）、C2 単独では 1.000

Novelty ≥0.8 で investigability が 0.672（overall）、C_rand で 0.273 に低下。  
この "過高 novelty" ゾーン（≥0.8）は entity の文献密度が低すぎ、PubMed 検索で literature を見つけられない仮説が多数を占める。

---

## 3. P1 novelty_ceiling 条件への入力: T_high 推奨値

**T_high = 0.75**

根拠:
- Novelty 0.6–0.8 ビン（C2）: investigability 1.000 → 許容レンジ
- Novelty 0.8+ ビン（C_rand）: investigability 0.273 → 許容不可
- 0.75 を上限とすることで「高 novelty かつ investigable」を最大化

適用時の注意: C2 70 件中 25 件（36%）が novelty <0.75 であり、フィルタ後の件数が減る。  
Phase B 実施時は生成件数を 2〜3× に増やすことを推奨。

---

## 4. C2 が Sweet Spot にどれくらい入っているか

| Method | Sweet spot (novelty≥0.4 & investigated) | 比率 |
|--------|----------------------------------------|------|
| C2_multi_op | 64/70 | **91.4%** |
| C1_compose | 46/70 | 65.7% |
| C_rand_v2 | 42/70 | 60.0% |

**C2 vs C_rand Fisher 検定: p = 1.1e-05（有意）**

C2 は C_rand よりも有意に多くの sweet spot 仮説を生成。  
C2 の優位性は、KG 経路が entity 間の文献がある程度存在するゾーン（novelty 0.6–0.8）に仮説を誘導する構造に起因。

---

## 5. Novelty Score 設計サマリー

```
combined_novelty = 0.3 × path_length_score
                 + 0.3 × cross_domain_score
                 + 0.4 × (1 - entity_popularity_normalized)
```

- path_length_score: chain_length ≥5 → 1.0、=3 → 0.5、=4 → 0.8
- cross_domain_score: chem vs bio → 1.0、同一 domain → 0.0
- entity_popularity_normalized: log(1+hits)/log(1+max_hits)、hits = past_pubmed_hits_le2023

---

## 6. 次のアクション

1. **[P1 Phase B] novelty_ceiling 条件**: T_high=0.75 で combined_novelty をフィルタ。生成件数 ×3 で Net 30 件を確保。
2. **[P1 Phase A] 継続**: bridge_quality / alignment_precision 条件の実装・検証。
3. **[P3 補足・任意]** entity レベル人気度スコアの追加（subject/object 単体の past hits）で novelty 指標を改善し、方法間の分離を強化できる可能性。

---

## 制限事項

- Novelty スコアはほぼ構造的に方法ごとに固定（path_length と cross_domain が method-invariant に近い）
- entity_popularity は hypothesis レベルの文献数（entity ペア）であり、entity 単体の人気度ではない
- 低 novelty 群（N=23）は C1 のみで構成されており、method confound が除去できていない
- 逆U字検証には novelty が中程度（0.4–0.6）の C2/C_rand サンプルが必要（現在 C2 はほぼ全件 0.6+）
