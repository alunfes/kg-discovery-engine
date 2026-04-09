# KG Discovery Engine

**KG発見エンジン検証プロジェクト**

Knowledge Graph (KG) オペレータパイプラインを用いて、科学的仮説を自動生成・評価するシステムの実験的検証。

## 概要

本プロジェクトは、複数のKGオペレータを組み合わせたパイプラインが、単一オペレータ手法よりも有用な仮説を生成できるかを検証する。

## 仮説

| ID | 仮説 |
|----|------|
| H1 | multi-operator KG pipelineはsingle-operator methodsより有用な仮説を生成する |
| H2 | 入力KGの完璧化よりも下流の評価レイヤーの強化が重要 |
| H3 | cross-domain KG操作はsame-domain操作より新規性の高い仮説を生成する |
| H4 | provenance-aware evaluationは仮説ランキングの品質を向上させる |

## クイックスタート

```bash
# 依存なし（標準ライブラリのみ）
python -m pytest tests/ -v

# 実験実行
python src/pipeline/run_experiment.py

# 全条件を比較
python src/pipeline/compare_conditions.py
```

## ディレクトリ構造

```
docs/           # リサーチドキュメント（仮説・オペレータ定義・評価ルーブリック）
runs/           # 実験アーティファクト（実行ごとのディレクトリ）
src/
  kg/           # KGデータモデル
  pipeline/     # パイプライン実装
  eval/         # 評価レイヤー
tests/          # テスト
```

## 技術スタック

- Python 3.11+（標準ライブラリのみ）
- 決定論的動作（乱数シード固定）
- 外部依存なし（pytest のみ）
