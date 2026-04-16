# KG Discovery Engine

**KGオペレータパイプラインによる科学的仮説自動生成・評価の実験的検証**

Knowledge Graph (KG) オペレータパイプラインを用いて、科学的仮説を自動生成・評価するシステムの実験的検証。

---

<<<<<<< HEAD
## 現フェーズ: P9 完了 → P10 計画中
=======
## 現フェーズ: P6 完了 → P7 設計済み（実装待ち）
>>>>>>> claude/eager-haibt

| フェーズ | 内容 | 状態 | 結論 |
|---------|------|------|------|
| P1 | 仮説 H1-H3 検証、density-aware selection | 完了 | density causal artifact 確認 |
| P2 | Structure-aware discovery framework | 完了 | density-selection 相関確認 |
| P3-A | KG augmentation causal isolation (run_031) | 完了 | augmentation null under shortest-path |
| P3-B | Selection redesign, augmentation reachability (run_032) | 完了 | augmentation 到達可能でも無効 |
<<<<<<< HEAD
| P4 | Evidence-aware path quality ranking (run_033) | 完了 | R3 +5.7pp (p=0.677) |
| P5 | Evidence-gated KG augmentation (run_034) | 完了 | FAIL: structural exclusion が真のボトルネック |
| P6-A | Bucketed selection by path length (run_036) | 完了 | T2 WEAK_SUCCESS: inv=0.929 |
| P7 | Multi-domain KG expansion (run_038) | 完了 | **STRONG_SUCCESS: inv=0.9857** |
| P8 | ROS family expansion (run_040) | 完了 | **DESIGN_PRINCIPLE confirmed** |
| **P9** | **NT family transfer test (run_041)** | **完了** | **GEOMETRY_ONLY: investigability 不転移** |
| P10 | T3 investigability pre-filter | 計画中 | — |
=======
| **P4** | **Evidence-aware path quality ranking (run_033)** | **完了** | **R3 +5.7pp (p=0.677)** |
| **P5** | **Evidence-gated KG augmentation (run_034)** | **完了** | **FAIL: structural exclusion が真のボトルネック** |
| **P6-A** | **Bucketed selection by path length (run_036)** | **完了** | **T2 WEAK_SUCCESS: inv=0.929, novelty_ret=0.905** |
| **P6-ranker** | **T2×R2 vs T2×R3 ranker comparison (run_037)** | **完了** | **等価確認: Δ=0 → P7 default=R3** |
| **P7** | **KG expansion — geometry ceiling test** | **設計済み** | **事前登録完了、実装待ち** |
>>>>>>> claude/eager-haibt

---

## P9 結論（run_041）— 最新

### Decision: GEOMETRY_ONLY — 設計原理はフロンティア文献に特異的

P9 は酸化ストレスファミリーで確立した多ドメイン交差設計原理が、神経伝達物質（NT）ファミリーでも成立するかを検証した。

| 条件 | Nodes | T3 inv | B2 inv | cdr_L3 | mc_L3 | 結果 |
|------|-------|--------|--------|--------|-------|------|
| C_P7_FULL | 10 | 0.9857 | 0.9714 | 0.619 | 190 | STRONG_SUCCESS |
| C_P6_NONE | 0 | 0.9429 | 0.9429 | 0.333 | 0 | NULL |
| **C_NT_ONLY** | **5** | **0.8571** | **0.9714** | **0.605** | **173** | **GEOMETRY_CONFIRMED** |
| C_COMBINED | 12 | 0.9429 | 0.9857 | 0.816 | 665 | WEAK_SUCCESS |

**仮説評価（全 H_P9_x 失敗）**:

| 仮説 | 予測 | 結果 | 判定 |
|------|------|------|------|
| H_P9_STRONG: C_NT_ONLY STRONG_SUCCESS | inv ≥ 0.986 | 0.8571 | ✗ |
| H_P9_COMBINED: C_COMBINED ≥ C_P7_FULL | regression なし | −0.043 | ✗ |
| H_P9_TRANSFER: family_transfer ≥ 0.95 | ≥ 0.95 | 0.8695 | ✗ |
| H_P9_DISPERSION: Gini < 0.4 | < 0.4 | 0.400 | ✗ |

**主要発見:**

<<<<<<< HEAD
1. **幾何学は転移する; investigability は転移しない**  
   C_NT_ONLY は cdr_L3=0.605（P7 の 97.7%）を達成。しかし T3 inv=0.8571 — ベースラインより悪化。

2. **B2 vs T3 ギャップ（重大発見）**  
   B2（グローバルランキング）= 0.9714; T3（バケット層別化）= 0.8571。差 = −0.114。  
   T3 のバケット強制が新ブリッジファミリーの investigability ボトルネックを増幅する。

3. **Serotonin = 0 investigated paths**  
   serotonin × うつ病の PubMed 論文は 486 本あるが、セロトニン経由の T3 パスは 0 本。  
   一般的な関連の coverage ≠ フロンティア研究の investigability。

4. **精緻化された設計原理**:
   > **設計原理は幾何学に対しては汎用的だが、文献フロンティアに対して特異的**  
   > criterion (3) には general coverage ではなく 2024-2025 のフロンティア活性が必要。
=======
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
>>>>>>> claude/eager-haibt

---

## P8 結論（run_040）— DESIGN_PRINCIPLE confirmed

### ROS family expansion: 設計原理の普遍性確認

