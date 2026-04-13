# Density Ceiling Hypothesis — H_ceiling

**Date**: 2026-04-14
**Status**: PROPOSED — awaiting run_021

---

## 主仮説 H_ceiling

> **Cross-domain hypothesis investigability is primarily constrained by literature-density asymmetry rather than by KG operator quality.**

言い換えると: operator を改善しても investigability が上がらなかった根本原因は、cross-domain エンティティペアを扱う文献そのものが少ないことにある。

---

## 背景と動機

P1 Phase A (run_020) の結果、bridge_quality / alignment_precision フィルタは investigability を改善しなかった (0.900, 0.909 vs baseline 0.933)。この観察と一致する最も単純な説明は:

1. C2 が生成する cross-domain 仮説は、biology × chemistry の境界を跨ぐ
2. そのような境界領域を扱う文献は、単一ドメイン内の仮説に比べて少ない
3. 文献が少ない = PubMed 2024-2025 での validation corpus にヒットしにくい = investigability が低い
4. これは operator の品質とは独立した構造的制約である

---

## Density Metrics の定義

既存データ (run_018 / run_020) の各仮説に以下の指標を付与する。

### a) subject_density
subject エンティティの PubMed past corpus (≤ 2023) ヒット数。
- 測定方法: E-utilities esearch, db=pubmed, datetype=pdat, maxdate=2023/12/31
- 意味: subject がどれだけ「研究されてきたか」

### b) object_density
object エンティティの PubMed past corpus ヒット数。
- subject_density と同様の方法

### c) pair_density
subject AND object の共起ヒット数 (past corpus ≤ 2023)。
- クエリ例: `"dopamine" AND "EGFR"`
- 意味: ペアとして研究されてきた文献量 — investigability の最も直接的な予測因子と予想

### d) bridge_density (cross-domain 仮説のみ)
bridge node の PubMed past corpus ヒット数。
- bridge が研究されているほど、そこから cross-domain 仮説が生まれやすいという仮定

### e) domain_density_gap
`|biology_node_avg_density - chemistry_node_avg_density|`
- cross-domain ペアのドメイン間の文献密度の非対称性
- 大きいほど、一方のドメインで蓄積が偏っている

### f) min_density
`min(subject_density, object_density)`
- bottleneck 指標: ペアの investigability はより文献の少ない側に制約される (Liebig の桶)

---

## 予測

1. **pair_density または min_density が investigability の最強の予測因子**
   - 相関係数 |r| ≥ 0.4 を期待
   - bridge_density よりも strong な predictor であることを確認

2. **density を control した後、C1 vs C2 の差が ≤ 0.02 に縮まる**
   - C1 (bio-only, 0.971) と C2 (cross-domain, ~0.91–0.93) の差は density の違いで説明できる
   - density が同等の仮説のみ比較すると、C1 vs C2 の差が消える or 小さくなる

3. **density が低い仮説のみ抽出すると investigability も低い**
   - density tertile の下位 1/3 での investigability と上位 1/3 を比較する

---

## 分析設計

### Step 1: Density Score の付与

既存の hypothesis データ (run_018 output_candidates.json, run_020 各条件) に density metrics を追加する。

```
src/scientific_hypothesis/add_density_scores.py
- 入力: runs/run_018_*/output_candidates.json
         runs/run_020_cross_domain_phase_a/hypotheses_*.json
- 処理: PubMed E-utilities で各エンティティ/ペアのヒット数を取得
         retmax=0 (count only), past corpus ≤ 2023
- 出力: 各仮説に density フィールドを追加した JSON
```

### Step 2: 相関分析

density metrics × investigability の相関を計算する。

```
metrics: [subject_density, object_density, pair_density,
          bridge_density, domain_density_gap, min_density]
target:  investigability (binary: 1/0)

分析:
- Pearson 相関 (Python 標準ライブラリで実装)
- point-biserial 相関 (binary target との相関)
- 各 metric のランク順位
```

### Step 3: Density による C1 vs C2 説明

```
1. C1 と C2 の density distribution を比較
   - C1 (bio-only) は density が高い → investigability が高い、という説明が成立するか
2. density を matched にした subset で C1 vs C2 比較
   → matched_comparison_plan.md 参照
```

### Step 4: Density Stratified Analysis

```
density tertile (T1=low, T2=mid, T3=high) ×  条件 (C1, C2) で
investigability を比較する 2×3 テーブルを作成
```

---

## 成功基準

| 基準 | 閾値 |
|------|------|
| pair_density or min_density が investigability の最強 predictor | |r| ≥ 0.4 |
| density control 後の C1 vs C2 差 | ≤ 0.02 |
| density T3 (high) vs T1 (low) の investigability 差 | ≥ 0.15 |

**失敗基準**: density と investigability に相関がない (|r| < 0.2 for all metrics) → H_ceiling 棄却、別の説明を探す

---

## 実装計画

| ステップ | ファイル | 出力先 |
|--------|--------|-------|
| density score 付与 | src/scientific_hypothesis/add_density_scores.py | runs/run_021_density_ceiling/ |
| 相関分析 | src/scientific_hypothesis/run_021_analyze.py | runs/run_021_density_ceiling/correlation_results.json |
| 層別比較 | 同上 | runs/run_021_density_ceiling/stratified_comparison.json |
| レビューメモ | — | runs/run_021_density_ceiling/review_memo.md |

---

## 注意事項

- PubMed E-utilities の rate limit に注意 (3 req/sec, API key なし)
- pair_density が 0 の場合は 0 として記録する（ゼロ除算注意）
- density は log 変換して使うことを推奨 (right-skewed distribution)
- past corpus ≤ 2023 を厳守: validation corpus (2024-2025) との混在を避ける
