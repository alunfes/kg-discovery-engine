# Run 007 Review Memo

**Run ID**: run_007_20260410_phase3_wikidata_bio_chem  
**Phase**: Phase 3 / Run 1  
**日付**: 2026-04-10  
**ブランチ**: claude/thirsty-bose

---

## 実験設定サマリー

- データ: Wikidata-derived semi-manual subset（bio 26ノード, chem 31ノード）
- 4条件: A(bio-only), B(chem-only), C(sparse bridge 5%), D(dense bridge 15%)
- 評価: EvaluationRubric(cross_domain_novelty_bonus=False)
- Alignment threshold: 0.5

---

## 主要結果

| 条件 | Single-op N | Multi-op N | Alignment | Unique-to-multi | Cohen's d |
|------|------------|-----------|---------|----------------|---------|
| A bio-only | 50 | 50 | 0 pairs | 0 | 0.000 |
| B chem-only | 4 | 4 | 0 pairs | 0 | 0.000 |
| C sparse | 60 | 54 | 6 pairs | **4** | 0.000 |
| D dense | 67 | 54 | 6 pairs | **4** | 0.000 |

### Unique candidates (C/D)
Multi-opのみが到達できる4候補:
- chem:complex_I/II → bio:ADP/ATP
- メカニズム: alignment(chem:ADP→bio:ADP等)によるノードマージ → 2ホップ経路生成

---

## 仮説評価

| 仮説 | Run 007結果 | 注記 |
|------|-----------|------|
| H1' reachability | **部分支持** | C/D で unique=4 (A/B=0) |
| H1' bridge-density依存 | **未確認** | C=D=4 (sparse=dense) |
| H3' structural distance | **未検出** | hop count proxy: cross=same=2.0 |
| H4 provenance stability | **trivially stable** | Δ=0 (全2ホップ) |

---

## 発見メカニズム

```
Multi-op alignment effect:
  bio:ADP ↔ chem:ADP (sim=1.0: "adenosine diphosphate")
  bio:ATP ↔ chem:ATP (sim=1.0: "adenosine triphosphate")

  → union() merges chem:ADP into bio:ADP
  → Path: chem:complex_I → chem:ATP_synthase → bio:ADP (2 hops in merged_kg)
  
Single-op limitation:
  → Path: chem:complex_I → chem:ATP_synthase → chem:ADP → bio:ADP (3 hops in full_kg)
  → compose(max_depth=3) effectively reaches only 2-hop nodes
  → 3-hop path NOT generated → complex_I→ADP not found by single-op
```

---

## 問題・制約

1. **max_depth制約**: compose(max_depth=3)は実質2ホップのみ → H3'/H4の適切なテスト不可
2. **スコアリング非対称**: single→full_kg評価, multi→merged_kg評価（参照KGが異なる）
3. **データ規模**: 26-31ノード（目標500-2000未達）

---

## 次回実験への推奨

**最優先**: Run 008 — max_depth=5での再実験
- compose(max_depth=5)で3ホップ候補を生成
- H3' hop count proxy が機能するようになる
- H4: 3ホップ候補がaware>naive traceability差を生む
- unique_to_multi数の増加を期待（より多くの深いクロスドメイン経路）

**コスト**: 候補数がO(n^2)で増加するため、budget_n上限（top-100等）を設ける