| 条件 | T3 inv | cdr_L3 | mc_L3 | 結果 |
|------|--------|--------|-------|------|
| C_ROS_ALL (5-bridge) | 0.9857 | 0.740 | 389 | STRONG_SUCCESS |
| C_ROS_GLUTATHIONE | 0.9857 | 0.619 | 190 | STRONG_SUCCESS |
| C_ROS_SUPEROXIDE | 0.9857 | 0.619 | 190 | STRONG_SUCCESS |
| C_BASELINE | 0.9429 | 0.333 | 0 | NULL |

**結論**: ROS ファミリー内のどの組み合わせでも STRONG_SUCCESS → 設計原理は ROS ファミリー内で普遍的。

---

## P7 結論（run_038）— ブレークスルー

### Multi-domain KG expansion: geometry ceiling 突破

| 条件 | T3 inv | cdr_L3 | mc_L3 | 結果 |
|------|--------|--------|-------|------|
| C_GEOMETRY_CEILING | 0.9429 | 0.333 | 0 | NULL |
| **C_P7_EXPANDED** | **0.9857** | **0.619** | **190** | **STRONG_SUCCESS** |

**キーブレークスルー**: 酸化ストレス中間体（glutathione, ROS）を KG に追加することで、bio→chem→bio の多ドメイン交差パスが生成され、STRONG_SUCCESS を達成。

---

## P6-A 結論（run_036）

### T2 WEAK_SUCCESS: inv=0.929, novelty_ret=0.905

| 条件 | Inv Rate | Novelty Ret | Long-path |
|------|----------|-------------|-----------|
| B2 (global R3) | 0.943 | 1.000 | 0% |
| T1 (3-bucket) | 0.943 | 0.808 ✗ | 50% |
| **T2 (2-bucket)** | **0.929** | **0.905 ✓** | **29%** |

---

## P7-P9 設計原理の累積エビデンス

| フェーズ | 実験 | 設計原理の要素 | 結果 |
|---------|------|--------------|------|
| P7 (run_038) | 酸化ストレスブリッジ追加 | 多ドメイン交差パスの生成 | ✓ STRONG_SUCCESS |
| P8 (run_040) | ROS ファミリー全体テスト | ROS 内どのメンバーでも有効か | ✓ 全組み合わせ STRONG_SUCCESS |
| P9 (run_041) | NT ファミリー置換テスト | 設計原理はドメイン非依存か | ✗ 幾何学のみ転移、GEOMETRY_ONLY |

**確立された設計原理**:
> 多ドメイン交差設計原理は bio→chem→bio 構造（幾何学）では汎用的だが、  
> investigability（2024-2025 フロンティア活性）は酸化ストレスファミリーに特異的。

---

## 仮説

| ID | 仮説 | 状態 |
|----|------|------|
| H1 | multi-operator KG pipelineはsingle-operator methodsより有用な仮説を生成する | 部分支持（C1 gap 確認済み） |
| H2 | 入力KGの完璧化よりも下流の評価レイヤーの強化が重要 | P3 で支持 |
| H3 | cross-domain KG操作はsame-domain操作より新規性の高い仮説を生成する | 支持（P7-P9 で確認） |
| H4 | provenance-aware evaluationは仮説ランキングの品質を向上させる | P4 で部分支持 |
| **H_DESIGN** | **多ドメイン交差設計原理は chemistry family 非依存** | **P9 で否定 — フロンティア特異的** |

---

## クイックスタート

```bash
# 依存なし（標準ライブラリのみ）
python -m pytest tests/ -v

# P9: NT family transfer test (run_041)
python -m src.scientific_hypothesis.run_041_p9_nt_family

# P8: ROS family expansion (run_040)
python -m src.scientific_hypothesis.run_040_p8_ros_expansion

# P7: Multi-domain KG expansion (run_038)
python -m src.scientific_hypothesis.run_038_p7_kg_expansion
```

---

## ディレクトリ構造

```
docs/scientific_hypothesis/   # 設計ドキュメント
  hypotheses.md               — 検証仮説 H1-H4 + H_DESIGN
  operators.md                — オペレータ仕様
  evaluation_rubric.md        — スコアリング基準

runs/
  run_031_causal_validation/       — P3-A
  run_032_selection_redesign/      — P3-B
  run_033_evidence_aware_ranking/  — P4
  run_034_evidence_gated_augmentation/ — P5
  run_036_bucketed_selection/      — P6-A
  run_038_p7_kg_expansion/         — P7 STRONG_SUCCESS
  run_039_ablation_ros_family/     — P7 ablation
  run_040_p8_ros_expansion/        — P8 DESIGN_PRINCIPLE
  run_041_p9_nt_family/            — P9 GEOMETRY_ONLY ← 最新

src/scientific_hypothesis/
  build_p7_kg.py              — P7 KGビルダー
  build_p8_kg.py              — P8 KGビルダー
  build_p9_kg.py              — P9 KGビルダー（NT nodes）
  run_038_p7_kg_expansion.py  — P7 実験
  run_039_ablation.py         — P8 ablation
  run_040_p8_ros_expansion.py — P8 実験
  run_041_p9_nt_family.py     — P9 実験
  bio_chem_kg_full.json       — ベース KG (200 nodes)
  bio_chem_kg_p7.json         — P7 KG (210 nodes)
  bio_chem_kg_p8.json         — P8 KG (215 nodes)
```

---

## 技術スタック

- Python 3.11+（標準ライブラリのみ、外部依存なし）
- 決定論的動作（seed=42）
- PubMed E-utilities（レート制限: 1 req/sec）
