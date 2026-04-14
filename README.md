# KG Discovery Engine

**KGオペレータパイプラインによる科学的仮説自動生成・評価の実験的検証**

Knowledge Graph (KG) オペレータパイプラインを用いて、科学的仮説を自動生成・評価するシステムの実験的検証。

---

## 現フェーズ: P6 完了 → P7 設計済み（実装待ち）

| フェーズ | 内容 | 状態 | 結論 |
|---------|------|------|------|
| P1 | 仮説 H1-H3 検証、density-aware selection | 完了 | density causal artifact 確認 |
| P2 | Structure-aware discovery framework | 完了 | density-selection 相関確認 |
| P3-A | KG augmentation causal isolation (run_031) | 完了 | augmentation null under shortest-path |
| P3-B | Selection redesign, augmentation reachability (run_032) | 完了 | augmentation 到達可能でも無効 |
| **P4** | **Evidence-aware path quality ranking (run_033)** | **完了** | **R3 +5.7pp (p=0.677)** |
| **P5** | **Evidence-gated KG augmentation (run_034)** | **完了** | **FAIL: structural exclusion が真のボトルネック** |
| **P6-A** | **Bucketed selection by path length (run_036)** | **完了** | **T2 WEAK_SUCCESS: inv=0.929, novelty_ret=0.905** |
| **P6-ranker** | **T2×R2 vs T2×R3 ranker comparison (run_037)** | **完了** | **等価確認: Δ=0 → P7 default=R3** |
| **P7** | **KG expansion — geometry ceiling test** | **設計済み** | **事前登録完了、実装待ち** |

---

## P6-A 結論（run_036）— 最新

### Decision: T2 WEAK_SUCCESS

| 条件 | Inv Rate | Novelty Ret | Long-path | 決定 |
|------|----------|-------------|-----------|------|
| B1 (global R1) | 0.886 | 1.000 | 0% | baseline |
| B2 (global R3) | 0.943 | 1.000 | 0% | tentative standard |
| T1 (3-bucket: L2=35,L3=25,L4+=10) | 0.943 | 0.808 ✗ | 50% | STRUCTURE_CONFIRMED_NOVELTY_FAIL |
| **T2 (2-bucket: L2=50,L3=20)** | **0.929** | **0.905 ✓** | **29%** | **WEAK_SUCCESS** |

**主要発見:**
- **機構的仮説確認**: global top-k は構造的に長パスを排除 (T1 long_path_share 0%→50%)
- **新規性幾何制約**: L3 パス (path_length=3) は常に cross_domain_ratio=0.333、novelty 制約 ≥0.90 を満たす最大 L3 quota = **20**
- **L4+ は調査可能** (stratum inv=1.0) だが cross_domain_ratio=0.25 で novelty 制約に違反
- **T2 実用的意義**: 同一 investigability で L3 パス 29% 包含 → path-length 多様性を維持

**P3→P4→P5→P6 連続学習:**

| Phase | 診断 | 結論 |
|-------|------|------|
| P3-A/B | shortest-path selection が augmentation を排除 | ✓ 構造的排除を特定 |
| P4 | evidence ranking で investigability 改善 | ✓ +5.7pp (R3 暫定標準) |
| P5 | evidence gate で augmentation を救えるか | ✗ 構造的排除が支配 |
| **P6-A** | **bucketed selection で長パスを保証** | **✓ T2 WEAK_SUCCESS (novelty OK)** |
| **P6-ranker** | **T2 内部 ranker: R2 vs R3** | **✓ 等価 (Δ=0) → P7 default=R3** |

## P6 総括

**結論: selection architecture の改善だけでは ceiling は破れない。問題は KG の geometry。**

- global top-k の構造的排除は bucketing で解決できる（機構的仮説確認）
- しかし ceiling は inv=0.929–0.943 に留まる（B2 を超えられない）
- 根本原因: L3 パスの cross_domain_ratio=0.333 が novelty 制約 ≥0.90 の下で L3_max=20 を数学的に決定
- reranking・selection 改善は全て同じ geometry ceiling の内側で動く
- **P7 の必要性**: KG の cross-domain connectivity を増やすことだけが ceiling を破れる

詳細: `docs/scientific_hypothesis/p6_conclusion.md`

---

## P5 結論（run_034）

### Decision: FAIL — A = B = C = 0.943

Evidence gate は正しく機能した（5/10 edges PASS）。しかし evidence quality を改善しても
investigability は変わらなかった。

