# Phase 3 Plan: Real-Data Conditional H1/H3 Verification

## 目的

Phase 2でtoy dataの飽和を確認したため、Phase 3では実データ（Wikidata bio+chem subset）を用いて再定式化仮説を検証する。

## 再定式化された研究課題

Phase 2「multi-opは普遍的に強いか？」→ Phase 3「どのような構造的条件でmulti-opはsingle-opを上回るか？」

1. **H1'**: multi-op pipeline は sparse-bridge または high-compositionality 条件下でのみ single-op を上回る
2. **H3'**: cross-domain 操作は domain distance が構造的に意味のある場合にのみ新規性を増加させる

## データ構築戦略

### ソース
- Primary: Wikidata SPARQL (https://query.wikidata.org/sparql)
- Fallback: curated semi-manual subset（実Wikidata Q-ID付き、決定論的）

### Biology subgraph（実体）
- DNA損傷応答ネットワーク: TP53, BRCA1, ATM, CHEK2, MDM2, CDK2, CDKN1A, RB1, BCL2, BAX, CASP3, PARP1, PCNA
- Warburg代謝: HK2, PKM2, LDHA, G6PD
- 共有代謝物: ATP, ADP, NAD+, NADH, pyruvate, glucose, lactate, acetyl-CoA
- 合計: ~26ノード, ~37エッジ, 7種類のリレーション

### Chemistry subgraph（実体）
- TCAサイクル: citrate, isocitrate, α-KG, succinyl-CoA, succinate, fumarate, malate, oxaloacetate
- TCA酵素: citrate synthase, aconitase, isocitrate DH, α-KG DH, succinyl synth, succinate DH, fumarase, malate DH, pyruvate DH
- 電子伝達系: complex_I, complex_II, ATP synthase
- 補因子: NAD+, NADH, FAD, FADH2, CoA, GTP, ATP, ADP
- 合計: ~31ノード, ~39エッジ, 4種類のリレーション

### 4条件

| 条件 | グラフ構成 | bridge_density | 特徴 |
|------|-----------|----------------|------|
| A | bio only | 0% | 同一ドメインbaseline |
| B | chem only | 0% | 同一ドメインbaseline |
| C | bio+chem+sparse bridges | ~5% | スパースbridgeテスト |
| D | bio+chem+dense bridges | ~15% | denseブリッジテスト |

bridge_sparse (4): acetyl-CoA, pyruvate, NAD+, NADH のsame_asリンク
bridge_dense (13): sparse + ATP, ADP + キナーゼ-エネルギーリンク

## H1'の分析方法

Reachability-first approach（Phase 2のCohen's d中心から転換）:
1. **unique_to_multi_op** : single-opで到達不能な(subject, object)ペア数（最重要指標）
2. **operator_contribution_rate**: multi-op候補のうちunique割合
3. Cohen's d（スコア差）: 参考値（異なる参照グラフへのスコアリングのため補助的）

H1'の評価基準:
- C/D: unique_to_multi_op > 0 → alignment-derived reachabilityが存在
- A/B: unique_to_multi_op = 0 → 同一ドメインでは優位性なし
- Bridge densityの関数として可視化

## H3'の分析方法

No bonus approach（Phase 2でボーナス除去→FAIL確認済み）:
- EvaluationRubric(cross_domain_novelty_bonus=False)を使用
- 構造的距離のプロキシ: mean hop count (cross-domain vs same-domain)
- 別プロキシ候補: relation type heterogeneity

## 技術的制約

- 外部API禁止（SPARQL fallbackで対処）
- random.seed(42)固定
- compose()はmax_depth=3（実質2ホップ候補のみ）
- 全テストは標準ライブラリのみ

## 成果物

- `runs/run_007_20260410_phase3_wikidata_bio_chem/` 実験アーティファクト
- `docs/phase3_hypothesis_reframing.md` H1'/H3'正式定義
- `docs/phase3_experiment_001.md` 実験詳細
- `docs/phase3_run1_decision_memo.md` 結果解釈と次回実験
