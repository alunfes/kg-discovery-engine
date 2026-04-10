# Phase 3 Readiness Memo

**Date**: 2026-04-10
**Basis**: Run 001–006 (Phase 2 complete)
**Author**: Phase 2 最終キャリブレーション (session: awesome-volhard)

---

## 1. Phase 2で修正したこと

### Run 005: 公平比較の実現
- **変更**: 候補バジェット制御 (top-N, N=min候補数) を導入
- **変更**: Cohen's d効果量による H1 判定（任意10%閾値を廃棄）
- **発見**: バジェット制御後、C2のmulti-op優位性は消失 (d=-0.058, negligible)
- **発見**: C1がbridge_kgを使用すれば、multi-opなしでも同等品質の仮説が生成される

### Run 006: Tautological要素の除去 + Evaluator品質向上
- **変更**: `cross_domain_novelty_bonus=False` フラグを追加し、prescriptive +0.2を除去
- **変更**: `testability_heuristic=True` フラグを追加、定数0.6を関係種別ヒューリスティックに置換
- **発見**: H3 PASS は設計依存だった — ボーナス除去後 ratio=1.0 (FAIL)
- **発見**: testabilityヒューリスティックは変動するが (std=0.036 > 0)、toy dataのrelation偏りのため弁別力改善には至らなかった

---

## 2. Phase 2で残った弱点

### (a) トイデータの構造的限界
- 全KGは手作りの12-15ノード規模: 実世界のスケールとは2-3桁異なる
- relation種別がmeasurable偏重: inhibits/activates/catalyzes等が支配的
- cross-domain接続は手動設計: 実データでは自然発生するはず
- **影響**: testabilityヒューリスティック、H3 intrinsic novelty、H1の全てでtoy dataの偏りが結果を歪める

### (b) 仮説の正直な信頼度評価

| 仮説 | 最終状態 | 正直な信頼度 | 問題の核心 |
|------|---------|------------|----------|
| H1 | FAIL (6 Runs) | **Low** | toy data飽和 + 閾値設定無根拠 + 実データで未検証 |
| H2 | 部分支持 | **Medium** | survivorship bias — degradation < 20%はcandidate数減少による |
| H3 | 設計整合性のみ | **Low (内在性は未証明)** | prescriptive scoring → tautology確認済み |
| H4 | 条件付き支持 | **Medium** | engineered KGのみ、実データでの検証なし |

### (c) プレースホルダーのまま残っているもの
- `analogy_transfer_placeholder()`: 未実装。Phase 2中に一度も使用されていない
- `belief_update_placeholder()`: 未実装。同上
- C3 (direct baseline): 常に空リスト返却 — baseline比較が未確立
- gold-standard ranking: H4で使うproxyは "heuristic proxy" であり、人間専門家評価ではない

---

## 3. Phase 3への準備状態判定

### 判定: **Conditional Go**

#### Go の根拠
1. **パイプラインの信頼性**: 6 Runsを通じてバグなく安定動作
2. **テストカバレッジ**: 115テスト全パス、主要コンポーネント網羅
3. **実験設計の成熟**: 公平比較、Cohen's d、hypothesis-level評価など方法論が確立
4. **失敗パターンの把握**: tautological scoring、survivorship bias、threshold設定の落とし穴を全て文書化済み

#### Conditional の条件（Phase 3前に解決すべき）
1. **C3 baseline を実装** — real dataではtemplate-based generationは意味を持つ
2. **評価フレームワークのスケール確認** — 実データKGは数千〜数万ノード: compose()のBFS複雑度を確認
3. **analogy_transfer / belief_update の設計決定** — Phase 3で使わないなら削除、使うなら設計する

---

## 4. 推奨する最初の実データ実験

### 候補データソース

| ソース | ノード規模 | エッジ規模 | メリット | デメリット |
|--------|----------|----------|---------|----------|
| **WikiData subset (bio+chem)** | ~500-2000 | ~1000-5000 | 構造化済み, SPARQL取得可, 多ドメイン | ライセンス確認要, 前処理コスト中 |
| **PubMed abstracts → KG** | ~200-1000 | ~500-3000 | リアルな科学テキスト, NLPパイプライン例多数 | NLP前処理コスト高, 精度依存 |
| **STRING DB (protein-protein)** | ~1000 | ~5000 | 高品質, 直接KG形式, bio領域に特化 | 単一ドメイン → H3検証には不向き |
| **DBpedia bio+chem subset** | ~500-1500 | ~1000-4000 | 多ドメイン, 公開, Python取得簡単 | 品質ムラあり |

**推奨**: **WikiData bio+chem subset** — multi-domain (biology + chemistry) が確保でき、H1・H3を実データで再検証できる。

### 必要な前処理
1. SPARQLでbiology/chemistry entityを500件ずつ取得
2. is_a / part_of / catalyzes / inhibits 等の主要関係に絞りKG構築
3. KGNode/KGEdge形式に変換するアダプタを `src/kg/real_data.py` に実装
4. domain ラベルの付与 (WikiDataのQ番号からbio/chem判定)

### 期待される規模
- ノード: 500-2000
- エッジ: 2000-8000
- compose()の候補数: 数千〜数十万（BFS最適化が必要になる可能性）

### 成功基準
実データPhase 3 の成功基準:

| 指標 | 成功条件 |
|------|---------|
| H1 (multi-op superiority) | Cohen's d ≥ 0.2 on real data (toy dataでは達成不可だった) |
| H3 (cross-domain novelty) | ratio ≥ 1.20 **without** cross_domain_novelty_bonus (intrinsic superiority) |
| H2 (noise robustness) | degradation < 20% at 30% edge deletion on real KG |
| H4 (provenance-aware) | Spearman(aware) > Spearman(naive) on KG with real 1-hop/2-hop/3-hop mix |
| パイプライン稼働 | 実データで end-to-end が動作する |

---

## 5. Phase 2 総括

### できたこと
- KGオペレータパイプラインの完全実装と検証 (6 Runs, 115テスト)
- H2 PASS, H4 PASS (条件付き)
- tautological scoringの発見と除去
- 実験設計の方法論的成熟 (公平比較、効果量、hypothesis-level評価)

### できなかったこと / 正直な認識
- H1はtoy dataの限界に達しており、実データなしに結論は出せない
- H3のPASSは実装内部整合性の確認に過ぎず、科学的発見ではない
- 全ての評価指標はheuristicベースであり、外部gold-standardとの比較はゼロ

### Phase 3へのメッセージ
Phase 2が残した最も重要な資産は「失敗パターンの文書化」と「健全なインフラ」である。  
スコアリングのtautology、survivorship bias、threshold設定の罠を事前に知っているため、  
Phase 3では同じ過ちを避けた実験設計が可能。
