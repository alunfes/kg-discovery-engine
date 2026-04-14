# Project Handover — KG Discovery Engine

*Last updated: 2026-04-15*

---

## P2-B Closed

**P2-B Closed: Structure-aware discovery framework established; performance governed by density structure with residual KG-driven limitations.**

P2-B successfully operationalized the density-selection artifact finding from P1 into a reusable, standardized selection framework. The optimization target has shifted from model/operator capability to (KG structure + selection policy). This boundary is now formally defined.

---

## Verification Series — Complete State Table

| Phase | Run | 結果 |
|-------|-----|------|
| Trading alpha | 001-014 | NO-GO |
| Supported novelty | 015-017 | SC-1r FAIL |
| Investigability | 017-018 | SC-3r PASS (再現) |
| Density ceiling | 019-021 | H_ceiling 支持 |
| Density-aware selection | 022 | C2=C1 parity |
| Causal verification | 023 | density が主因 (R² 88%) |
| Framework standardization | 024 | 飽和曲線確定, 6 policy, 標準設計完了 |

---

## Key Findings (P2-B)

**Strong Claim**: Structure-aware (density-aware) selection is necessary. Naive uniform selection confounds model capability with structural KG accessibility.

**Qualified Claim**: Performance follows a saturating relationship with density, and residual failure is concentrated in the lowest-density regime (Q1, min_density < 4,594).

**Critical Insight**: 50% of Q1 failures are `sparse_neighborhood` type — a KG data quality issue, not a selection policy issue. These failures are untreatable by selection policy alone.

**Operational Claim**: The system must explicitly separate what is controllable via selection policy from what is constrained by KG structure. This separation defines the P2-B / P3 boundary.

| 問題 | 責任 | 対処 |
|------|------|------|
| density mismatch | Selection policy | density filter/weighting |
| sparse neighborhood | KG structure | P3 densification |
| missing bridges | KG structure | P3 augmentation |
| diversity-driven low-quality | Selection policy | diversity guardrails |

---

## P3 Initialized

P3 has been initialized with two sub-phases:

### P3-A (Priority): KG Densification / Augmentation
- Target: sparse_neighborhood failure class (50% of Q1 failures)
- Success criterion: Q1 failure rate 38.5% → <20%
- Entry point: `src/scientific_hypothesis/sparse_region_detection.py`
- Plan: `docs/kg_optimization_plan.md`

### P3-B (Research): Density Decomposition / Topology Analysis
- Target: decompose density into structural KG metrics
- Separate PubMed density from KG-internal connectivity
- Plan: `docs/p3_overview.md`

---

## Active Standard Configs

| Config | Policy | Mode |
|--------|--------|------|
| `configs/density_policy_default.json` | diversity_guarded | Production |
| `configs/density_policy_explore.json` | quantile_constrained | Research |
| `configs/density_policy_stable.json` | hard_threshold | Benchmark |

All future runs MUST declare `selection_policy` in `run_config.json`.

---

## 論文図表 状態

| 図 | ファイル | 状態 |
|----|---------|------|
| Fig 1 (C1 主図) | `docs/figures/fig2_c1_geometry_breakthrough.png` | **生成済み** (2026-04-15) |
| Fig 2 (C2 主図) | `docs/figures/fig3_c2_domain_agnostic.png` | **生成済み** (2026-04-15) |
| Fig 3 (C3 主図) | `docs/figures/fig1_p10a_comparison.png` | 既存 |
| Table 1–3 | 本文 inline | 未執筆（データあり） |

生成スクリプト:
- `scripts/generate_c1_geometry_chart.py` — Fig 1
- `scripts/generate_c2_domain_agnostic_chart.py` — Fig 2
- `scripts/generate_p10a_comparison_chart.py` — Fig 3（既存）

仕様書: `docs/paper/figure_table_list.md`, `docs/paper/paper_structure.md`

---

## Next Action

**論文本文執筆**: paper_skeleton.md を LaTeX に変換

1. `docs/paper_skeleton.md` を元に LaTeX ソースを作成
2. Fig 1〜3 を本文に埋め込む（Section 4.1, 4.2, 4.3）
3. Table 1〜3 を inline で記述（データソース: `docs/paper/figure_table_list.md`）
4. `docs/bibliography_todo.md` の引用を整理・追加
