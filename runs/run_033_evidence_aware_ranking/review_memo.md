# run_033 review memo — P4 Evidence-Aware Ranking
Generated: 2026-04-14T07:01:58.939895

## Setup
- Pool: top-200 compose candidates from bio_chem_kg_full.json
- Selection: top-70 per ranking
- Evidence window: ≤2023 PubMed co-occurrence
- Validation window: 2024-2025 PubMed investigability

## Results: Investigability by Ranking

| Ranking | Inv Rate | Fail Rate | Mean e_min | Cross-domain |
|---------|----------|-----------|------------|--------------|
| R1_baseline | 0.886 | 0.114 | 1.624 | 0.500 |
| R2_evidence_only | 0.943 | 0.057 | 2.469 | 0.500 |
| **R3_struct_evidence** ← new C2 standard | **0.943** | **0.057** | **2.469** | **0.500** |
| R4_full_hybrid | 0.929 | 0.071 | 2.462 | 0.500 |
| R5_conservative | 0.900 | 0.100 | 2.233 | 0.500 |

## Statistical Tests vs R1 Baseline

| Ranking | Inv Rate | Δ | Cohen's h | p-value | Sig |
|---------|----------|---|-----------|---------|-----|
| R2_evidence_only | 0.943 | +0.0572 | +0.2072 | 0.6768 | no |
| R3_struct_evidence | 0.943 | +0.0572 | +0.2072 | 0.6768 | no |
| R4_full_hybrid | 0.929 | +0.0429 | +0.1488 | 0.8350 | no |
| R5_conservative | 0.900 | +0.0143 | +0.0463 | 1.0000 | no |

## Final Decision: C — Moderate improvement; hybrid approach recommended

**R3 (Structure 40% + Evidence 60%) adopted as C2 暫定標準**

- R1 (baseline) investigability: 0.886
- R3 investigability: 0.943 (+5.7pp, p=0.677)
- Automated threshold fired Decision A (Δ≥0.05), but **p=0.677 は未有意**
- N=70 で検出力不足の可能性 — P5 でより大きなサンプルで検証予定

### ナラティブ
「R3 が勝った」ではなく「**次フェーズの実験の標準土台を更新した**」。
evidence が investigability の支配変数である可能性が高いことは示せたが、
確定には N=140+ が必要。

## Interpretation

### P3 との整合性
- P3: literature-sparse なペアへのエッジ追加 → investigability 低下
- P4: literature-dense なペアを優先 → investigability 向上
- 共通メカニズム: **PubMed 過去共起 (≤2023) が 2024-2025 カバレッジを予測する**

### Evidence-Novelty 直交性
- R2/R4 ともに cross_domain_ratio = 0.500（完全一致）
- 全パスが length-2 のため evidence フィルタが novelty を破壊しない
- **Evidence と novelty は現 KG 上では直交 → evidence 優先で novelty を犠牲にしない**

### R3 採用理由（R2 ではなく）
- R2/R3 は investigability 同値（0.943）
- R3 は構造項 (40%) を残すため、将来 length>2 のパスが増えた際に安定する
- より長いパスや KG 拡張後の汎化性を維持

## Next: P5 Evidence-Gated KG Augmentation
P3 の根本原因（augmented edges are literature-sparse）を直接修正:
1. エッジ追加前に pubmed_count(A AND B, ≤2023) ≥ threshold でゲーティング
2. evidence-gated augmentation の investigability を R3 baseline と比較
3. Expected run: run_034_evidence_gated_augmentation

## Artifacts
- feature_matrix.json: 200 candidates × features
- ranking_comparison.json: per-ranking metrics
- tradeoff_analysis.json: high/low evidence split, novelty retention
- statistical_tests.json: Fisher exact tests
- plots/: 4 HTML diagnostic plots
