# run_019 Review Memo — P3 Novelty-Investigability Tradeoff

**Date**: 2026-04-14  
**Run**: run_019_novelty_tradeoff_analysis  
**Source data**: run_018_investigability_replication (N=210, C2/C1/C_rand_v2, 70 each)

---

## 目的

novelty score を 210 件の仮説に付与し、novelty-investigability の関係を定量化する。  
逆U字曲線（最適 novelty レンジ）の存在を検証し、P1 novelty_ceiling 条件の T_high を決定する。

---

## Novelty Score 設計

| スコア | 計算方法 | 備考 |
|--------|----------|------|
| path_length_score | chain_length: 2=0.2, 3=0.5, 4=0.8, 5+=1.0 | C2: 全件1.0、C_rand: 全件0.5 |
| cross_domain_score | subject/object の domain prefix 差異 (chem vs bio) | C2: 全件1.0、C1: 全件0.0、C_rand: 全件1.0 |
| entity_popularity_score | 1 - log(1+hits)/log(1+max_hits)。hits = past_pubmed_hits_le2023 | 既存 Layer 2 データを再利用（重複 API 呼び出し回避） |
| combined_novelty | 0.3×path + 0.3×cross_domain + 0.4×popularity_score | — |

**設計上の注意**: entity_popularity_score は hypothesis レベルの past corpus 文献数を使用（subject+object 組み合わせ検索の代理）。この設計により各 method の novelty は構造的に強く規定される。

---

## 主要結果

### Novelty 分布（method 別）

| Method | Novelty median | Novelty range | Inv. rate |
|--------|---------------|---------------|-----------|
| C2_multi_op | 0.842 | 0.665–1.000 | 0.914 |
| C1_compose | 0.435 | 0.167–0.624 | 0.971 |
| C_rand_v2 | 0.780 | 0.594–0.850 | 0.600 |

C2 と C1 の novelty 分布は重複がほぼない（C2 は高 novelty に集中、C1 は低〜中 novelty）。

### Novelty Bin × Investigability Rate

```
Bin          Overall        C2        C1    C_rand   C2_n   C1_n   Cr_n
------------------------------------------------------------------------
0.0-0.2        1.000       N/A     1.000       N/A      0      2      0
0.2-0.4        0.952       N/A     0.952       N/A      0     21      0
0.4-0.6        0.978       N/A     0.977     1.000      0     43      2
0.6-0.8        0.840     1.000     1.000     0.739     25      4     46
0.8-1.0        0.672     0.867       N/A     0.273     45      0     22
```

**重要な発見**:
- Novelty ≥0.8 のビンで investigability が大幅低下（overall 0.672、C_rand 0.273）
- Novelty 0.6–0.8 ビンでは C2=1.0、C_rand=0.739（まだ高水準）
- C1 は 0.0–0.8 の範囲に全件収まり、investigability は概ね 0.95+

---

## 仮説検証結果

### 逆U字パターンの有無

**結論: 逆U字なし。単調低下（novelty が高いほど investigability が下がる）。**

- 低 novelty 群（<0.4、N=23、全件 C1）: investigability = 0.957
- 高 novelty 群（≥0.6、N=142）: investigability = 0.761
- Fisher 検定: p = 0.997（一方向、高>低を検定）→ **非有意**

期待していた逆U字は観察されなかった。代わりに novelty ceiling（高 novelty で investigability が低下）が明確に確認された。

### Sweet Spot 分析（novelty ≥0.40 かつ investigated=1）

| Method | Sweet spot | 比率 | High novelty inv. rate |
|--------|-----------|------|----------------------|
| C2_multi_op | 64/70 | **0.914** | 0.914 |
| C1_compose | 46/70 | 0.657 | 0.979 |
| C_rand_v2 | 42/70 | 0.600 | 0.600 |

C2 が最多の sweet spot 仮説を生成（91.4%）。C1 は investigability 自体は高いが novelty が低いため sweet spot 率は低い。

### 統計検定

| 検定 | 結果 | 有意 |
|------|------|------|
| Test1: 高 vs 低 novelty investigability (Fisher one-sided) | p = 0.997 | ❌ |
| Test2: C2 vs C_rand sweet spot 占有率 (Fisher one-sided) | p = 1.1e-05 | ✅ |

Test2 は強く有意。C2 は C_rand よりも sweet spot に有意に多い（91.4% vs 60.0%）。

---

## 解釈

### なぜ C2 は sweet spot に集中するか

C2 の novelty score の内訳:
- path_length_score: 全件 1.0（chain_length 5〜9）
- cross_domain_score: 全件 1.0（chem→bio）
- entity_popularity_score: C2 の past_hits 中央値 = 57（C_rand=5 より高い）

その結果、C2 は combined_novelty 0.665〜1.000 の範囲（中央値 0.842）に集中。  
C_rand は popularity が低すぎる（中央値 hits=5）ため novelty ≥0.8 に偏り、0.8+ ビンでは investigability が 27.3% に低下。

**C2 の優位性は「KG 経路によって entity 間の文献がある程度存在する範囲の仮説を生成する」構造に起因する。**

### Novelty Ceiling の確認

Novelty ≥0.8 ビン:
- overall: 67.2%
- C_rand: 27.3%（低文献 entity ペアは文献なしで終わる）

これは P1 novelty_ceiling 条件（T_high フィルタ）の設計根拠となる。

---

## P1 への入力: T_high 推奨値

**T_high = 0.75**（推奨）

根拠:
- 0.6–0.8 ビン: C2 investigability = 1.0、optimal
- 0.8–1.0 ビン: overall investigability = 67.2%、C_rand = 27.3%
- 0.75 を上限とすることで novelty ≥0.8 の「過高 novelty」ゾーンへの侵入を防げる
- C2 の 70 件中 25 件（36%）が 0.6–0.8 ビンに入っており、フィルタ効果が期待できる

**注意**: T_high=0.75 を C2 に適用すると 25/70 件（35.7%）が残る。フィルタ後の絶対数を確保するため、run_019 Phase B では生成件数を増やす必要がある可能性あり。

---

## 制限事項

1. **novelty score が構造的に固定**: path_length と cross_domain はほぼ method 固有の値。実質的な differentiator は entity_popularity のみ。
2. **entity_popularity の代理指標**: past_pubmed_hits_le2023 は entity-level でなく hypothesis-level の指標（subject+object ペアの文献数）。
3. **逆U字なし**: 期待した inverted-U を確認できなかった。low novelty 群（N=23）はほぼ全件 C1 であり、method の confounding を除去できていない。

---

## 次のアクション

1. **[P1 Phase B] novelty_ceiling 条件の実装**: T_high=0.75 を combined_novelty の上限として適用
2. **[P1 Phase A] 継続**: bridge_quality + alignment_precision 条件の生成（P3 完了により Phase B ゲート通過）
3. **[任意] Novelty score の改善**: entity レベルの popularity スコア（subject 単体、object 単体の文献数）を追加すれば differentiator が増える

---

## ファイル一覧

| ファイル | 内容 |
|---------|------|
| novelty_scores.json | 210件 + novelty scores |
| bin_analysis.json | Bin × investigability rate（method別） |
| sweet_spot_analysis.json | Sweet spot 分析 |
| statistical_tests.json | Fisher 検定結果 |
| novelty_scatter.html | インタラクティブ散布図 |
| review_memo.md | 本ファイル |