**真のボトルネック: structural exclusion（構造的排除）**

> augmented paths（多くが 3-hop 以上）は R3 の構造項 (40% × 1/path_length) により
> 2-hop の original paths に排除される。top-70 に入る augmented path はわずか 1 本。
> edge の evidence quality ではなく、**selection architecture** が問題。

### P3→P4→P5 連続学習

| Phase | 仮説 | 実験 | 結論 |
|-------|------|------|------|
| P3-A/B | shortest-path selection が augmentation を排除 | run_031-032 | ✓ 確認 |
| P4 | evidence ranking で investigability 改善 | run_033 | ✓ +5.7pp (p=0.677) |
| P5 | evidence gate で augmentation を救えるか | run_034 | ✗ 構造的排除が支配 |

**augmentation 路線クローズ。次の主題: selection architecture。**

---

## P4 結果サマリー（run_033）

### C2 標準ランキング: **R3 (Structure 40% + Evidence 60%)**

| Ranking | Inv Rate | Δ vs baseline | p-value | 備考 |
|---------|----------|--------------|---------|------|
| R1_baseline | 0.886 | — | — | 旧標準 |
| **R3_struct_evidence** | **0.943** | **+0.057** | 0.677 | **新 C2 標準** |
| R2_evidence_only | 0.943 | +0.057 | 0.677 | R3 と同値 |
| R4_full_hybrid | 0.929 | +0.043 | 0.835 | |
| R5_conservative | 0.900 | +0.014 | 1.000 | |
| C1 (baseline) | 0.971 | — | — | 単一オペレータ上限 |

### Decision C — 暫定標準化（N=140+ での confirmatory replication 待ち）

- **R3 +5.7pp 改善**（88.6% → 94.3%）
- **p=0.677 で未有意**（n=70、検出力不足）
- run_035 (N=140) で confirmatory replication を実施予定

### Core Insight (P3→P4→P5)

> PubMed 過去共起 (≤2023) が 2024-2025 カバレッジを予測する — 確立
> KG augmentation の失敗原因は edge quality ではなく selection architecture — 確立

---

## 仮説

| ID | 仮説 | 状態 |
|----|------|------|
| H1 | multi-operator KG pipelineはsingle-operator methodsより有用な仮説を生成する | 検証中（C1 gap 2.8pp） |
| H2 | 入力KGの完璧化よりも下流の評価レイヤーの強化が重要 | P3 で支持 |
| H3 | cross-domain KG操作はsame-domain操作より新規性の高い仮説を生成する | 支持（cross-domain ratio 一定） |
| H4 | provenance-aware evaluationは仮説ランキングの品質を向上させる | P4 で部分支持（Decision C） |

---

## クイックスタート

```bash
# 依存なし（標準ライブラリのみ）
python -m pytest tests/ -v

# P4: evidence-aware reranking (run_033)
python -m src.scientific_hypothesis.reranking_pipeline

# デフォルトランキング: R3_struct_evidence (Structure 40% + Evidence 60%)
# 変更する場合: reranking_pipeline.py の DEFAULT_RANKER を編集
```

---

## ディレクトリ構造

```
docs/scientific_hypothesis/   # P4 設計ドキュメント
  path_quality_features.md    — WS1 特徴量定義
  evidence_scoring.md         — WS2 evidence スコア定義
  ranking_function_design.md  — WS3 R1–R5 設計根拠
  p4_interpretation.md        — P4 解釈・次ステップ

runs/
  run_031_causal_validation/       — P3-A
  run_032_selection_redesign/      — P3-B
  run_033_evidence_aware_ranking/  — P4
  run_034_evidence_gated_augmentation/ — P5 ← 最新

src/scientific_hypothesis/
  path_features.py            — WS1 特徴量計算
  evidence_scoring.py         — WS2 evidence スコア
  ranking_functions.py        — WS3 R1–R5 実装
  reranking_pipeline.py       — WS4–WS6 フルパイプライン (R3 標準)
  evidence_gate.py            — P5 augmentation evidence gate
  run_p5_evidence_gated.py    — P5 3条件パイプライン
  bio_chem_kg_full.json       — ベース KG (200 nodes, 325 edges)
  bio_chem_kg_gated.json      — P5 gated KG (200 nodes, 330 edges)
```

---

## 技術スタック

- Python 3.11+（標準ライブラリのみ、外部依存なし）
- 決定論的動作（seed=42）
- PubMed E-utilities（レート制限: 1 req/sec）
