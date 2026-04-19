# Competition Analysis: Sprint F Artifacts

**Date**: 2026-04-19
**Artifact**: `run_005_sprint_f/output_candidates.json` (60 cards)
**Purpose**: sign_error_rate 0.666 の構造的原因を仮説競合の観点から分析

## 主要発見

### 1. Family の極端な偏り

| family | cards | 比率 |
|--------|-------|------|
| cross_asset | 58 | 96.7% |
| microstructure | 2 | 3.3% |
| momentum | 0 | 0% |
| reversion | 0 | 0% |
| regime | 0 | 0% |

**60 cards 中 58 cards が "correlation break" という単一パターン。**
パイプラインが事実上 1 種類の仮説しか生成していない。

### 2. Claim の単調性

| パターン | 件数 |
|----------|------|
| correlation_break | 58 |
| funding_extreme | 2 |

全 claim が「ペア間の相関崩壊 → OI 蓄積 → ポジション解消」という同一メカニズムの変種。
**代替仮説（momentum, reversion, regime shift）が生成されていない。**

### 3. Evidence Strength の天井張り付き

| 指標 | min | max | mean |
|------|-----|-----|------|
| plausibility | 0.620 | **1.000** | 0.812 |
| novelty | 0.000 | 1.000 | 0.259 |
| actionability | **0.700** | **0.700** | 0.700 |

- plausibility が多くのカードで 1.000 (天井) — 識別力がない
- actionability が全カード 0.700 で定数 — 実行可能性が評価されていない
- novelty だけが分散を持つが、仮説の質ではなく「在庫との距離」を測っている

### 4. Competition Engine の結果

**全グループで confidence = 0.000。**

原因: 同一 family の仮説同士が競合しているため、contradiction edge が生成されない。
net_evidence も全て 1.000 近傍で横並び。competition engine が「全員同じくらい強い」と判定。

これは competition engine のバグではなく、**入力の多様性不足** を忠実に反映している。

## 根本原因の構造化

sign_error_rate = 0.666 の原因チェーン:

```
1. パイプラインが cross_asset 仮説に極端に偏っている
   ↓
2. 全仮説が同一メカニズム (correlation_break → OI_build → crowding) の変種
   ↓
3. 同一メカニズムが「当たる局面」と「外れる局面」があるが、
   regime による使い分けができていない
   ↓
4. 外れる局面でも代替仮説がないため、外れたまま確定する
   ↓
5. win rate 33.4% = 「correlation break は 3 回に 1 回しか当たらない」
   のではなく、「当たる局面を選んでいない」
```

## 推奨: 次の Phase 2 ステップ

### A. Arbitration Scope 定義

「同一 market state」の切り方を以下に定める:
- **Primary key**: (asset_pair, cycle_window)
- **Secondary grouping**: regime label at cycle start
- 同一 (asset_pair, cycle) 内の仮説を競合させる

### B. Family 多様性の確保 (パイプライン側)

competition engine をいくら改善しても、入力が単一 family なら裁定できない。
パイプラインが以下を生成するよう拡張が必要:
- **momentum**: 同じ market state に対する「トレンド継続」仮説
- **reversion**: 同じ market state に対する「平均回帰」仮説
- **regime_null**: 「何も起きない」null 仮説
これにより初めて「correlation_break vs momentum vs null」の競合が成立する。

### C. Regime-conditioned Scoring

- correlation_break は特定 regime でのみ有効
- regime_dependency を card 生成時に付与
- 現在の regime と一致しない仮説の evidence_strength を自動減衰

### D. Null Hypothesis の導入

「何も起きない」null baseline を全 competition group に自動注入。
これにより「correlation_break が null に負ける局面」= 「シグナルを出すべきでなかった」が識別可能になる。

## 結論

sign_error_rate 0.666 は「戦略の予測力が低い」のではなく、
**「1 種類の仮説しか持っておらず、場面の使い分けができていない」** が正体。
これは計測系の問題ではなく、KG semantics の問題であり、
Phase 2 の hypothesis competition / regime graph が直接効く領域。
