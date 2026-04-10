# Evaluation Summary — Run 002

**日付**: 2026-04-10
**前回**: Run 001 (2026-04-10)

---

## 定量比較: Run 001 vs Run 002

| 指標 | Run 001 C1 | Run 002 C1 | 変化 | Run 001 C2 | Run 002 C2 | 変化 |
|------|-----------|-----------|------|-----------|-----------|------|
| 仮説数 | 8 | 8 | → | 23 | 16 | -7 |
| mean_total | 0.7050 | 0.7237 | **+2.7%** | 0.7050 | 0.7475 | **+6.0%** |
| mean_plausibility | 0.7000 | 0.7625 | **+8.9%** | 0.7000 | 0.7687 | **+9.8%** |
| mean_novelty | 0.8000 | 0.8000 | → | 0.8000 | 0.8875 | **+10.9%** |
| mean_testability | 0.6000 | 0.6000 | → | 0.6000 | 0.6000 | → |
| mean_traceability | 0.7000 | 0.7000 | → | 0.7000 | 0.7000 | → |

※ C2仮説数が23→16に減ったのは、同義語アライメントでchem側ノードが統合され、重複パスが消えたため。これは正常な挙動。

---

## 仮説検証状態

### H1: multi-op (C2) は single-op (C1) より 10% 以上スコアが高い

| Run | C1 mean | C2 mean | 差異 | 判定 |
|-----|---------|---------|------|------|
| Run 001 | 0.7050 | 0.7050 | 0.0% | **FAIL** |
| Run 002 | 0.7237 | 0.7475 | **+3.3%** | **FAIL** |

**考察**: Run 001から改善されたが、閾値10%には届いていない。
C2の16件中7件がcross-domain仮説(total=0.785)、残り9件がsame-domain仮説(total≈0.72)。
cross-domain比率が低いことが原因。閾値を達成するには仮説の過半数がcross-domainである必要がある。

**進展**: Run 001では「差がゼロ」だったが、今回は明確な差が生まれた。原因の特定と修正は成功している。

---

### H2: 詳細評価 vs 簡易評価 (未検証)

まだ設計・実装していない。Run 003以降の課題。

---

### H3: cross-domain仮説はsame-domain仮説より novelty が高い

| Run | Cross-domain | Same-domain | 比率 | 判定 (閾値1.20) |
|-----|-------------|------------|------|----------------|
| Run 001 | 0.8000 | 0.8000 | 1.000 | **FAIL** |
| Run 002 | 0.8875 | 0.8000 | **1.109** | **FAIL** |

**考察**: 明確な改善(1.000→1.109)。cross-domain仮説はnovelyスコア1.0(max)を取得している。
しかし同条件内でsame-domain仮説が混在し、平均値では1.20閾値に届いていない。

**個別仮説レベルでは成立**: C2の全cross-domain仮説(novelty=1.0) > C1のsame-domain仮説(novelty=0.8) ✓

**提案**: H3の検証方法を変更 — 「条件平均」ではなく「仮説単位でのcross vs same比較」で評価すべき。

---

### H4: provenance-aware評価はスコアを向上させる (未検証)

provenance_aware=Trueの評価を実施していない。Run 003以降の課題。

---

## Cross-domain仮説の例 (Run 002 Top 5)

| 仮説ID | subject | object | total |
|--------|---------|--------|-------|
| H0002 | bio:protein_A (biology) | chemistry::chem:reaction_alpha (chemistry) | **0.785** |
| H0005 | bio:protein_B (biology) | chemistry::chem:reaction_alpha (chemistry) | **0.785** |
| H0007 | bio:enzyme_Y (biology) | chemistry::chem:polymer_Z (chemistry) | **0.785** |
| H0014 | chemistry::chem:reaction_alpha (chemistry) | bio:enzyme_X (biology) | **0.785** |
| H0015 | chemistry::chem:solvent_S (chemistry) | bio:reaction_2 (biology) | **0.785** |

Run 001ではcross-domain仮説が**ゼロ**だったのに対し、Run 002では**7件**生成された。

---

## アライメント改善の効果

| 項目 | Run 001 | Run 002 |
|------|---------|---------|
| アライメント数 | 0件 | 4件 |
| cross-domain仮説数 | 0件 | 7件 |
| cross-domain仮説スコア | N/A | 0.785 (same-domain 0.72 より +8.7%) |

---

## 解析: なぜH1/H3が閾値に届かないか

### H1の分析

C2 mean = (7件 × 0.785 + 9件 × 0.720) / 16 = 0.7475

H1 pass条件: C2_mean >= C1_mean × 1.10 = 0.7237 × 1.10 = 0.7961

必要なC2 mean = 0.7961 に対して現在 0.7475。
差を埋めるには、C2の仮説の大多数(12+件/16件)がcross-domain仮説である必要がある。

**根本**: toy dataの8ノード×8ノードの小規模KGでは、アライメントで生まれるcross-domainパスが限られる。

### H3の分析

H3 pass条件: cross-domain_novelty >= same-domain_novelty × 1.20 = 0.8 × 1.20 = 0.96

現在のC2 bio+chem novelty mean = 0.8875 < 0.96

**原因**: C2の16件中9件がsame-domain仮説(novelty=0.8)のため、平均が0.96に届かない。

**提言**: H3の検証方式を変更すべき — 仮説レベル比較に切り替えることで、本来の仮説の意図を正確に検証できる。

---

## 技術品質

- テスト数: 28件(Run 001) → **32件(Run 002)**  (+4件)
- テスト全パス: ✓
- 決定論的動作: ✓ (外部依存なし)
- コード変更: operators.py +50行, scorer.py +15行
