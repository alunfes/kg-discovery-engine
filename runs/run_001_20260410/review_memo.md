# レビューメモ — Run 001

**日付**: 2026-04-10
**レビュアー**: Claude (初回セッション)

---

## 現在のプロジェクト状態

**Phase 0 完了**: 基盤実装（KGモデル・オペレータ・評価）が動作する状態
**Phase 1 進行中**: Run 001 実行済み、結果に基づく分析完了

---

## 実装内容

### 実装済み

| コンポーネント | ファイル | 状態 |
|--------------|---------|------|
| KGNode, KGEdge, KnowledgeGraph | `src/kg/models.py` | 完了 |
| HypothesisCandidate | `src/kg/models.py` | 完了 |
| Toy datasets（4ドメイン） | `src/kg/toy_data.py` | 完了 |
| align オペレータ | `src/pipeline/operators.py` | 完了（v0 heuristic） |
| union オペレータ | `src/pipeline/operators.py` | 完了 |
| difference オペレータ | `src/pipeline/operators.py` | 完了 |
| compose オペレータ | `src/pipeline/operators.py` | 完了 |
| analogy-transfer | `src/pipeline/operators.py` | Placeholder |
| belief-update | `src/pipeline/operators.py` | Placeholder |
| EvaluationRubric | `src/eval/scorer.py` | 完了 |
| evaluate関数 | `src/eval/scorer.py` | 完了 |
| 実験ランナー（C1/C2/C3） | `src/pipeline/run_experiment.py` | 完了 |
| 比較スクリプト | `src/pipeline/compare_conditions.py` | 完了 |
| テスト（28件） | `tests/` | 全パス |

---

## 実行結果

```
C1 (single-op): 8件の仮説, mean_total=0.7050
C2 (multi-op):  23件の仮説, mean_total=0.7050
C3 (direct):    0件（placeholder）

H1 判定: FAIL (C2 score == C1 score, 差異なし)
H3 判定: FAIL (cross/same-domain novely 共に 0.8000)
```

---

## 成功点

1. **エンドツーエンドのパイプラインが動作**: align → union → compose → difference → evaluate
2. **C2の探索空間拡大が機能**: 8件 → 23件（+188%の仮説生成）
3. **28テスト全パス**: コードの正確性が保証されている
4. **決定論的動作**: 毎回同じ結果を再現
5. **ドキュメント整備**: goal/hypotheses/operators/rubric/assumptions が揃っている

---

## 問題点

### 問題1: スコアリングが単調（最重要）

現行のヒューリスティックが2ホップパスに一律スコアを付与するため、
C1とC2のmean scoreが等しくなってしまった。

**根本原因**: plausibility/novelty/traceabilityのいずれも、
パス長のみから計算されており、関係の「意味」を考慮していない。

**影響**: H1・H3が数値的に検証できない

### 問題2: アライメントの意味的理解不足

Jaccard文字列類似度では "enzyme" と "catalyst" が対応付けられない。
cross-domainのanalogical reasoningができていない。

**影響**: C2のcross-domain探索のメリットが十分に発揮されていない

### 問題3: C2のcross-domain仮説が少ない

merged KG上でcomposeを実行しているが、bio-chemクロスのパスは
アライメントされたノードを経由してしか生成されない。
現状でアライメントが空のため、クロス仮説がほぼ生まれていない。

---

## 最重要次ステップ

### ステップ1（次セッションの最初にやること）

`src/eval/scorer.py` の `_score_novelty` を修正：
- merged KGのノードのdomainを確認
- subject.domain != object.domain の場合に novelty ボーナスを付与
- これにより cross-domain 仮説が same-domain 仮説より高スコアになる

### ステップ2

`src/pipeline/operators.py` の `align` 関数にドメイン同義語辞書を追加：
```python
SYNONYMS = {"enzyme": ["catalyst"], "inhibit": ["block"], "protein": ["compound"]}
```
これにより概念的cross-domainアライメントが機能し、C2の強みが発揮される

### ステップ3

修正後にRun 002を実行してH1・H3を再検証

---

## アーキテクチャの健全性評価

| 観点 | 評価 | コメント |
|------|------|---------|
| コードの読みやすさ | ✓ Good | 関数が短く目的が明確 |
| 拡張性 | ✓ Good | オペレータの追加が容易 |
| テストカバレッジ | ✓ Good | 28件、主要パスをカバー |
| 決定論性 | ✓ Good | 外部依存なし |
| スコアリング品質 | △ Needs work | ヒューリスティックが単純すぎ |
| アライメント品質 | △ Needs work | 意味的類似度が必要 |
