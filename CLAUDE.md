# KG Discovery Engine — Claude Instructions

## プロジェクト概要

KGオペレータパイプラインによる科学的仮説自動生成・評価の実験的検証プロジェクト。

## 作業ルール

### コード
- Python標準ライブラリのみ（外部依存禁止）
- 決定論的動作必須（random.seed固定）
- 関数は40行以下
- 全パブリック関数にdocstring
- 型ヒント必須

### 実験
- 実験ごとに `runs/run_NNN_YYYYMMDD/` ディレクトリを作成
- `run_config.json` に実験設定を記録
- 結果は `output_candidates.json` に保存
- 実験後は `review_memo.md` を必ず作成

### コミットメッセージ

```
feat(kg): KGNodeクラス追加
test(pipeline): alignオペレータのテスト追加
docs(hypotheses): H3仮説定義を詳細化
```

### 実験条件

| Condition | 説明 |
|-----------|------|
| C1 | single-op baseline（compose-only） |
| C2 | multi-op pipeline（align→union→compose→difference→evaluate） |
| C3 | direct baseline placeholder |

## 重要ファイル

- `docs/hypotheses.md` — 検証すべき仮説（H1-H4）
- `docs/operators.md` — オペレータ仕様
- `docs/evaluation_rubric.md` — スコアリング基準
- `runs/` — 実験アーティファクト

## 禁止事項

- 外部APIコール（決定論的動作を破壊）
- 乱数シード未設定での実行
- 実験後のrun_config.json未作成
