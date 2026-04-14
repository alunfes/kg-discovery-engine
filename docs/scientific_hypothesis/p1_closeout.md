# P1 Closeout — Operator Tuning NO-GO

**Date**: 2026-04-14
**Run**: run_020_cross_domain_phase_a
**Status**: CLOSED — NO-GO

---

## 正式結論

> **「cross-domain investigability を operator tuning で改善する」という仮説は棄却する。**

bridge_quality フィルタ (confidence ≥ 0.7) を適用した場合、investigability は baseline (0.933) を下回る 0.900 となった。alignment_precision フィルタ (confidence ≥ 0.8) でも 0.909 に留まり、かつサンプル数が 11 件と検出力が不足していた。

---

## 結果サマリー

| 条件 | N | Investigability | vs baseline | 判定 |
|------|---|----------------|-------------|------|
| C2_baseline | 30 | 0.933 | — | 参照 |
| C2_bridge_quality | 30 | 0.900 | -0.033 | **FAIL** |
| C2_alignment_precision | 11 | 0.909 | -0.024 | **FAIL + underpowered** |
| C2_novelty_ceiling | 8 | 1.000 | +0.067 | underpowered (N=8) |
| C2_combined | 6 | 1.000 | +0.067 | underpowered (N=6) |

**注意**: novelty_ceiling と combined の 1.000 は N が小さすぎる（N=8, N=6）ため、主張の根拠として使用しない。

---

## 何が分かったか

### 「改善不能」ではない

operator tuning では改善しなかったが、これは investigability の向上が原理的に不可能だということを意味しない。改善レバーが operator の側にはなかっただけである。

### bridge quality を上げても investigability は上がらない

bridge_quality フィルタは confidence の高い bridge node を持つ仮説を選別するが、investigability は **subject–object ペアの文献密度** に依存している。bridge node の品質が高くても、そのペアを扱う文献が少ない領域では investigability は上がらない。

### C2 の investigability ~0.91–0.93 は構造的上限に近い可能性

run_018 (0.914) と run_020 baseline (0.933) の値は operator を変えても動かなかった。これは C2 が生成する cross-domain 仮説の investigability が、KG に含まれるエンティティの文献密度によって上限を画されている可能性を示唆する。

---

## P2 (align 精度分析) の位置づけ変更

P1 Phase A の NO-GO を受け、P2 の優先度を下げて保留とする。

- P2 の問い（align オペレータの精度が investigability を左右するか）は技術的に有効だが、今回の差の主因ではないことが示唆された
- strict token-overlap による alignment_precision 条件で N=11 という結果が示すように、今の pool では十分な検定力を確保できない
- 将来、別ドメインや大規模 pool で実験を行う際に再検討する

---

## 問いの転換

P1 Phase A の結論を踏まえ、次の研究問いを以下のように切り替える。

| 旧問い | 新問い |
|--------|--------|
| How to improve operator quality? | What determines the investigability ceiling? |
| align ノイズを下げれば investigability は上がるか？ | 文献密度が investigability の主要な予測因子か？ |

---

## 次のアクション

1. **density ceiling 分析 (run_021)**: 各仮説に density metrics を付与し、investigability との相関を分析する → `docs/scientific_hypothesis/density_ceiling_hypothesis.md`
2. **matched comparison**: novelty × density でマッチングした部分集合での C1 vs C2 比較 → `docs/scientific_hypothesis/matched_comparison_plan.md`
3. **P2 保留**: align 精度分析は将来の別ドメイン実験まで持ち越し

---

## P1 Final Closing Statement

**Date**: 2026-04-14 (run_023 完了後)

> **"P1 Closed: Observed C1–C2 gap is primarily a density-selection artifact, with residual weakness confined to the lowest-density regime."**

run_022 (density-aware selection) および run_023 (causal verification) により、以下が確定した:

- C1-C2 の observational gap は density mismatch が主因 (density β有意 p=0.01、model β非有意 p=0.30、R²分解 88%)
- C2 の一般的能力劣位は否定される
- 残差的弱さは Q1 (lowest-density) に限局 (interaction β=0.228, p=0.0004)
- density control 後の matched test では非有意 (p=0.20)

結論の形が確定した。「完全に終わった」ではなく「C2 の弱さの構造が特定された」として閉じる。

次フェーズ (P2) の優先候補: density-aware selection を discovery engine の標準設計に昇格 (P2-B)
