# KG Discovery Engine

**KGオペレータパイプラインによる科学的仮説自動生成・評価の実験的検証**

Knowledge Graph (KG) オペレータパイプラインを用いて、科学的仮説を自動生成・評価するシステムの実験的検証。

---

## 現フェーズ: P4 完了 → P5 準備中

| フェーズ | 内容 | 状態 | 結論 |
|---------|------|------|------|
| P1 | 仮説 H1-H3 検証、density-aware selection | 完了 | density causal artifact 確認 |
| P2 | Structure-aware discovery framework | 完了 | density-selection 相関確認 |
| P3-A | KG augmentation causal isolation (run_031) | 完了 | augmentation null under shortest-path |
| P3-B | Selection redesign, augmentation reachability (run_032) | 完了 | **edge quality is the bottleneck** |
| **P4** | **Evidence-aware path quality ranking (run_033)** | **完了** | **Decision C: R3 暫定標準採用** |
| P5 | Evidence-gated KG augmentation (run_034) | 次フェーズ | — |

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

### Decision C — 暫定標準化（確定勝利ではない）

- **R3 +5.7pp 改善**（88.6% → 94.3%）
- **p=0.677 で未有意**（n=70、検出力不足）
- Evidence が investigability の支配変数である可能性が高い
- 確定には N=140+ での再検証が必要
- **「R3 が勝った」ではなく「次の実験の標準土台を更新した」**

### Core Insight (P3→P4)

> PubMed 過去共起 (≤2023) が 2024-2025 カバレッジを予測する  
> literature-sparse なエッジ追加 → 失敗（P3）  
> literature-dense なペアを優先 → 成功（P4）

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
  run_031_causal_validation/  — P3-A
  run_032_selection_redesign/ — P3-B
  run_033_evidence_aware_ranking/ — P4 ← 最新

src/scientific_hypothesis/
  path_features.py            — WS1 特徴量計算
  evidence_scoring.py         — WS2 evidence スコア
  ranking_functions.py        — WS3 R1–R5 実装
  reranking_pipeline.py       — WS4–WS6 フルパイプライン
  bio_chem_kg_full.json       — ベース KG (200 nodes, 325 edges)
```

---

## 技術スタック

- Python 3.11+（標準ライブラリのみ、外部依存なし）
- 決定論的動作（seed=42）
- PubMed E-utilities（レート制限: 1 req/sec）
