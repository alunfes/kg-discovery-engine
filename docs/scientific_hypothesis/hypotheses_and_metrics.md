# Phase 1: Hypotheses and Evaluation Framework

## 検証仮説の構造

本フェーズでは「KG multi-operator pipeline が single-op / random baseline より将来文献で支持されやすい仮説を生成できるか」を3つの直交する次元で検証する。

---

## 1. 主仮説: 将来文献支持割合（Investigated Precision）

### H0_main
KG multi-operator pipeline (C2) が生成した仮説の investigated precision は、single-operator baseline (C1) および random baseline (C_rand) の investigated precision と統計的に差がない。

```
precision_investigated(C2) = precision_investigated(C1)  [帰無仮説]
precision_investigated(C2) = precision_investigated(C_rand)  [帰無仮説]
```

### H1_main
KG multi-operator pipeline (C2) の investigated precision は、いずれの baseline より有意に高い。

```
precision_investigated(C2) > precision_investigated(C1)     [片側, α=0.05]
precision_investigated(C2) > precision_investigated(C_rand) [片側, α=0.05]
```

**Investigated precision の定義:**
```
precision_investigated = |{h ∈ H : label(h) ∈ {supported, partially_supported, contradicted}}|
                         / |{h ∈ H : label(h) ≠ not_investigated}|
```

- 分母は `not_investigated` を除いた仮説集合（investigated subset）
- supported/partially_supported を「仮説が価値を持つ」とみなす場合の precision:
  ```
  precision_positive = |{h : label(h) ∈ {supported, partially_supported}}|
                       / |investigated subset|
  ```
- 主分析は `precision_positive` を使用、`precision_investigated` は補助指標

**統計検定**: Fisher's exact test（サンプル数が少ない場合）または chi-square test（各セル≥5 の場合）

---

## 2. 副仮説1: Investigability（将来文献で検証対象になりやすさ）

### H0_cov
C2 仮説の investigability ratio は C1・C_rand と差がない。

### H1_cov
C2 仮説の investigability ratio は C1・C_rand より高い（≥5 percentage points）。

**Investigability ratio の定義:**
```
investigability(H) = |{h ∈ H : label(h) ≠ not_investigated}| / |H|
```

**意図**: not_investigated を「失敗」と扱わないが、「将来文献が拾いやすい仮説を生成しているか」は独立して評価する。investigability が低い場合、corpus期間の延長や corpus 拡大が必要なことを示す。

**成功閾値**: investigability(C2) ≥ investigability(C_rand) かつ investigability(C2) ≥ 0.30（仮説の30%以上が将来文献で言及される）

---

## 3. 副仮説2: High-novelty かつ 未検証の仮説量

### H0_novel
C2 が生成する「high-novelty かつ not_investigated」仮説の割合は C_rand と差がない。

### H1_novel
C2 の「high-novelty かつ not_investigated」割合は C_rand より有意に高い（≥10 percentage points）。

**定義:**
```
high_novelty_uninvestigated(H) = |{h ∈ H : novelty_score(h) ≥ 0.7 AND label(h) = not_investigated}|
                                  / |H|
```

`novelty_score(h)` は既存の `scorer.py` の `_score_novelty()` を流用（cross-domain: 1.0, new edge: 0.8, reframed: 0.5）。

**意図**: 「まだ文献が追いついていないが構造的に意味のある仮説」を C2 がより多く生成できるかを検証。これは KG 固有の価値仮説。

---

## 4. 評価ラベル 5分類

すべての仮説に対し、以下の5つのラベルを1つ付与する。

| ラベル | 定義 |
|--------|------|
| `supported` | 将来corpus（validation period）内の1本以上の文献が、この仮説の中心的な関係を実験的・臨床的に確認している |
| `partially_supported` | 将来corpusに関連する知見があるが、仮説の全条件を満たしていない（一部の条件のみ確認、または間接的証拠のみ） |
| `contradicted` | 将来corpusに、仮説の中心的な関係を明示的に否定する文献がある |
| `investigated_but_inconclusive` | 将来corpusで実験・調査されたが、支持も否定も明確にされなかった（replication failure、mixed resultsを含む） |
| `not_investigated` | 将来corpusで仮説のキーワード・概念が登場しない、または仮説の検証が試みられた痕跡がない |

### ラベル付けに関する基本方針

- `not_investigated` は失敗扱いしない。これは「corpus が薄い」または「仮説が先進的すぎる」可能性を含む。
- `contradicted` は「価値のない仮説」ではない。KG が反論可能な仮説を生成できることは productive failure として価値がある。
- `investigated_but_inconclusive` は precision 分析では分母に含まれる（investigated subset）が、numerator には含まれない。

---

## 5. 指標一覧と計算方法

| 指標名 | 計算式 | 主/副 | 比較対象 |
|--------|--------|-------|----------|
| `precision_positive` | (supported + partially_supported) / investigated | 主 | C2 vs C1, C_rand |
| `precision_investigated` | investigated / all | 副（investigability） | C2 vs C1, C_rand |
| `high_novelty_uninvestigated_rate` | high_novelty AND not_investigated / all | 副（novelty） | C2 vs C_rand |
| `mean_novelty_score` | mean(novelty_score) across all hypotheses | 補助 | C2 vs C1, C_rand |
| `label_distribution` | 5ラベルの割合 | 記述統計 | all methods |

---

## 6. サンプルサイズ計画

**目標**: 各 method から 50 仮説生成（max_hypotheses_per_method = 50）

| method | 仮説数 |
|--------|--------|
| C2 (multi-op) | 50 |
| C1_compose (single-op: compose only) | 50 |
| C1_diff (single-op: difference only) | 50 |
| C_rand (random path) | 50 |
| 合計 | 200 |

**期待 investigated 数**: investigability ≥ 0.30 と仮定すると各method ≥ 15 件。
Fisher's exact test で precision_positive の差が 20 percentage points のとき power ≥ 0.70 を達成するには各group ≥ 15 件が必要（α=0.05、片側）。

**MVP**: 各 method から 20 仮説、厳密ラベリング 80 件で検証可能性を先に確認する。

---

## 7. 成功基準の明示

以下のすべてを満たした場合、「KG multi-operator pipeline の scientific hypothesis generation における有効性が示された」と判断する。

| 基準 | 条件 |
|------|------|
| SC-1 | precision_positive(C2) > precision_positive(C_rand), p < 0.05 (片側) |
| SC-2 | investigability(C2) ≥ investigability(C_rand) |
| SC-3 | high_novelty_uninvestigated_rate(C2) > high_novelty_uninvestigated_rate(C_rand) |

SC-1 のみ達成、SC-2/SC-3 未達の場合は「部分的支持」とし、追実験を推奨。
SC-1 未達の場合、SC-2/SC-3 の結果を用いてどの側面でKGが価値を示したかを報告する。

---

## 8. 既存仮説（H1-H4）との関係

本フェーズの仮説は、既存の `docs/hypotheses.md` の H1-H4 とは独立した新規実験として扱う。

| 既存 | 本フェーズとの関係 |
|------|------------------|
| H1（multi-op ≥10% plausibility+novelty） | plausibility は本フェーズでは"文献支持"に置き換え。rubric scoreは補助指標 |
| H2（強い評価層 > 完璧KG） | 本フェーズでは evaluator の比較は行わない（スコープ外） |
| H3（cross-domain novelty ≥20%） | high_novelty_uninvestigated_rate に統合 |
| H4（provenance-aware scoring）| 本フェーズでは provenance は traceability の記録にとどめる |
