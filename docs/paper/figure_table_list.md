# Figure & Table List
*Fixed 2026-04-15 | paper_structure.md と対で使う。各図表の仕様・ファイルパス・本文参照位置を定義する。*

---

## Fig 1 — C1 主図: Bridge Geometry Breaks the Novelty Ceiling

| 項目 | 内容 |
|------|------|
| **図番号** | Fig 1 |
| **対応 Claim** | C1: Enriched bridge geometry removes novelty ceiling |
| **ファイルパス** | `docs/figures/fig2_c1_geometry_breakthrough.png`（**新規作成が必要**） |
| **本文参照位置** | Section 4.1, 第1段落 |
| **状態** | 未生成 — 仕様を本文書に記録 |

### 仕様

**何を比較するか**: P6-A (run_036) / P7 (run_038) / P8 (run_040) の 3 実験条件を横並びで比較し、geometry 増強が investigability ceiling を破ることを示す。

**グラフ種別**: 2-metric クラスター棒グラフ（左軸 + 右軸）または小パネル 2 枚構成。

**X 軸**: 実験条件（3 点）
- `P6-A (T2)` — ceiling 未突破: cdr_L3=0.333
- `P7 (T3)` — breakthrough: cdr_L3=0.619
- `P8 (T3)` — DESIGN_PRINCIPLE 確認: cdr_L3=0.740

**Y 軸（左）**: Investigability [0.85, 1.01]
- 各条件の T2/T3 inv 値
- 水平点線: B2 baseline (inv=0.9714)
- アノテーション: "ceiling" (P6-A) / "STRONG_SUCCESS" (P7/P8)

**Y 軸（右）**: cdr_L3 [0, 1]（折れ線または二次棒で重ねる）

**数値データ**:
| 条件 | cdr_L3 | inv (T2/T3) | B2 gap |
|------|--------|------------|--------|
| P6-A / T2 | 0.333 | 0.9429 | −0.028 |
| P7 / T3 | 0.619 | 0.9857 | +0.014 |
| P8 / T3 | 0.740 | 0.9857 | +0.014 |
| B2 baseline | — | 0.9714 | 0.000 |

**Key message**: cdr_L3 が ≥ 0.60 を超えると investigability が B2 を上回る。geometry 増強は ceiling 突破の十分条件。

**参照スクリプト**: 生成スクリプトは `scripts/generate_c1_geometry_chart.py`（未作成）で作成予定。データソース: `runs/run_036_*/run_config.json`, `runs/run_038_*/run_config.json`, `runs/run_040_*/run_config.json`

---

## Table 1 — C1 補助: ROS/NT Family Geometry Metrics

| 項目 | 内容 |
|------|------|
| **図表番号** | Table 1 |
| **対応 Claim** | C1: geometry breakthrough の reproducibility 確認（ROS family ablation） |
| **ファイルパス** | 本文内テーブル（Markdown）— 独立ファイル不要 |
| **本文参照位置** | Section 4.1, Fig 1 の直後 |
| **状態** | データあり — 本文執筆時に inline で記述 |

### 仕様

**内容**: P8 での ROS サブセット別に cdr_L3 と investigability を並べる表。

| Condition | Bridge nodes | cdr_L3 | T3 inv | Classification |
|-----------|-------------|--------|--------|---------------|
| C_P7_EXPANDED | glutathione, ROS intermediates | 0.619 | 0.9857 | STRONG_SUCCESS |
| C_ROS_GLUTATHIONE | {glutathione} | 0.619 | 0.9857 | STRONG_SUCCESS |
| C_ROS_SUPEROXIDE | {superoxide_dismutase} | 0.619 | 0.9857 | STRONG_SUCCESS |
| C_ROS_ALL | 5 nodes | 0.740 | 0.9857 | STRONG_SUCCESS |
| C_GEOMETRY_CEILING | (P6-A baseline) | 0.333 | 0.9429 | ceiling |

**Key message**: ROS ファミリーのいずれのサブセットでも cdr_L3 ≥ 0.60 かつ STRONG_SUCCESS が維持される。特定の化学ノードへの依存なし。

---

## Fig 2 — C2 主図: Domain-Agnostic Transfer (ROS vs NT)

| 項目 | 内容 |
|------|------|
| **図番号** | Fig 2 |
| **対応 Claim** | C2: Mechanism is domain-agnostic |
| **ファイルパス** | `docs/figures/fig3_c2_domain_agnostic.png`（**新規作成が必要**） |
| **本文参照位置** | Section 4.2, 第1段落 |
| **状態** | 未生成 — 仕様を本文書に記録 |

### 仕様

**何を比較するか**: ROS ファミリー（P8, 基準点）と NT ファミリー（P9 T3 vs P10-A T3+pf）を並べ、selection strategy によって GEOMETRY_ONLY が STRONG_SUCCESS に転換することを可視化する。

**グラフ種別**: グループ化棒グラフ（X 軸 = ファミリー、凡例 = selection variant）

**X 軸**: 2 グループ
- `ROS (P8)` — reference domain
- `NT (P9/P10-A)` — transfer domain

**Y 軸**: Investigability [0.80, 1.05]

**凡例（棒の種類）**:
- `T3 (e_score_min ordering)` — 薄色
- `T3+pf (endpoint-aware)` — 濃色
- `B2 baseline` — 点線水平参照線 (0.9714 / 0.9714 for ROS / NT)

**数値データ**:
| Group | Selection | inv | Classification |
|-------|-----------|-----|---------------|
| ROS (P8) | T3 | 0.9857 | STRONG_SUCCESS |
| NT (P9) | T3 | 0.8571 | GEOMETRY_ONLY |
| NT (P10-A) | T3+pf | 1.000 | STRONG_SUCCESS |

