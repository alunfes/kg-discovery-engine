# KG Discovery Engine — Development Roadmap

**策定日**: 2026-04-19
**方針**: 3レーン並行 (Shadow reliability / KG semantics / Research ingestion)
**核心**: signal 抽出器から仮説運用OSへの進化

---

## 全体方針

### Lane A: Shadow Reliability
計測系の受入完了。目的は「戦略評価可能な観測基盤」にすること。

### Lane B: KG Semantics Upgrade
仮説ノード・矛盾・代替仮説・無効化条件を第一級化。
目的は「イベント整理」から「仮説運用OS」へ進化させること。

### Lane C: Research KG Ingestion
論文・過去 run・レビュー・設計メモを構造化して吸い上げる。
目的は「live market state」と「既知の mechanism」を接続すること。

---

## Phase 1: 計測系の受入完了 (Week 1)

### 1-1. 完走受入
- 100-cycle 完走
- 受入条件6点: sign_error_rate, fetch_miss_count, duplicate_count, regime_events, canary snapshot, restart=0

### 1-2. Partial Canary
- 5-10 cycle ごとの中間 snapshot
- pending_count, resolved_count, pending_age_p95 追加
- 品質判定レイテンシ 100分→5-10分に短縮

### 1-3. Failure Telemetry
- no_events, ws_stale, queue_growth, pending_stall, canary_snapshot_missing を明示的 failure code 化
- 障害が「静かな失敗」にならない構造

---

## Phase 2: 仮説OS化 (Week 2-3)

### 2-1. Hypothesis Node 導入
属性: hypothesis_id, claim, family, regime_dependency, horizon, evidence_strength,
contradiction_pressure, novelty, execution_feasibility, invalidation_conditions,
alternative_hypotheses, next_observations

event は hypothesis を支える材料、signal は hypothesis から導かれる1つの表現。

### 2-2. Relation Semantics 拡張
supports, contradicts, reroutes_to, invalidates, depends_on, explains,
co_occurs_with, requires_observation

### 2-3. Competing Hypotheses Engine
- 同一 market state に対して複数仮説生成
- 仮説同士の競合・reroute の構造化
- 出力: 主仮説 + 代替仮説 + 反証条件 + 追加観測候補

---

## Phase 3: Regime Graph 独立化 (Week 4)

### 3-1. Regime Node Layer
quiet / transition / active, trend persistence, funding stress,
liquidity fragility, cross-asset coupling, dealer imbalance, event shock proximity

### 3-2. Regime-conditioned Hypothesis
- 仮説がどの regime で成立/失効するか
- regime shift で仮説寿命を更新
- 同じ signal でも regime 次第で別評価

---

## Phase 4: Failure Graph 導入 (Week 4)

### 4-1. Failure KG
ノード: false_positive_cluster, duplicate_pattern, fetch_miss_cause,
reroute_confusion_site, stale_signal, overfit_family, regime_misclassification
エッジ: caused_by, amplified_by, hidden_by, co_occurs_with, fixed_by

### 4-2. Auto Postmortem
- shadow run 完了後に failure graph 自動更新
- 改善が属人的な勘でなく knowledge として蓄積

---

## Phase 5: Research KG Ingestion (Week 5)

### 5-1. Ingestion Pipeline
入力: 論文, ブログ, market microstructure notes, review memo, 過去 run レポート, 設計議論ログ
抽出単位: claim, assumption, evidence, applicable regime, failure regime, execution constraint

### 5-2. Research Claim Schema
claim_id, source, domain, asset_scope, market_scope, horizon, supporting_evidence,
contradictions, operating_conditions, break_conditions, implementation_notes

### 5-3. Market KG との接続
Research KG の mechanism を live state にマッピング。
「この live 仮説は、どの既存メカニズム知識で裏づけられるか」を即座に出せる。

---

## Phase 6: Active Experiment Planner (Week 6)

### 6-1. Next Best Observation
- 競合仮説群を列挙 → 最も識別できる追加観測を提案
- 観測コスト見積もり

### 6-2. Information Gain Scoring
uncertainty reduction, observation cost, expected actionability, latency penalty

---

## Phase 7: Portfolio-aware Output (Week 6)

### 7-1. Recommendation Object
main hypothesis, alternatives, size suggestion, conviction, invalidation,
expected holding window, liquidity risk, correlation impact, execution difficulty, cancellation rule

### 7-2. Portfolio Interaction Layer
複数仮説の相関、同一メカニズムへの重複露出抑制、family 偏り抑制、regime 切替時のポジション更新

---

## 評価指標 (継続計測)

### Reliability
first-cycle latency, heartbeat continuity, fetch miss rate, duplicate rate, pending stall rate

### Hypothesis Quality
hypothesis precision@k, contradiction detection latency, reroute quality,
invalidation correctness, alternative hypothesis usefulness

### Discovery Quality
novelty-adjusted actionability, execution-feasible discovery rate,
regime-conditioned expectancy, failure mode coverage, knowledge half-life

---

## 優先順位

| 優先度 | 内容 |
|--------|------|
| P0 | Shadow acceptance + partial canary + failure telemetry |
| P1 | Hypothesis node + relation semantics + competing hypotheses |
| P2 | Regime graph + failure graph |
| P3 | Research KG ingestion + claim extractor + claim-to-market linker |
| P4 | Active observation planner + portfolio-aware recommendation |
