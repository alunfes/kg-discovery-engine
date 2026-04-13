# Matched Comparison Plan — H_match

**Date**: 2026-04-14
**Status**: PROPOSED — run_021 と同時実施

---

## 副仮説 H_match

> **After matching for novelty and literature density, the investigability gap between C1 and C2 shrinks substantially (≤ 0.02).**

現在観察されている C1 (0.971) vs C2 (0.914) の investigability 差は、operator の優劣ではなく、C1 が bio-only (高密度) で C2 が cross-domain (低密度) という **composition の違い** に起因する可能性がある。

---

## 背景

| 条件 | Investigability | 特性 |
|------|----------------|------|
| C1 (bio-only, run_018) | 0.971 | 単一ドメイン、文献密度が高い |
| C2 (cross-domain, run_018) | 0.914 | biology × chemistry、文献密度が低い |
| C2 (run_020 baseline) | 0.933 | 同上 |

この差 (~0.06) を「C2 の operator が劣る」と解釈するのは早計である。C1 は bio-only のため literature density が高く、それだけで investigability が高くなることを説明できる可能性がある。

---

## 方法

### データソース

- run_018 C1: 70件 (bio-only hypotheses)
- run_018 C2: 70件 (cross-domain hypotheses)
- density scores: run_021 で算出 (density_ceiling_hypothesis.md 参照)
- novelty scores: run_019 で算出済み

### Step 1: 各仮説への特徴付与

各仮説に以下を付与する:
```
- combined_novelty (run_019 算出済み)
- min_density (run_021 で算出)
- pair_density (run_021 で算出)
- investigability (run_018 既存ラベル)
- condition (C1 or C2)
```

### Step 2: Bin の定義

**novelty bin** (3分位):
```
low:  combined_novelty ≤ 33rd percentile
mid:  33rd < combined_novelty ≤ 67th percentile
high: combined_novelty > 67th percentile
```

**density bin** (3分位):
```
low:  min_density ≤ 33rd percentile
mid:  33rd < min_density ≤ 67th percentile
high: min_density > 67th percentile
```

※ percentile は C1+C2 合算の分布で算出する

### Step 3: Bin 内での比較

各 novelty_bin × density_bin セルで C1 vs C2 の investigability を比較する。

```
例: novelty=mid × density=mid のセルで
    C1: n件中m件 investigated
    C2: n件中m件 investigated
    → investigability の差を算出
```

### Step 4: 結果の解釈

- **H_match 支持**: 各セル内の C1 vs C2 差が ≤ 0.02
- **H_match 棄却**: セル内の差が > 0.04 で継続的
- **中間**: 差が 0.02–0.04 の範囲 → 追加分析が必要

---

## サンプルサイズへの注意

matching によって各セルの N が小さくなりすぎる場合の代替戦略:

### 代替1: Propensity Score Matching の代わりに層別比較

bin を 3×3=9 セルから 2×2=4 セルに粗くする:
```
novelty: low (≤ median) / high (> median)
density: low (≤ median) / high (> median)
```
各セル N ≥ 5 を確保できれば報告可能。

### 代替2: density のみでマッチング (novelty を無視)

density bin (tertile) のみで C1 vs C2 を比較する 3セル版。
novelty は密度と独立した共変量として別途記録する。

### 代替3: 連続量による回帰的アプローチ

Python 標準ライブラリのみで実装可能な範囲で:
```python
# 簡易 logistic-style: 各 density 分位での investigability rate を算出
# C1 と C2 の density distribution が overlap する領域のみで比較
```

---

## 成功基準

| 基準 | 判定 |
|------|------|
| matched subset での C1 vs C2 差 ≤ 0.02 | H_match 支持 |
| matched subset での C1 vs C2 差 > 0.04 | H_match 棄却 |
| 0.02 < 差 ≤ 0.04 | 中間 — density 以外の要因が残存 |
| 各セル N < 5 で比較不能 | 「検出力不足」として正直に報告 |

---

## 実装計画

density_ceiling 分析 (run_021) と同一スクリプト内で実施する:

```
src/scientific_hypothesis/run_021_analyze.py
- density_ceiling_hypothesis.md の Step 1-4 を実行した後
- matched_comparison として novelty × density bin 比較を追加
- 出力: runs/run_021_density_ceiling/matched_comparison.json
```

---

## 報告方針

結果がどうあれ正直に報告する:

- H_match が支持された場合: C1 vs C2 の差は operator の優劣ではなく density composition の違いと結論付ける
- H_match が棄却された場合: density 以外の要因 (例: C2 の operator が生成するエンティティペアの種類) が investigability を下げている可能性を検討する
- 検出力不足の場合: N が小さすぎて結論不能と明記し、必要な pool サイズを算出する

---

## 関連文書

- `density_ceiling_hypothesis.md` — 主仮説 H_ceiling の定義と分析設計
- `p1_closeout.md` — P1 Phase A NO-GO の結論
- `phase_a_results.md` — run_020 の実験結果
