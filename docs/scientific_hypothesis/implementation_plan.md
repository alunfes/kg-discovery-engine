# Phase 6: Implementation Plan

## 設計方針

- 評価設計（Phase 0-5）が先、実装は後
- MVP を最初に完成させ、Full Scale は MVP の結果を見てから決定
- 既存 `src/pipeline/operators.py`, `src/eval/scorer.py` を最大限に再利用
- 新しいモジュールは自動化可能な部分のみ実装する（手動ラベリングは実装不要）

---

## 1. ディレクトリ構成

### 新規追加（MVP）

```
src/
└── scientific_hypothesis/
    ├── __init__.py
    ├── kg_builder.py          # biology/chemistry KG 構築（≥200 ノード）
    ├── hypothesis_generator.py # C2/C1/C_rand 各 method の仮説生成
    ├── baseline.py            # C_rand 生成アルゴリズム
    └── evaluator.py           # キーワード検索・候補文献絞り込み・結果集計

tests/
└── scientific_hypothesis/
    ├── test_kg_builder.py
    ├── test_hypothesis_generator.py
    ├── test_baseline.py
    └── test_evaluator.py

scripts/
├── run_scientific_hypothesis_generation.py  # 仮説生成（freeze 後に実行）
├── run_scientific_hypothesis_evaluation.py  # ラベリング支援・集計
├── verify_time_split.py                      # time split 検証
├── verify_baseline_parity.py               # method 間複雑度の確認
└── verify_determinism.py                   # 決定論的動作確認

data/
├── corpus/
│   ├── past/                    # KG 構築用文献（〜2023-12-31）
│   │   └── .gitkeep
│   └── validation/              # ラベリング用文献（2024-01-01〜）
│       └── .gitkeep
└── kg/
    ├── biology_kg_v1.json       # biology KG（freeze 後不変）
    └── chemistry_kg_v1.json     # chemistry KG（freeze 後不変）
```

---

## 2. モジュール仕様

### `src/scientific_hypothesis/kg_builder.py`

```python
"""biology × chemistry KG の構築（MVP: ≥200 ノード手動キュレーション版）。"""

def build_biology_kg(source_path: str) -> KnowledgeGraph:
    """past corpus JSONLから biology KG を構築する。
    
    source_path: data/corpus/past/biology_entities.jsonl
    Returns: KnowledgeGraph with domain='biology'
    """

def build_chemistry_kg(source_path: str) -> KnowledgeGraph:
    """past corpus JSONLから chemistry KG を構築する。"""

def validate_kg_size(kg: KnowledgeGraph, min_nodes: int, min_edges: int) -> bool:
    """KG がMVP要件（≥200 ノード, ≥400 エッジ）を満たすか確認する。"""
```

### `src/scientific_hypothesis/hypothesis_generator.py`

```python
"""各 method（C2/C1_compose/C1_diff）による仮説生成。"""

def generate_c2(
    bio_kg: KnowledgeGraph,
    chem_kg: KnowledgeGraph,
    max_hypotheses: int = 50,
    seed: int = 42,
) -> list[HypothesisCandidate]:
    """multi-op pipeline: align→union→compose→difference。"""

def generate_c1_compose(
    bio_kg: KnowledgeGraph,
    max_hypotheses: int = 50,
    seed: int = 42,
) -> list[HypothesisCandidate]:
    """single-op: compose only（biology KG のみ）。"""

def generate_c1_diff(
    bio_kg: KnowledgeGraph,
    chem_kg: KnowledgeGraph,
    max_hypotheses: int = 50,
    seed: int = 42,
) -> list[HypothesisCandidate]:
    """single-op: align→difference。"""
```

### `src/scientific_hypothesis/baseline.py`

```python
"""C_rand: ランダムパス baseline 生成。"""

def generate_random_baseline(
    merged_kg: KnowledgeGraph,
    reference_candidates: list[HypothesisCandidate],
    seed: int = 42,
) -> list[HypothesisCandidate]:
    """chain_length 分布と relation 構成比を reference_candidates と揃えたランダム仮説を生成する。"""

def verify_parity(
    reference: list[HypothesisCandidate],
    random_baseline: list[HypothesisCandidate],
) -> dict[str, float]:
    """chain_length 分布と relation 構成比の一致度（KS統計量、χ²）を返す。"""
```

### `src/scientific_hypothesis/evaluator.py`

```python
"""ラベリング支援：キーワード検索・候補文献絞り込み・結果集計。"""

def build_search_query(candidate: HypothesisCandidate) -> str:
    """仮説から PubMed 検索クエリ文字列を生成する。"""

def search_corpus(
    query: str,
    corpus_path: str,
    max_results: int = 20,
) -> list[dict]:
    """validation corpus JSONL をキーワード検索し候補文献を返す（外部API呼び出しなし）。"""

def compute_metrics(labels: list[dict]) -> dict[str, float]:
    """ラベルファイルから precision_positive, investigability, high_novelty_rate を計算する。"""

def run_fisher_test(
    group_a: list[str],
    group_b: list[str],
    positive_labels: set[str],
) -> dict[str, float]:
    """Fisher's exact test を stdlib math のみで実装し p 値と odds ratio を返す。"""
```

---

## 3. スクリプト仕様

