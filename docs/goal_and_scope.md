# プロジェクトゴールとスコープ

## ゴール

Knowledge Graph (KG) オペレータを組み合わせたパイプラインが、既存の単純なアプローチより**有用な科学的仮説を自動生成できるか**を実験的に検証する。

## 検証フレームワーク

### なぜKGオペレータか

科学的発見は多くの場合、異なる知識ドメインの「橋渡し」から生まれる。例：

- ペニシリンの発見（カビの観察 × 細菌学の知識）
- ナイロンの発明（絹のタンパク質構造 × 高分子化学）

KGオペレータは、この「橋渡し」プロセスを形式化・自動化する試み。

### 検証対象

| 問い | 対応仮説 |
|------|----------|
| multi-opはsingle-opより良いか？ | H1 |
| 入力KG品質 vs 評価レイヤー品質、どちらが重要か？ | H2 |
| cross-domainはsame-domainより新規性が高いか？ | H3 |
| provenance情報はランキング品質を向上させるか？ | H4 |

## スコープ

### In Scope

- 合成トイデータセット（biology, chemistry, software, networking）
- 7種類のオペレータ（align, union, difference, compose, analogy-transfer, evaluate, belief-update）
- 3実験条件（C1: single-op、C2: multi-op、C3: direct baseline）
- 5次元評価ルーブリック（plausibility, novelty, testability, traceability, evidence support）
- Python標準ライブラリのみの実装

### Out of Scope（本フェーズ）

- 実世界のKGデータ（WikiData, PubMed等）の使用
- LLMとの統合
- 分散処理・大規模スケール
- UIダッシュボード

### 成功基準

| 指標 | 目標値 |
|------|--------|
| C2のplausibilityスコア | C1より≥10%高い |
| C2のnoveltyスコア | C1より≥15%高い |
| cross-domainのnovelty | same-domainより≥20%高い |
| provenance-aware評価の順位相関 | naiveより≥0.1改善 |

## タイムライン

| フェーズ | 内容 | 状態 |
|----------|------|------|
| Phase 0 | 基盤実装（KGモデル・オペレータ・評価） | 完了 |
| Phase 1 | Run 001：トイデータで全条件比較 | 進行中 |
| Phase 2 | 仮説H1-H4の統計的検証 | 未着手 |
| Phase 3 | 実世界データへの拡張検討 | 未着手 |
