# 評価サマリー — Run 001

**実行日**: 2026-04-10
**実験**: biology + chemistry トイデータ、全条件比較

---

## 数値結果

| 条件 | 仮説数 | 平均Total | 平均Plausibility | 平均Novelty |
|------|--------|-----------|-----------------|-------------|
| C1 (single-op compose) | 8 | 0.7050 | 0.7000 | 0.8000 |
| C2 (multi-op pipeline) | 23 | 0.7050 | 0.7000 | 0.8000 |
| C3 (direct baseline) | 0 | — | — | — |

---

## 仮説検証結果

### H1: Multi-operator Pipeline優位性

| 指標 | 結果 |
|------|------|
| C1 mean total | 0.7050 |
| C2 mean total | 0.7050 |
| 閾値（C1 × 1.10） | 0.7755 |
| **判定** | **FAIL** |

**所見**: C2はC1より多くの仮説を生成（8件 vs 23件）したが、スコア分布は同一だった。
現行のスコアリングヒューリスティックが2ホップパスに一律スコアを与えるため、
C1とC2の質的差異が数値に現れなかった。

### H3: Cross-domain新規性（予備）

| 指標 | 結果 |
|------|------|
| Cross-domain (bio+chem) novelty | 0.8000 |
| Same-domain (bio+bio) novelty | 0.8000 |
| **判定** | **FAIL** |

**所見**: noveltyスコアの計算が「KGに直接エッジが存在しないか」のみに依存しており、
ドメイン境界を越えた関係の novelty ボーナスが機能していない。

---

## 主要な発見

### 成功点

1. **パイプライン自体は動作した**: align → union → compose → difference の連鎖が正常に機能
2. **C2はより多くの仮説を生成**: 8件 → 23件（cross-domainの探索空間拡大が機能）
3. **全テスト28件パス**: 実装の正確性は担保されている

### 問題点

1. **スコアリングが単調すぎる**: 全2ホップパスに同一スコアが割り当てられる
   - plausibility: 2ホップ固定 0.7
   - novelty: 直接エッジなし固定 0.8
   → 仮説間の質的差異がスコアに反映されない

2. **アライメントが機能しなかった**: "EnzymeX" ↔ "CatalystM" の概念的対応が検出できず
   - 文字列Jaccardでは意味的類似度を捉えられない
   - cross-domain のメリット（analogical reasoning）が活用されていない

3. **noveltyスコアのcross-domainボーナスが無効**: `_score_novelty`でのドメイン比較ロジックが
   merged KG上では機能しない（merged KGはnameが"union_biology_chemistry"で、
   評価時のkg.get_node()がnodeのdomainを正しく返しているが、
   merged KGのbio系ノードのdomainは"biology"、chem系は"chemistry"で正しい。
   問題は merged KG上での compose が bio-chem cross を発見できていないこと）

---

## スコアリングの詳細

トップ5仮説（C1/C2ともに同一スコア0.7050）:

1. ProteinA → [inhibits → EnzymeX → catalyzes →] Reaction1
2. ProteinA → [binds_to → CellMembrane → contains →] EnzymeY
3. ProteinB → [activates → EnzymeX → catalyzes →] Reaction1
4. EnzymeX → [catalyzes → Reaction1 → produces →] ProteinB
5. Reaction1 → [produces → ProteinB → activates →] EnzymeX
