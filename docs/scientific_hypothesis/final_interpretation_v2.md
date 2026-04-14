# 最終解釈 v2 — KG Discovery Engine 検証系列の総括

作成日: 2026-04-14

---

## 概要

run_001 から run_021 に至る検証系列全体を一本化した最終解釈。「KG は失敗した」ではなく「KG の有効境界が特定された」という建設的結論を提示する。

---

## 検証の進化経路（4段階）

### 段階 1: Trading alpha / meta-filter（run_001–014）

**目的:** KG オペレータを用いたトレーディングシグナル生成・メタフィルタリング

**結果:** 14本中 1本 Hard No-Go

**主な教訓:**
- KG は timing 微差・execution 依存の課題には向かない
- 市場での有効性は statistical signal の有無より execution infrastructure が律速
- 本プロジェクトは trading alpha 追求から科学的仮説生成へ軸足を移した

---

### 段階 2: Scientific hypothesis — Supported novelty（run_015–017）

**目的:** KG multi-op が random baseline より supported novel fact を多く当てるか

**検定:** SC-1r

| 条件 | 値 |
|------|----|
| C2 (multi-op) | 0.130 |
| C_rand | 0.219 |
| p値 | 0.91 |
| 判定 | **FAIL** |

**主な教訓:**
- KG multi-op は「正しい仮説を当てる装置」ではない
- supported novelty は KG の強みを測る指標として不適切
- 「何が新しいか」より「何が検証可能か」に焦点を移す必要があった

---

### 段階 3: Scientific hypothesis — Investigability（run_017–018）

**目的:** KG multi-op が random baseline より investigable な仮説を生成するか

**検定:** SC-3r

| 条件 | 値 |
|------|----|
| C2 (multi-op) | 0.914 |
| C_rand | 0.600 |
| p値 | 0.0007 |
| N | 70 |
| 判定 | **PASS（再現確認済み）** |

**追加観察:**
- C1 (bio-only, single-op): 0.971 > C2 (cross-domain, multi-op): 0.914
- cross-domain の investigability は single-domain より低いが、random よりは有意に高い

**主な教訓:**
- KG multi-op は「検証可能な仮説を生成する装置」として有望
- investigability の差は operator の問題ではなく、domain の性質の問題である可能性が浮上

---

### 段階 4: Density ceiling（run_019–021）

**目的:** investigability の上限を規定する要因の特定

**run_019（P3）:**
- novelty ≥0.8 の条件下で C_rand の investigability が崩壊
- C2 は 0.867 を維持 → novelty ceiling effect を確認

**run_020（P1 Phase A）:**
- bridge_quality / alignment_precision の operator tuning では investigability 改善せず
- 判定: **NO-GO**

**run_021（H_ceiling）:**

| 指標 | 値 | 閾値 | 判定 |
|------|----|------|------|
| log_min_density \|r\| | 0.461 | ≥0.4 | ✅ |
| Q4 vs Q1 investigability gap | 0.453 | ≥0.15 | ✅ |
| McFadden pseudo R² | 0.218 | — | moderate |

- `log_min_density` が investigability の最強予測因子 (|r|=0.461)
- C2 の avg_min_density (14,213) << C1 の avg_min_density (29,007) — density 分布の非対称性を確認

**matched comparison（密度 × 条件のギャップ分析）:**

| Density 群 | C1_inv | C2_inv | Gap |
|-----------|--------|--------|-----|
| den_low | 0.957 | 0.760 | +0.197 |
| den_mid | 1.000 | 1.000 | 0.000 |
| den_high | 0.968 | 1.000 | −0.032 |

- ギャップは低密度群に集中
- 中〜高密度では C1 ≈ C2（または C2 > C1）
- C2 の investigability 問題の根本原因は operator ではなく **literature-density asymmetry**

**主な教訓:**
- C2 の ceiling は operator tuning では改善しない
- density が十分な cross-domain ペアでは C2 は C1 と同等の investigability を達成する
- density-aware pair selection が次の主戦場

---

## 現時点で支持される主張

| 主張 | 根拠 |
|------|------|
| KG multi-op は random baseline より investigable な仮説を生成する | SC-3r PASS (p=0.0007)、N=70で再現 |
| investigability の上限は operator quality ではなく文献密度の非対称性で決まる | run_021: log_min_density |r|=0.461、matched comparison |
| density-balanced な cross-domain ペアでは C2 は C1 と同等の investigability を達成する | den_mid/den_high で gap ≈ 0 |

---

## 支持されなかった主張

| 主張 | 根拠 |
|------|------|
| KG multi-op は random より novel supported fact を多く当てる | SC-1r FAIL (p=0.91) |
| KG multi-op は single-op より常に investigable | den_low では C2 < C1 |
| operator tuning で cross-domain investigability を改善できる | run_020 NO-GO |

---

## 建設的結論

**「KG は失敗した」ではなく「KG の有効境界が特定された」。**

### 有効境界

文献密度が十分な cross-domain ペアに対しては、KG multi-op は investigable な仮説生成器として機能する。

具体的には:
- `min_density ≥ Q2` 程度（≈1,000件以上）の cross-domain ペアでは investigability ≈ 1.0 を達成
- この条件を満たせば、C2 は C1 (single-domain) と統計的に同等

### 制約

低文献密度の cross-domain ペアでは investigability が低下するが、これは **operator の問題ではなく知識インフラの問題** である。

- 解決策は operator を改善することではなく、density-aware pair selection を導入すること
- これは「KG が使えない」ではなく「KG の使い方がわかった」という前進

---

## 参照文書

- `docs/scientific_hypothesis/final_conclusion_v1.md` — 段階3時点の結論
- `docs/scientific_hypothesis/density_ceiling_results.md` — run_021 詳細結果
- `docs/scientific_hypothesis/hypothesis_update_v2.md` — 仮説更新履歴
- `runs/run_021_density_ceiling/review_memo.md` — run_021 レビューメモ
- `docs/scientific_hypothesis/density_aware_next_steps.md` — 次の研究方向
