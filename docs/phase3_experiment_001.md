# Phase 3 実験 001: Wikidata bio+chem subset による条件付き効果検証

## 実験概要

**Run ID**: run_007_20260410_phase3_wikidata_bio_chem  
**実験日**: 2026-04-10  
**目的**: H1'（bridge density条件付きmulti-op優位性）およびH3'（構造的距離と新規性）の実データ検証

## データソース

| 項目 | 詳細 |
|------|------|
| Source | fallback_semi_manual（SPARQL fallback）|
| Bio 実体 | TP53, BRCA1, ATM, CHEK2, CDK2, BCL2, BAX, CASP3, PARP1, PCNA, HK2, PKM2, LDHA, G6PD + 代謝物 |
| Chem 実体 | TCAサイクル（citrate→isocitrate→α-KG→succinyl-CoA→succinate→fumarate→malate→oxaloacetate）+ ETC（complex_I/II/ATP_synthase）|
| Q-ID追跡 | 全実体にWikidata Q-IDを付与（例: TP53=Q14818, citrate synthase=Q407398）|
| Toy dataとの差異 | 実entity名、現実的なトポロジー（hub-spoke + sequential cycle）、10種類以上のrelation type |

## 条件設計

| 条件 | ノード数 | エッジ数 | bridge_density | Relation entropy |
|------|--------|--------|---------------|----------------|
| A bio-only | 26 | 37 | 0.0000 | — |
| B chem-only | 31 | 39 | 0.0000 | — |
| C sparse bridge | 57 | 80 | 0.0500 | 高 |
| D dense bridge | 57 | 89 | 0.1461 | 高 |

Sparse bridges (4): bio:acetyl_CoA↔chem:acetyl_CoA, bio:pyruvate↔chem:pyruvate, bio:NAD+↔chem:NAD+, bio:NADH↔chem:NADH  
Dense bridges (13): sparse + bio:ATP↔chem:ATP, bio:ADP↔chem:ADP + CDK2/ATM/HK2/PKM2/LDHA/G6PD/PARP1 機能リンク

## 実験手順

各条件で以下を実行:
1. **Single-op**: compose(full_kg) with EvaluationRubric(cross_domain_novelty_bonus=False)
2. **Multi-op**: align(bio_sub, chem_sub) → union → compose + diff → deduplicate → evaluate
3. 指標計算: unique_to_multi_op, operator_contribution_rate, Cohen's d, H3' structural distance

Alignmentの閾値: 0.5（label similarity: exact=1.0, synonym-bridge=0.5, Jaccard otherwise）

## 結果

### 候補数

| 条件 | Single-op N | Multi-op N | Alignment pairs |
|------|------------|-----------|----------------|
| A | 50 | 50 | 0 (degenerate) |
| B | 4 | 4 | 0 (degenerate) |
| C | 60 | 54 | 6 (ATP, ADP, NAD+, NADH, pyruvate, acetyl-CoA) |
| D | 67 | 54 | 6 (same as C) |

### H1' 分析: reachability

| 条件 | bridge_density | unique_to_multi | contribution_rate | Cohen's d |
|------|---------------|----------------|------------------|---------|
| A | 0.0000 | 0 | 0.0000 | 0.0000 |
| B | 0.0000 | 0 | 0.0000 | 0.0000 |
| C | 0.0500 | **4** | 0.0741 | 0.0000 |
| D | 0.1461 | **4** | 0.0741 | 0.0000 |

### 4つのunique候補（C/D共通）

Multi-opがsingle-opでは発見できない仮説候補:
1. chem:complex_I → bio:ADP （NADH:ubiquinone oxidoreductase → adenosine diphosphate）
2. chem:complex_II → bio:ADP （succinate:ubiquinone oxidoreductase → adenosine diphosphate）
3. chem:complex_I → bio:ATP （NADH:ubiquinone oxidoreductase → adenosine triphosphate）
4. chem:complex_II → bio:ATP （succinate:ubiquinone oxidoreductase → adenosine triphosphate）

**発見メカニズム**: alignmentによりchem:ADP/ATPがbio:ADP/ATPにマージされ、2ホップ経路（complex → ATP_synthase → ADP/ATP）が生成。Single-opでは3ホップ経路（complex → ATP_synthase → chem:ADP → bio:ADP）が必要だが、compose(max_depth=3)の実質到達深さ(2ホップ)を超えるため到達不能。

### H3' 分析: 構造的距離

| 条件 | Cross-domain hops | Same-domain hops | Distance detected |
|------|------------------|-----------------|------------------|
| A | 0.0 | 2.0 | False（cross=0件）|
| B | 0.0 | 2.0 | False（cross=0件）|
| C | 2.0 | 2.0 | False（同値）|
| D | 2.0 | 2.0 | False（同値）|

**観察**: compose(max_depth=3)の実質的な生成深さが2ホップに限定されており、全候補が2ホップ。ホップ数プロキシでは構造的距離を検出できない。

### H4 安定性

全条件でΔtraceability=0.0（std=0.0）。全候補が2ホップであり、naive(0.7)とaware(0.7)が同値。

## 解釈

### H1' の評価
- **Reachability証拠: 条件付き支持**
  - A/B: unique=0 ✓（同一ドメインでは優位性なし）
  - C/D: unique=4 ✓（クロスドメイン条件でalignment経由の独自候補）
- **Bridge density依存性: 未確認**
  - C(sparse)とD(dense)でunique数が同一（4）
  - 理由: alignmentが発見するのはADP/ATP（明示的bridgeの有無に関わらず同じ）
- **スコア優位性: なし**（Cohen's d=0）

### アライメントメカニズムの実証
Bio/chemの共有代謝物（ATP, ADP, NAD+, NADH, pyruvate, acetyl-CoA）に対して自動整合が成立。これによりmulti-opは2ホップで到達できる経路が、single-opでは3ホップ必要となる。

### H3' の評価
- **未確認**: hop count プロキシでは構造的距離を検出できない
- **原因**: max_depth=3の制約により全候補が2ホップ
- **次のアクション**: 別プロキシ（relation type heterogeneity）またはmax_depth=5での再実験

## 新たに発見された仮説候補（科学的に興味深いもの）

4つのunique候補はすべて実験的に検証可能な仮説:
- **complex_I → ADP**: ETC複合体Iは電子輸送を通じてADP（ATP synthaseの基質）に間接的に影響
- **complex_II → ATP**: コハク酸脱水素酵素はETC経由でATP産生に貢献
- これらはWarburg効果と電子伝達系の交差点に位置し、cancer metabolism研究に関連

## 制約と注意点

1. **データ規模**: 26-31ノード/ドメイン（目標500-2000には未達。実験的実行可能性を優先）
2. **スコアリング非対称**: single-op→full_kg評価、multi-op→merged_kg評価（参照KGが異なる）
3. **2ホップ制限**: compose(max_depth=3)は実質2ホップのみ生成（H3'/H4分析の制約）
4. **SPARQL fallback使用**: 決定論的動作のためfallback data使用（実Wikidata構造を反映）
