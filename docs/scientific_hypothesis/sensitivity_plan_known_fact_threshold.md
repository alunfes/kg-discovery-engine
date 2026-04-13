# Sensitivity Analysis 計画 — known_fact Threshold

**作成日**: 2026-04-14  
**Status**: PLAN — 未実施  
**種別**: Exploratory (主解析の結論変更には使わない)

---

## 1. 目的

run_017 では `KNOWN_THRESHOLD = 20`（過去コーパスのヒット数 ≥ 20 で `known_fact` に分類）を使用した。
このしきい値が SC-1r の結論に与える影響を確認するための感度分析を計画する。

**この分析の目的は主解析の結論を変えることではない。**  
目的は「ラベリングの robustness を確認すること」に限定する。

---

## 2. 背景

### 現行 threshold の問題

`KNOWN_THRESHOLD = 20` が低すぎる可能性がある。例として:

- `metformin → NAFLD 改善` は 2023 年以前でも 20 件超ヒットするが、
  「trivially known」とは言い切れない（臨床試験が続いている）
- C2 の known_fact_rate = 0.740 は C_rand_v2 の 0.420 より大幅に高く、
  threshold の影響を受けやすい状態にある

ただし、これが「C2 が本当は novel」だということを意味するわけではない。
ラベリングの閾値選択が結果にどの程度影響するかを定量化するだけである。

---

## 3. テストする threshold

| Threshold | 意味 |
|-----------|------|
| 20 (現行) | 過去コーパスで 20 件以上ヒット → known_fact |
| 50 | 過去コーパスで 50 件以上ヒット → known_fact |
| 100 | 過去コーパスで 100 件以上ヒット → known_fact |
| 200 | 過去コーパスで 200 件以上ヒット → known_fact |

---

## 4. 分析手順

各 threshold について以下を実施する:

1. **再ラベリング**: run_017 の `labeling_results_layer2.json` を読み込み、
   各仮説のヒット数を使って新 threshold で `known_fact` / `novel_supported` / `plausible_novel` を再分類
2. **再集計**: C2 / C1 / C_rand_v2 ごとに `novel_supported_rate` を再計算
3. **再検定**: SC-1r の Fisher's exact test を再実行し p 値を記録

---

## 5. 記録する指標

各 threshold での結果テーブル:

| Threshold | C2 known_fact | C2 novel_sup_rate | C_rand_v2 novel_sup_rate | SC-1r p値 | SC-1r 結果 |
|-----------|--------------|-------------------|--------------------------|-----------|-----------|
| 20 (現行) | 0.740 | 0.130 | 0.219 | 0.9088 | FAIL |
| 50 | TBD | TBD | TBD | TBD | TBD |
| 100 | TBD | TBD | TBD | TBD | TBD |
| 200 | TBD | TBD | TBD | TBD | TBD |

---

## 6. 解釈ルール（事前定義）

以下のルールを事前に定義し、結果を見た後に解釈を変えない:

### 主解析への影響なし（原則）

**この sensitivity analysis の結果がどうであれ、主解析 (SC-1r FAIL) の結論は変更しない。**

run_017 の事前登録された threshold は 20 である。
後付けで threshold を変えて「PASS になった」ことを主解析の結論とすることは禁止する。

### threshold robustness の評価基準

| 結果パターン | 解釈 |
|-------------|------|
| 全 threshold で SC-1r FAIL | ラベリングに関わらず C2 は novel_supported_rate で劣る。robustness 高い |
| 高 threshold (≥100) で SC-1r PASS | threshold 感度あり。ラベリング定義の再検討が必要（次実験の設計課題） |
| 低 threshold (≤50) でも PASS に近い | 現行 threshold が特に厳しい可能性あり。探索的発見として記録 |

---

## 7. 報告方針

- 結果は正直に全て報告する
- threshold を上げると FAIL が PASS に変わる場合でも、その解釈を「救済」としない
- 「threshold 依存性の発見」として記録し、investigability 仮説 v2 の pre-registration 時に
  threshold 定義を改めて事前登録する

---

## 8. 実装方針

```python
# validate_hypotheses_v2.py の KNOWN_THRESHOLD 定数を変更して再実行
# ただし PubMed API 再クエリは不要（既存の hit count を再利用）

THRESHOLDS_TO_TEST = [20, 50, 100, 200]

for threshold in THRESHOLDS_TO_TEST:
    # labeling_results_layer2.json を読み込み
    # hit_count >= threshold → known_fact に再分類
    # novel_supported_rate を再計算
    # Fisher's exact test を実行
    # 結果を sensitivity_results_{threshold}.json に保存
```

実装は `src/scientific_hypothesis/sensitivity_analysis.py` として独立させる。
既存の `validate_hypotheses_v2.py` は変更しない。

---

## 9. タイムライン

この sensitivity analysis は **investigability 仮説 v2 の pre-registration 前** に実施することが望ましい。
threshold の robustness 確認が次実験の設計（labeling 定義）に影響するため。

ただし blocking ではなく、pre-registration を先行させることも許容する。
