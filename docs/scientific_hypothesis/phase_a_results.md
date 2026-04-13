# P1 Phase A Results — bridge_quality / alignment_precision

**Date**: 2026-04-14
**Run ID**: run_020_cross_domain_phase_a
**Status**: NO-GO

---

## 実験条件

| 条件 | フィルタ | N |
|------|---------|---|
| C2_baseline | なし | 30 |
| C2_bridge_quality | Bridge broad ≥ 0.7 | 30 |
| C2_alignment_precision | Bridge strict ≥ 0.8 | 11 |
| C2_novelty_ceiling | combined_novelty ≤ 0.75 | 8 |
| C2_combined | Bridge ≥ 0.7 AND novelty ≤ 0.75 | 6 |

---

## 結果

| 条件 | N | Investigated | Investigability | p vs baseline |
|------|---|-------------|----------------|---------------|
| C2_baseline | 30 | 28 | 0.933 | — |
| C2_bridge_quality | 30 | 27 | 0.900 | 0.8234 |
| C2_alignment_precision | 11 | 10 | 0.909 | 0.8297 |
| C2_novelty_ceiling | 8 | 8 | 1.000 **✓** | 0.6188 |
| C2_combined | 6 | 6 | 1.000 **✓** | 0.6905 |

参考: C1 = 0.971, C2 baseline (run_018) = 0.914

---

## 総合判定: **NO-GO**

全条件で investigability ≤ 0.92 → align ではなく文献密度の構造的問題 → P2 優先度下げ

---

## 結論

全条件で investigability が目標値 0.95 を下回った。 bridge_quality/alignment_precision フィルタは investigability 改善に不十分。 根本原因は align オペレータではなく KG の文献密度の構造的制約の可能性が高い。 P2 (align precision analysis) の優先度を下げる。