### `scripts/run_scientific_hypothesis_generation.py`

```
実行前提: configs/scientific_hypothesis_registry.json の frozen: true
入力:
  --bio_kg    data/kg/biology_kg_v1.json
  --chem_kg   data/kg/chemistry_kg_v1.json
  --output    runs/run_sci_{NNN}_{YYYYMMDD}/
  --seed      42
出力:
  output_candidates.json  # 全 method の仮説（200件）
  run_config.json         # 実験設定スナップショット
```

### `scripts/run_scientific_hypothesis_evaluation.py`

```
入力:
  --candidates  runs/run_sci_NNN/output_candidates.json
  --corpus      data/corpus/validation/pubmed_2024_2025.jsonl
  --output      runs/run_sci_NNN/labeling_support/
出力:
  candidate_queries.json   # 各仮説の検索クエリ
  candidate_hits.json      # 各仮説の候補文献リスト
  labeling_template.json   # primary labeler が入力する空のラベルファイル
```

---

## 4. 自動化範囲 vs 手動レビュー範囲

| タスク | 自動化 | 手動 |
|--------|--------|------|
| KG 構築（toy_data.py 拡張） | ○（コードで定義） | △（エンティティ・関係の内容は人手キュレーション） |
| C2/C1/C_rand 仮説生成 | ○ | - |
| time split 検証 | ○ | - |
| baseline parity 確認 | ○ | - |
| キーワード検索・候補文献絞り込み | ○ | - |
| ラベリング（5分類の付与） | ✗ | ○（labeling_protocol.md 参照） |
| Double review / adjudication | ✗ | ○ |
| 統計検定（Fisher's test）の計算 | ○ | - |
| 結果解釈・review_memo.md 作成 | ✗ | ○ |

---

## 5. MVP 定義

**MVP の範囲**: 「1 テーマ・小規模 corpus・3 methods 比較・少数仮説厳密ラベリング・再現可能 time split」

| 要素 | MVP 仕様 |
|------|---------|
| テーマ | biology × chemistry, drug repurposing subtheme |
| KG サイズ | ≥200 ノード（手動キュレーション） |
| 仮説生成 methods | C2, C1_compose, C_rand（計3 methods, 各20件 = 60件） |
| ラベリング対象 | 60件全件 |
| double review | 12件（20%） |
| corpus | past: toy KG 手動拡張, validation: 手動収集 JSON 30-50件 |
| time split | past ≤ 2023-12-31, validation 2024-2025 |
| 決定論性 | `verify_determinism.py` でパス |

**MVP の成功条件**: 60件ラベリング完了、Fisher's test 実行、review_memo.md 作成。統計的有意差は必須でない（MVP は手順の検証）。

**MVP から Full Scale への拡張条件**:
- MVP で investigability ≥ 0.20 を確認できた場合
- 50件/method への拡張が工数的に実現可能と判断した場合

---

## 6. テスト方針

### 単体テスト（`tests/scientific_hypothesis/`）

| テスト対象 | テスト内容 |
|-----------|----------|
| `test_kg_builder.py` | build_biology_kg がノード数 ≥200 を返すか、domain が正しく設定されるか |
| `test_hypothesis_generator.py` | 各 method が max_hypotheses 以下を返すか、seed 固定で決定論的か |
| `test_baseline.py` | verify_parity が parity 違反を検出するか（chain_length 分布を意図的にずらしたケース） |
| `test_evaluator.py` | build_search_query が正しいクエリを生成するか、compute_metrics が正しく計算するか |

### 統合テスト

`tests/scientific_hypothesis/test_full_pipeline.py`:
- KG 構築 → 仮説生成 → キーワード検索 → metrics 計算 の end-to-end
- 入力: toy KG（biology: 10 ノード, chemistry: 10 ノード）
- 出力: 仮説が1件以上生成される、metrics が float で返る

### 決定論性テスト（既存 `verify_determinism.py` を拡張）

同一 seed・同一 KG から2回実行した output_candidates.json が bit-identical であることを確認。

---

## 7. 実装順序

1. `src/scientific_hypothesis/kg_builder.py` + テスト
2. `src/scientific_hypothesis/hypothesis_generator.py` + テスト（既存 operators.py の wrapper）
3. `src/scientific_hypothesis/baseline.py` + テスト
4. `scripts/run_scientific_hypothesis_generation.py`（integrate 1-3）
5. `scripts/verify_determinism.py`（拡張）, `scripts/verify_time_split.py`
6. `src/scientific_hypothesis/evaluator.py` + テスト
7. `scripts/run_scientific_hypothesis_evaluation.py`
8. MVP 実行 → ラベリング → `scripts/verify_baseline_parity.py`

---

## 8. 依存関係

**新規外部依存**: なし（Python 標準ライブラリのみ）

| 機能 | 使用モジュール |
|------|--------------|
| KG モデル | `src.kg.models` (既存) |
| KG オペレータ | `src.pipeline.operators` (既存) |
| Novelty スコア | `src.eval.scorer` (既存) |
| 統計検定（Fisher's test） | `math` + `fractions` (標準ライブラリで実装) |
| JSON 読み書き | `json` |
| ランダム | `random` (seed 固定) |
| 文字列マッチ | `re` |
