# KG 最適化計画

## 現状
- 現行 KG: 200ノード
- Q1 failure 率: 38.5%（うち 50% が sparse_neighborhood 型）
- sparse_neighborhood 失敗はKGデータ品質問題であり、selection policy では解決不可

## 最適化ステップ

1. 現行 KG (200ノード) の sparse region map を作成
2. sparse region に対するデータ補完戦略
   - PubMed abstract からの relation extraction
   - DrugBank/UniProt の追加エンティティ
   - 手動キュレーション
3. 補完後の KG で run_022 相当を再実行し、Q1 failure 率の変化を測定
4. 成功基準: Q1 failure 率を 38.5% → 20% 以下に削減

## 責任分離

| 問題 | 責任 | 対処 |
|------|------|------|
| density mismatch | Selection policy | density filter/weighting |
| sparse neighborhood | KG structure | P3 densification |
| missing bridges | KG structure | P3 augmentation |
| diversity-driven low-quality | Selection policy | diversity guardrails |
