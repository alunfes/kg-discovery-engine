# P3: KG Structure Optimization

## P3-A (Priority): KG Densification / Augmentation

目的: sparse neighborhood 問題の解決、low-density failure の削減

初期タスク:
1. Q1 failure 例の詳細抽出（run_024 の failure_map から）
2. sparse 領域の特定（どのノード/エッジ周辺が sparse か）
3. bridge 候補生成（既存 align オペレータの拡張）
4. 外部データ統合の検討（PubMed abstract からの自動エンティティ抽出）

## P3-B (Research): Density Decomposition / Topology Analysis

目的: density を構造的に分解し、path / bridge / local connectivity を定量化

- density は現在 PubMed ヒット数で測っているが、KG 内の構造的 connectivity とは別
- KG topology metrics (degree, betweenness, clustering) と investigability の関係を分析
- 「density が高いから investigable」なのか「connectivity が高いから investigable」なのかを分離
