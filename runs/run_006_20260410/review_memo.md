# Run 006 Review Memo

**Date**: 2026-04-10
**Purpose**: H3再検証（tautological scoring除去）+ evaluator品質向上（testabilityヒューリスティック）

---

## 変更点

| 変更 | 内容 | 目的 |
|------|------|------|
| `cross_domain_novelty_bonus=False` | noveltyの+0.2 cross-domainボーナスを除去 | H3 PASS が設計依存か内在的かを検証 |
| `testability_heuristic=True` | 定数0.6を関係種別ヒューリスティックに置換 (範囲0.4-0.9) | testabilityの弁別力向上 |

---

## 結果

### H3: Cross-domain Novelty Superiority

| 指標 | 標準スコアラー | ボーナスなし (Run 006) |
|------|--------------|----------------------|
| cross-domain novelty | 1.000 | **0.800** |
| same-domain novelty | 0.800 | **0.800** |
| ratio | 1.25 | **1.00** |
| H3 PASS? | ✓ YES | **✗ NO** |

**H3 判定: ボーナス除去後FAIL — cross-domain novelty優位性は設計依存**

### Testability Distribution

| 指標 | 標準スコアラー (constant 0.6) | Run 006 (heuristic) |
|------|------------------------------|---------------------|
| mean | 0.600 | **0.885** |
| std | 0.000 | **0.036** |

→ ヒューリスティックにより testability が正常に変動するようになった。

### Score Discrimination

| 指標 | 標準スコアラー | Run 006 |
|------|--------------|---------|
| total_std | 0.0286 | 0.0186 |
| discrimination_improved | — | **NO (std低下)** |

---

## 解釈

### H3について
`H3 PASS` はH1-H4の中で唯一の「実装の内部整合性テスト」であった。  
cross-domainスコアが高いのは+0.2ボーナスを持つから、という循環論法。  
ボーナス除去後、cross-domain(0.8) == same-domain(0.8): 区別なし。

**正直な再フレーミング**: H3は「cross-domain仮説が生成できること」を確認したが、  
「cross-domain仮説が本質的により新規」という主張はサポートされていない。

### Testabilityヒューリスティックについて
良い点：
- testability が 0.036 の std を持ち、候補間で変動するようになった
- bio/chemのパスは measurable関係（inhibits/activates/catalyzes等）が支配的
- → 多くの候補が 0.9 の高testabilityスコアを得る（concrete namespace + measurable）

悪い点（意外な発見）：
- testability平均が 0.6 → 0.885 に上昇したことでtotal_stdが低下 (0.029 → 0.019)
- 全候補が同じく高testabilityを得るため、弁別力はむしろ下がった
- toy dataのrelation種別が偏りすぎ（ほぼ全て measurable）

**教訓**: testabilityヒューリスティックの設計自体は正しいが、  
toy dataがほぼ全てmeasurable relationsで構成されているため弁別が機能しない。  
実データ（abstract relationsが混在）では効果的になる可能性がある。

---

## Phase 2 最終カリブレーション後のH1-H4状態

| 仮説 | 最終状態 | 信頼度 | 根本的な問題 |
|------|---------|--------|------------|
| H1 | **FAIL** (5Runs) | Low | toy data飽和、閾値設定無根拠 |
| H2 | 部分支持 | Medium | survivorship bias |
| H3 | **再フレーム: 設計整合性PASS、内在的優位性FAIL** | High | 設計が結論を決めていた |
| H4 | 条件付き支持 | Medium | engineered KGのみ |

---

## 次のアクション

→ `docs/phase3_readiness_memo.md` 作成: Phase 3 Go/No-Go判断
