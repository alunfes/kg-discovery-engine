# Competition Analysis: Live Shadow Artifacts

**Date**: 2026-04-19
**Artifact**: live `kg-shadow` run (41 cycles, 364 cards)
**Purpose**: Phase 2 の改善が live output でも成立するか検証

## Before/After 比較

| metric | before | after (corr_break) | after (resting) |
|--------|-------:|-------------------:|----------------:|
| families/group mean | 1.0 | **5.0** | **5.0** |
| null win % | 0% | 0% | 0% |
| confidence median | 0.053 | 0.053 | 0.005 |
| regime-decayed groups % | 0% | **100%** | **100%** |
| contradiction edges/group | 0.0 | **2.0** | 1.0 |

## 主要発見

### 1. Family Diversity は機能している
- before: 全 group が cross_asset のみ (1.0 family/group)
- after: 全 group が 5 family に拡張 (cross_asset + momentum + reversion + regime_continuation + null)
- **diversifier は live でも正常動作**

### 2. Regime Decay は劇的に効く
- **correlation_break regime**: cross_asset が primary (期待通り)
- **resting_liquidity regime**: **regime_continuation が primary に昇格** — cross_asset が全て 0.5x に減衰
- regime 切替で勝者が完全に入れ替わる → 場面の使い分けが機能

### 3. Null はまだ勝たない
- null の evidence=0.35 に対して、cross_asset は 0.567、regime_continuation は 0.352
- null が勝つには real hypothesis が 0.35 未満に落ちる必要がある
- 現状では最弱の仮説でも null を上回る → no-trade 判定は出ない

### 4. Confidence は低いまま
- 0.053 (corr_break) → 0.005 (resting) — どちらも低い
- 原因: 同一 asset 内に 200+ の cross_asset cards が同等スコアで並ぶ
- primary と best alternative の gap がほぼゼロ

## 定性レビュー (5 groups)

### BTC in correlation_break regime
- Primary: cross_asset (ne=0.567) — correlation break が本命
- Alternative 1: cross_asset (ne=0.567) — 同等の別 cross_asset card
- Null (ne=0.35) は最下位 — BTC に edge があるという判定は妥当
- **判定: 正しい方向だが、同一 family 内の差別化が不足**

### BTC in resting_liquidity regime
- Primary: regime_continuation (ne=0.352) — 「何も変わらない」が勝利
- cross_asset 全 cards が 0.5x decay → ne=0.284
- **判定: 非常に妥当 — resting 時に correlation break を追うべきでない**

### ETH in correlation_break regime
- BTC とほぼ同一構造 — family diversity は asset 間で均一に効いている
- ETH 特有の differentiation はまだない

### HYPE in resting_liquidity regime
- regime_continuation が primary (ne=0.352) — 妥当
- HYPE の cross_asset cards が decay → small cap の correlation break は特に regime 依存が強いはず
- **判定: regime decay の設計意図通り**

### 全体的な "null が勝つべきだった" 局面の不在
- 364 cards 全てが cross_asset で、evidence 飽和が起きている
- パイプラインが「弱い根拠でも card を出す」設計のため、null を下回る card が生まれにくい
- **改善案: card 生成段階で evidence threshold を厳格化すべき**

## 判定

### 接続判定条件 vs 実績

| 条件 | 目標 | 実績 | 判定 |
|------|------|------|------|
| families/group >= 3 | 3+ | **5.0** | PASS |
| confidence median >= 0.2 | 0.2+ | **0.053** | FAIL |
| null wins 10-35% | 10-35% | **0%** | FAIL |
| regime decay で順位変動 | あり | **あり (cross_asset→regime_continuation)** | PASS |
| alternative が人間レビューで妥当 | 妥当 | **妥当 (regime_continuation in resting)** | PASS |

**結果: 6条件中 3 PASS, 2 FAIL**

### FAIL の原因分析

**confidence FAIL**: 同一 family (cross_asset) 内に 200+ cards が同等スコアで並ぶため。
これは competition engine の問題ではなく、パイプラインが同一メカニズムの微小変種を大量生産している問題。

**null win FAIL**: card 生成に最低 evidence threshold がなく、弱い仮説でも card として出力されるため。
null (0.35) を下回る card がそもそも生まれない。

### 改善方向

1. **Card 生成の evidence threshold 導入** — plausibility_prior が 0.4 未満なら card を出さない
2. **Cycle-level grouping** — asset 単位でなく (asset, cycle) 単位で競合させ、200+ cards の横並びを避ける
3. **Cross_asset 内部の subgroup 化** — correlation pair, OI duration, break_score で内部差別化

## 結論

Phase 2 の改善は live artifact でも成立する。特に regime decay は劇的に効き、
resting_liquidity で cross_asset → regime_continuation への切替が正しく動作している。

ただし confidence と null win は目標未達。
原因は competition engine ではなく、**パイプラインの仮説生成粒度** (同一 family の大量重複) と
**card 生成閾値の不在** (弱い仮説でも出力される) にある。
