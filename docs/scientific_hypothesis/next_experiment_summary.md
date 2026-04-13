# Phase 7: Next Experiment Summary（1ページサマリー）

---

## 検証テーマ

**Biology × Chemistry KG による Drug Repurposing 仮説の将来文献支持率検証**

---

## 検証仮説

| ID | 仮説 | 検定 |
|----|------|------|
| H_main | KG multi-op (C2) の precision_positive > random baseline (C_rand), p < 0.05 | Fisher's exact test, 片側 |
| H_cov | C2 の investigability ≥ C_rand | 記述統計 + 95% CI |
| H_novel | C2 の high_novelty_uninvestigated_rate > C_rand | Fisher's exact test, 片側 |

---

## Baselines

| method ID | 説明 | 仮説数 |
|-----------|------|--------|
| C2 | align→union→compose→difference（multi-op） | 20（MVP）→ 50（Full Scale） |
| C1_compose | compose only（single-op） | 20 → 50 |
| C_rand | ランダムパス（chain length・relation 構成比を C2 と揃える） | 20 → 50 |

---

## 必要データ

| データ | 用途 | 取得方法 |
|--------|------|---------|
| biology KG（~120 ノード） | 仮説生成 (past) | `src/scientific_hypothesis/kg_builder.py`（手動キュレーション） |
| chemistry KG（~80 ノード） | 仮説生成 (past) | 同上（合計 ≥200 ノード） |
| PubMed validation corpus (2024-2025) | ラベリング | 手動 download または E-utilities 静的 dump |
| bioRxiv validation corpus (2024-2025) | ラベリング（補助） | 静的 JSON dump |

---

## Time Split

```
past corpus    : 〜 2023-12-31  （KG 構築・仮説生成）
validation     :   2024-01-01 〜 2025-12-31  （ラベリング・文献照合）
```

仮説生成スクリプトは past corpus のみ参照。validation corpus は仮説生成完了後に解禁。

---

## ラベリング方式

- 5分類: `supported / partially_supported / contradicted / investigated_but_inconclusive / not_investigated`
- 手順: 自動キーワード検索 → 候補文献絞り込み（最大20件/仮説）→ 人手ラベリング
- Double review: 全件の20%（seed=42 ランダムサンプル）
- Adjudication: conservative downgrade（不一致時は保守的ラベルを採用）
- `not_investigated` は失敗扱いしない

---

## 成功基準

| ID | 条件 | 必須 |
|----|------|------|
| SC-1 | precision_positive(C2) > precision_positive(C_rand), p < 0.05 | 必須 |
| SC-2 | investigability(C2) ≥ investigability(C_rand) | 副次的 |
| SC-3 | high_novelty_uninvestigated_rate(C2) > high_novelty_uninvestigated_rate(C_rand) | 副次的 |

SC-1 のみ達成 → 「部分的支持」、追実験推奨。SC-1 未達 → 「有効性なし」として記録、corpus 拡大または KG 拡張を検討。

---

## MVP の最初の1サイクル

### Step 1: KG 構築（2-3日）
- `src/scientific_hypothesis/kg_builder.py` を実装
- biology KG ≥200 ノード・chemistry KG ≥200 ノードを手動キュレーション
- `data/kg/biology_kg_v1.json`, `data/kg/chemistry_kg_v1.json` に保存
- `verify_determinism.py` でパスを確認

### Step 2: Pre-registration Freeze（1日）
- `configs/scientific_hypothesis_registry.json` の `kg_generation_commit` を記入
- `frozen: true` に設定
- `docs/scientific_hypothesis/pre_registration.md` の Freeze チェックリストを確認

### Step 3: 仮説生成（1日）
- `scripts/run_scientific_hypothesis_generation.py` を実行（seed=42, 各 method 20件）
- `runs/run_sci_001_20260414/output_candidates.json` に保存
- `verify_baseline_parity.py` でパリティ確認
- `configs/scientific_hypothesis_registry.json` の `hypothesis_generation_commit` を記入

### Step 4: Validation Corpus 取得（1日）
- PubMed E-utilities で 2024-2025 年の bio/chem 論文を静的 JSON に保存
- `data/corpus/validation/pubmed_2024_2025.jsonl` に配置

### Step 5: ラベリング（2日）
- `scripts/run_scientific_hypothesis_evaluation.py` で候補文献リストを生成
- `labeling_protocol.md` に従い60件をラベリング
- Double review（12件）+ adjudication を実施
- `runs/run_sci_001_20260414/labels.json` に保存

### Step 6: 分析・レポート（1日）
- `compute_metrics()` で precision_positive, investigability, high_novelty_rate を計算
- Fisher's test を実行
- `runs/run_sci_001_20260414/review_memo.md` を作成（成功基準への照合を含む）
- 次のアクション（Full Scale / corpus 拡大 / 仮説生成パラメータ調整）を決定

---

## 未確定事項（スタート前に解決が必要）

| 項目 | 期限 |
|------|------|
| KG ノード数の実現可能性（手動キュレーション ≥200 ノードが現実的か） | Step 1 開始時 |
| Validation corpus の密度（2024-2025 の関連論文が30件以上あるか） | Step 4 完了後 |
| Second labeler の確保（自己 2週間再ラベルで代替可か） | Step 5 開始前 |

---

*作成: 2026-04-13 / 次レビュー: Step 3 完了後（仮説生成 freeze 後）*
