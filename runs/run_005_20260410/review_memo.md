# Run 005 Review Memo

**Date**: 2026-04-10
**Purpose**: H1の公平な再検証 — 候補バジェット制御 + Cohen's d効果量評価

---

## 実験設計の変更点

| 項目 | 従来 (Run 001-004) | Run 005 |
|------|-------------------|---------|
| 比較入力 | C1: biology KG / C2: bio+chem KG | C1: bridge_kg / C2: bio+chem pipeline |
| 候補数制御 | なし (C2が常に多い) | top-N (N=33, min候補数) |
| H1判定 | 固定閾値10% | Cohen's d > 0.2 |

---

## 結果

| 指標 | C1 (single-op) | C2 (multi-op) | 差 |
|------|---------------|--------------|-----|
| N (top-N) | 33 | 33 | — |
| mean_total | 0.7523 | 0.7508 | **-0.0015 (C1優位)** |
| median_total | 0.7550 | 0.7350 | +0.020 |
| std_total | 0.0238 | 0.0286 | — |
| top3_mean | 0.785 | 0.785 | 0.000 |
| promising_ratio | 1.000 | 1.000 | — |
| Cohen's d | — | — | **-0.058 (negligible)** |

**H1 判定: FAIL (Cohen's d = -0.058, negligible effect)**

---

## 解釈

### なぜC1がわずかに高かったか
`bio_chem_bridge_kg` はcross-domain接続が予め組み込まれたKGのため、  
single-op compose でも高品質なcross-domain仮説が生成される。  
つまり、C1がbridge_kgを使う限り、multi-op pipelineの優位性は相殺される。

### 効果量が負になった意味
Cohen's d = -0.058: **C2はC1と実質同等（negligible効果）**。  
従来のRun 003/004で見られた+3-7%の差は、C2が多くの候補を生成していたことに起因しており、  
バジェット制御後は消失した。

### カテゴリ分布の均一性
全候補が`promising`カテゴリ (0.60-0.85) に集中。  
スコア範囲が狭い（0.705-0.785）ため、現在の評価器は候補間の弁別力が低い。

---

## H1の最終結論

**H1 (multi-opは≥10%高品質) は5つのRunを通じてFAIL**。

ただし解釈は重要：
1. **10%閾値は実証的根拠なし** — 設定時から一度も達成されていない
2. **C2の優位性は候補数に依存** — バジェット制御後は消失
3. **bridge_kgで単純にcomposeすると同等品質** — pipeline自体の付加価値は限定的
4. **toy dataの飽和** — これ以上のtoy data実験でH1を解決するのは困難

### Phase 3への示唆
実データ (PubMed/WikiData) では:
- C1のinputとなる単一KGに事前にcross-domain接続は存在しない
- multi-op pipelineの意義が正しく測定できる可能性がある
- 実データでの再検証が必要

---

## 未解決問題

1. **スコアの弁別力不足** — 全候補がpromising帯に集中 → Run 006でtestability改善試みる
2. **C1のbridge_kg使用の公平性** — C1がbridge_kgを使えるなら、multi-opは不要では？という問いが残る

---

## 次のアクション

→ Run 006: H3の根本問題（tautological scoring）とevaluator品質の改善