**アノテーション**:
- NT T3 → NT T3+pf の矢印に「+14.3pp (selection artifact fixed)」
- NT T3 の棒を破線/薄色で「GEOMETRY_ONLY (artifact)」
- ROS T3 の棒に「STRONG_SUCCESS (reference)」

**Key message**: selection strategy を変える（T3 → T3+pf）だけで NT ファミリーが ROS ファミリーと同等の investigability に達する。geometry は domain-agnostic に転移する。

**参照スクリプト**: `scripts/generate_c2_domain_agnostic_chart.py`（未作成）。データソース: `runs/run_040_*/run_config.json`, `runs/run_041_*/run_config.json`, `runs/run_043_*/run_config.json`

---

## Table 2 — C2 補助: Family Transfer Score Table

| 項目 | 内容 |
|------|------|
| **図表番号** | Table 2 |
| **対応 Claim** | C2: geometry と investigability の family transfer 比較 |
| **ファイルパス** | 本文内テーブル — 独立ファイル不要 |
| **本文参照位置** | Section 4.2, Fig 2 の直後 |
| **状態** | データあり — 本文執筆時に inline で記述 |

### 仕様

| Phase | Family | cdr_L3 | T3/T3+pf inv | B2 gap | Verdict |
|-------|--------|--------|--------------|--------|---------|
| P8 (run_040) | ROS | 0.740 | 0.9857 (T3) | +0.014 | STRONG_SUCCESS |
| P9 (run_041) | NT | 0.605 | 0.8571 (T3) | −0.114 | GEOMETRY_ONLY → artifact |
| P10-A (run_043) | NT | 0.605 | 1.000 (T3+pf) | +0.029 | STRONG_SUCCESS |

**Key message**: geometry (cdr_L3) は ROS→NT に転移するが、investigability 転移には endpoint-aware selection が必要。

---

## Fig 3 — C3 主図: Pre-Filter Inverts the B2–T3 Gap

| 項目 | 内容 |
|------|------|
| **図番号** | Fig 3 |
| **対応 Claim** | C3: Endpoint-aware pre-filter is required |
| **ファイルパス** | `docs/figures/fig1_p10a_comparison.png`（**既存**） |
| **本文参照位置** | Section 4.3, 第1段落 |
| **状態** | 生成済み (`scripts/generate_p10a_comparison_chart.py` で生成) |

### 内容確認

3 メトリクス × 3 条件（B2 / T3 / T3+pf）のクラスター棒グラフ:
- Investigability: B2=0.9714, T3=0.8571, T3+pf=1.000
- Novelty Retention: B2=1.000(ref), T3=1.342, T3+pf=1.238
- Long-path Share: B2=0.000, T3=0.500, T3+pf=0.500
- アノテーション: B2–T3 gap −0.114 → B2–(T3+pf) gap +0.029 の矢印

---

## Table 3 — C3 補助: B2–T3 Gap Reversal + Bucket Survival

| 項目 | 内容 |
|------|------|
| **図表番号** | Table 3 |
| **対応 Claim** | C3: pre-filter のメカニズム定量 |
| **ファイルパス** | 本文内テーブル — 独立ファイル不要 |
| **本文参照位置** | Section 4.3, Fig 3 の直後 |
| **状態** | データあり（`runs/run_043_p10a_prefilter/survival_analysis.json`） |

### 仕様（2 部構成）

**Part A: Gap Reversal**

| Gap | Value | Verdict |
|-----|-------|---------|
| B2 − T3 (investigability) | −0.114 | T3 が B2 を下回る |
| B2 − (T3+pf) (investigability) | **+0.029** | T3+pf が B2 を上回る（逆転） |

**Part B: Bucket Survival Rate**

| Bucket | T3 count | T3+pf count | Overlap | Survival Rate |
|--------|----------|-------------|---------|---------------|
| L2 | 35 | 35 | 20/35 | 57.1% |
| L3 | 20 | 20 | 1/20 | **5.0%** |
| L4+ | 15 | 15 | 0/15 | **0.0%** |

**Key message**: pre-filter は T3 をわずかに補正するのではなく、L3/L4+ バケットをほぼ完全に作り直す。これが investigability gap 逆転の直接メカニズム。

---

## 新規図の生成優先順位

| 優先度 | 図表 | 理由 |
|--------|------|------|
| **HIGH** | Fig 1 (C1 主図) | C1 は論文の出発点。P6-A→P7 breakthrough の可視化がなければ ceiling 解除の議論が始まらない |
| **HIGH** | Fig 2 (C2 主図) | GEOMETRY_ONLY → DOMAIN_AGNOSTIC の転換は本論文の最重要貢献。図なしでの説明は困難 |
| LOW | Table 1, 2, 3 | データが既存 JSON から直接構成可能。本文執筆時に inline で記述すれば足りる |
| DONE | Fig 3 (C3 主図) | 既存 (`fig1_p10a_comparison.png`) — 再生成不要 |

---

## データソース一覧

| 図表 | データファイル |
|------|--------------|
| Fig 1 | `runs/run_036_*/run_config.json`, `runs/run_038_*/run_config.json`, `runs/run_040_*/run_config.json` |
| Table 1 | `runs/run_040_*/run_config.json`（ROS ablation results） |
| Fig 2 | `runs/run_040_*/run_config.json`, `runs/run_041_*/run_config.json`, `runs/run_043_p10a_prefilter/run_config.json` |
| Table 2 | 同上 |
| Fig 3 | `runs/run_043_p10a_prefilter/comparison_table.json` |
| Table 3 | `runs/run_043_p10a_prefilter/survival_analysis.json` |
