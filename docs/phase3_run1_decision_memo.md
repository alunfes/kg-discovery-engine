# Phase 3 Run 1 Decision Memo

**日付**: 2026-04-10  
**Run**: run_007_20260410_phase3_wikidata_bio_chem

---

## 何をテストしたか

1. **H1'**: Wikidata bio+chem実データを用いて、4つのbridge density条件（A/B/C/D）でmulti-op vs single-op を比較
2. **H3'**: no-bonus条件でcross-domainのstructural distance（hop count proxy）
3. **H4 stability**: 4条件を通じたprovenance-aware rankingの安定性

## 何をテストしなかったか

- 500-2000ノード規模の実データ（26-31ノード/ドメインで実行）
- max_depth=5での3ホップ以上の経路探索（全候補が2ホップ）
- SPARQLからの生データ（タイムアウト/不安定のためfallback使用）
- H2（ノイズ頑健性）の実データ版（Phase 3 Run 2以降へ）
- graph edit distance等の高度な構造的距離メトリクス

---

## 条件付きH1'のエビデンス

### 支持されること
- **Reachability優位性の確認**: 同一ドメイン（A/B）ではunique=0、クロスドメイン（C/D）ではunique=4
- **メカニズムの解明**: alignmentによるADP/ATPのマージが2ホップ経路を生成（single-opでは3ホップ必要）
- **実データでの再現**: toy dataと同様の「alignment-derived reachability」が実データでも成立

### 支持されないこと（修正が必要な点）
- **Bridge density依存性**: CとDでunique数が同一（4）→ 「sparse bridge条件でより有効」という予測は未確認
- **スコア優位性**: Cohen's d=0（品質差なし）→ H1'はreachabilityの問題で品質の問題ではない
- **H1'の解釈修正**: 「sparse bridge条件でのみ有効」ではなく「bridge density依存なく、alignment可能な共有概念がある場合に有効」

### H1'の修正定式化（Run 1後）

> **H1'（修正）**: multi-op pipelineはcross-domain条件でsingle-opが到達不能な候補を生成する。この優位性はbrdige densityより、各ドメインに整合可能な共有概念（aligned nodes）が存在するかどうかに依存する。

---

## 条件付きH3'のエビデンス

### 観察
- C/D: cross-domainとsame-domainの平均ホップ数が同値（2.0 vs 2.0）
- Hop countプロキシでは構造的距離を検出できない

### 原因分析
- compose(max_depth=3)が実質2ホップのみ生成するため、全候補が同じパス長
- 構造的距離の検出にはhop count以外のプロキシが必要

### H3'のエビデンス: なし（適切なプロキシが必要）

次のアクション:
1. max_depth=5で3ホップ候補を生成し、hop count差を再測定
2. Relation type heterogeneity（cross-domainパスが使うrelation種別の多様性）を代替プロキシとして実装

---

## 実データでのprovenance-aware evaluationの有用性

**H4 stability**: Δtraceability=0（全条件で同一）  
理由: 全候補が2ホップ → naive(0.7)とaware(0.7)が同値  
結論: 2ホップのみのデータでは、provenance-aware有無を区別できない

次の実験での設計変更:
- max_depth=5を使用して3ホップ候補を含める
- → naive(0.7) vs aware(0.5) の差が生まれ、H4を意味のある形でテスト可能

---

## 次の最高価値実験

### 優先度1: Phase 3 Run 2 — max_depth=5での再実験
**目的**: 3ホップ候補を含めてH3'/H4を適切にテスト  
**変更点**: compose(max_depth=5)  
**期待値**: cross-domain候補がより多くの3ホップパスを含み、structural distance検出可能  
**コスト**: 実験規模がO(n^2)で増加、適切な上限が必要

### 優先度2: Phase 3 Run 3 — Relation type heterogeneity
**目的**: H3'の代替プロキシとして relation type entropy の比較  
**変更点**: analyze_h3_structural_distance()にrelation diversity計算を追加  
**期待値**: cross-domainパスがmulti-step reactionなど多様なrelationを使用する場合に検出

### 優先度3: データ拡大 — SPARQL実データ取得
**目的**: 500-2000ノード規模でのH1'検証  
**変更点**: src/data/wikidata_loader.pyのSPARQL quertiesを強化  
**期待値**: 大規模グラフでbrdige densityの効果がより明確に分離される可能性

### 優先度4: Phase 3 Run 4 — noisy real data (H2 real-data版)
**目的**: 実データノイズ環境でのevaluator頑健性  
**変更点**: build_noisy_kg()を実データに適用（30/50%エッジ削除）  
**期待値**: toy dataで確認したH2（劣化<20%）が実データでも成立するか

---

## 総括

Phase 3 Run 1は以下を達成した:
1. ✅ 実データ（Wikidata Q-ID付き）での実験パイプライン確立
2. ✅ Alignment-derived reachability優位性の実データ確認（4 unique candidates）
3. ✅ メカニズム解明（alignment→ノードマージ→パス短縮→2ホップ到達）
4. ⚠️ Bridge density依存性: 未確認（C=D=4 unique）
5. ❌ H3' structural distance: hop count プロキシでは検出不能
6. ❌ H4 provenance stability: 2ホップのみデータでは区別不可能

Run 1の主な貢献: 実データでのmulti-op reachabilityメカニズム解明と、次実験（max_depth=5）設計根拠の確立。
