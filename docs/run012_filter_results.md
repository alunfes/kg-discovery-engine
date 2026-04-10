# Run 012 Filter Results — Review-Driven Drift Suppression

**Date**: 2026-04-10  
**Filter**: contains, is_product_of, is_reverse_of, is_isomer_of + guards  
**Baseline**: Run 009 Condition C P4 (939候補, 20 deep cross-domain)  
**Reference labels**: Run 011 qualitative review (promising=3, weak_spec=12, drift_heavy=5)

## 結果サマリー

| 指標 | Before (Run 009/011) | After (Run 012) | 変化 |
|------|---------------------|-----------------|------|
| 候補総数 | 939 | 446 | ▼493 (52.5%) |
| Deep cross-domain (≥3-hop) | 20 | 3 | ▼17 |
| drift_heavy率 | 25.0% | 0.0% | **▼25pp** |
| promising率 | 15.0% | 100.0% | **▲85pp** |
| promising損失 | — | 0 | なし |
| drift_heavy除去 | — | 5/5 (100%) | 全件除去 |
| 除去効率 | — | 5/17 = 29.4% | |

## 成功条件

| 条件 | 目標 | 結果 | 判定 |
|------|------|------|------|
| drift_heavy率 | 25% → <15% | 0.0% | **PASS** |
| promising率 | 15% → >25% | 100.0% | **PASS** |
| deep CD候補が大幅崩れない | ≥3件 | 3件 | **PASS** |

## Deep Cross-Domain候補の残存状況

Run 012後に残った3件（全てpromising）:

| ID | パス | Hop数 | Strong-Ratio |
|----|------|-------|-------------|
| H0xxx | g_VHL→encodes→VHL→inhibits→HIF1A→activates→LDHA→requires_cofactor→NADH→undergoes→r_Oxidation | 5 | 0.60 |
| H0xxx | VHL→inhibits→HIF1A→activates→LDHA→requires_cofactor→NADH→undergoes→r_Oxidation | 4 | 0.50 |
| H0xxx | g_HIF1A→encodes→HIF1A→activates→LDHA→requires_cofactor→NADH→undergoes→r_Oxidation | 4 | 0.50 |

全3件がVHL/HIF1A/LDHAカスケード（Warburg効果制御仮説）。
科学的に検証可能な機構的仮説を形成している。

## 除去された候補の分析

### Promising損失: 0件
全promising候補（VHL/HIF1A/LDHA カスケード）がfilterを通過した。

### Weak_Speculative除去: 12件全件
- is_reverse_of含む6件: r_Oxidation→is_reverse_of→r_Reduction パターン（化学的事実）
- contains含む4件: amino-acid→contains→functional-group パターン（構造的事実）
- strong_ratio<0.40で2件: 機構的anchorsが不十分

### Drift_Heavy除去: 5件全件
- is_product_of/contains含む2件: m_AMP→ATP化学構造チェーン
- is_precursor_of連続+contains: 3PG→Ser→Gly→official-group チェーン
- is_reverse_of含む1件: r_Oxidation→is_reverse_of→r_Reductionチェーン

## Filter効果の解釈

**Filter 1 (`filter_relations`) が支配的**:
- drift_heavy 5件中5件、weak_speculative 12件中10件に作用
- 除去候補の多くが複数filterにかかる（redundant coverage）

**is_reverse_of の作用範囲**:
- weak_speculative 6件 (H0275, H0300, H0344, H0401, H0524, H0644) を除去
- これらは r_Oxidation → is_reverse_of → r_Reduction という化学的事実チェーン
- 機構的仮説ではなく化学的同一性の展開であり、除去は適切

**min_strong_ratio=0.40 の作用**:
- H0268, H0633 (weak_speculative) を追加で除去: strong_ratio=0.33
- これらはLDHA/NADH/r_Oxidationチェーンでis_reverse_ofなし
- requires_cofactor/undergoesが強relation非含有のため基準未達

## Tradeoff文書

| Tradeoff | 内容 |
|---------|------|
| Deep CD候補数 20→3 | 17件削減。しかし削減されたのは全て weak_speculative/drift_heavy であり、promising損失はゼロ |
| 総候補 939→446 | 52.5%削減。top-20は変化なし（2-hopの強chainが依然支配的）|
| is_reverse_of除去 | weak_speculative 6件を除去したが、これらは機構的仮説でなく化学的対称性の記述 |

## Top-20への影響

Top-20の深さ分布は変化なし（2-hop候補が占める）。
Mean score: 0.78 → 0.78（変化なし）。

**Observation**: Deep cross-domain候補の品質は向上したが、top-20への進出には
追加施策が必要（Run 013検討事項）。

## 次ステップ推薦

1. **Run 013 — filter後の公正テスト**: H1''/H3''をfilter後のkGで再検証
2. **is_reverse_of の再考**: 除去範囲が広い。r_Reductionへの展開が「仮説」とみなせるか
   別途評価し、過剰除去であれば除外候補から外す
3. **min_strong_ratio チューニング**: 0.30 vs 0.40 vs 0.50 でsensitivity analysis
4. **deep候補のtop-k進出**: plausibility/traceabilityスコアの調整またはdepth-bonus追加を検討
