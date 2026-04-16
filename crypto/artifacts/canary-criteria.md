# Canary 指標 & Rollback 条件 — Shadow Trading 事前定義

*作成日: 2026-04-16*  
*ベース config: [run034 frozen config](runs/20260416T120000_run034_packaging/recommended_config.json)*  
*Run 035 canary 実測: [20260416T160000_run035_live_canary](runs/20260416T160000_run035_live_canary/)*  
*目的: Shadow 開始前に成功/失敗基準を凍結し、後付け解釈を防ぐ*

---

## 1. Canary 指標（7項目）

### 必須 4 指標

---

#### 1-A. reviews/day

| 項目 | 内容 |
|------|------|
| **定義** | 1日（8h × 3セッション換算）に配信されたレビュー合計数。push（T1/T2）+ fallback（poll_45min）の合算。 |
| **計測方法** | `n_reviews` / セッション × 3（または実稼働時間から補外）。push と fallback の内訳を必ず併記。 |
| **Run 035 実測** | **31.9/day**（push: 18.9/day + fallback: 14.1/day）|
| **Run 034 定義閾値** | warn: 25/day、alert: 35/day |
| **Shadow 適用閾値** | warn: **35/day**（run035 canary_decision 推奨: push+fallback 合算に対し再校正）、alert: **50/day** |
| **注記** | push 単体は 18.9/day で run028 目標（< 20/day）を満たしている。warn 超過は fallback 込みの合算が原因であり、構造的に想定内。 |

---

#### 1-B. false positive rate

| 項目 | 内容 |
|------|------|
| **定義** | surfaced（配信）したが actionable でなかった card の比率。 |
| **計測方法** | 配信した card のうち、配信後 24h 以内に当該銘柄の price move（絶対値）が ±3% 未満だったものの割合。price move は OHLCV の max(high−open, open−low) を使用。 |
| **Run 034/035 実測** | 合成データのため未計測（Shadow-3 で初計測）。 |
| **閾値** | warn: > 20%、**halt: > 30%** |
| **注記** | Shadow-1/2 ではまだ計測しない（synthetic 比乖離・Canary 指標の安定を優先）。Shadow-3 から本格計測。 |

---

#### 1-C. missed critical rate

| 項目 | 内容 |
|------|------|
| **定義** | 配信しなかった（DROP/ARCHIVE された）card のうち、後続 24h 以内に ±5% 以上の price move と相関したものの割合。 |
| **計測方法** | DROP/ARCHIVE 時刻から 24h の price を取得し、5% 超の move が発生した card 数 ÷ 総 DROP/ARCHIVE 数。 |
| **Run 035 実測** | **0**（全 20 seed で missed_critical = 0）。Run 028 でも 0。 |
| **閾値** | 理想: 0。**halt: > 5%（1 日でも発生した場合、即時停止）** |
| **注記** | 唯一の non-negotiable 指標。閾値を超えた時点で即日停止しパラメータ調査を行う。 |

---

#### 1-D. latency

| 項目 | 内容 |
|------|------|
| **定義** | market data tick 受信から push 判定 output（配信可否フラグ）までの処理遅延。 |
| **計測方法** | shogun VPS 上で `tick_received_at` → `push_decision_at` のタイムスタンプ差分を median / p95 で記録（アプリ内ロギング）。 |
| **Run 034/035 実測** | 合成データのため未計測。Shadow-1 初日にベースライン計測を実施。 |
| **閾値** | warn: > 5s（median）、**halt: > 15s が 1 時間内に 10 回以上** |
| **注記** | halt 条件はデータ鮮度の毀損（HL が 40〜90min のカードが陳腐化）を防ぐための緊急停止基準。 |

---

### 追加 3 指標

---

#### 1-E. fallback 発火率

| 項目 | 内容 |
|------|------|
| **定義** | 全レビューのうち poll_45min fallback がトリガーしたレビューの割合（%）。regime 別（quiet / hot）に集計。 |
| **計測方法** | `n_fallback_activations / n_reviews × 100`。quiet（hot_prob < 0.3）と hot（hot_prob ≥ 0.5）を別集計。 |
| **Run 035 実測** | 全体 42%。quiet regime: ~82%（11 reviews 中 ~9 が fallback）、hot regime: ~3%（33 reviews 中 ~1）。 |
| **期待値** | quiet: 高め（70〜90%）、hot: 低め（< 20%）。push が正しく機能していれば hot 時に fallback は減少する。 |
| **異常値** | **hot regime で > 50%** → push トリガー（T1/T2）が機能していない兆候。即日調査。 |
| **閾値** | Run 034 定義: warn > 30%（全体）、alert > 60%（全体）。hot 専用: > 50% で即調査。 |

---

#### 1-F. surfaced family coverage

| 項目 | 内容 |
|------|------|
| **定義** | 1 日に少なくとも 1 枚以上 surfaced された KG ファミリーの種類数（5 ファミリー中）。 |
| **計測方法** | 配信 card の `grammar_family` distinct count を日次集計。5 ファミリー: `cross_asset`, `momentum`, `reversion`, `unwind`, `beta_reversion`（またはその時点の有効ファミリー一覧）。 |
| **Run 035 実測** | 合成: **5.0/session（100%）**。7-day 実データ模擬: **4/day**（L2 制約で beta_reversion / flow_continuation が未発火）。 |
| **期待値** | ≥ 3/day。Shadow 開始直後は L2 制約（OI/funding 欠損）により 3〜4 が現実的。 |
| **閾値** | warn: < 3/day が 3 日連続、halt: < 2/day が 2 日連続（単一ファミリー支配 = 多角的洞察の喪失）。 |
| **注記** | L2 修正（OI WebSocket 追加）後は 5/day が目標になる。それまでは warn 閾値を 2 に据え置く。 |

---

#### 1-G. operator burden

| 項目 | 内容 |
|------|------|
| **定義** | 1 日あたりのオペレーター手動介入回数。「手動介入」= Shadow daemon の手動停止・再起動・パラメータ変更・アラート確認応答のうち unplanned なもの。 |
| **計測方法** | shogun VPS の操作ログ（または Discord アクティビティ）から手動介入を日次カウント。計画外の操作のみカウント（scheduled メンテは除外）。 |
| **Run 035 実測** | 合成のため 0（Shadow 期間の目標値）。 |
| **期待値** | Shadow 期間中は 0 が理想。alert/warn 頻発で手動停止→再開が必要になる場合、パラメータが合っていない兆候。 |
| **閾値** | warn: > 1/day、**alert: > 3/day が 2 日連続 → 手動判断（Phase 継続可否を評価）** |

---

## 2. Rollback 条件

以下の条件を充足した時点で Shadow を停止し、原因調査を実施する。

### 自動停止

| ID | 条件 | 根拠 |
|----|------|------|
| AUTO-1 | `reviews/day > 50`（alert 閾値）が **3 日連続** | オペレーター過負荷のリスク |
| AUTO-2 | `fallback 発火率（全体）> 60%`（alert 閾値）が **3 日連続** | push トリガー機能不全 |
| AUTO-3 | `surfaced family coverage < 2/day` が **2 日連続** | 単一ファミリー支配 |

### 即時停止（1 日でも発生したら停止）

| ID | 条件 | 根拠 |
|----|------|------|
| HALT-1 | `missed_critical_rate > 5%` | 重要シグナルを見逃している = システム根本欠陥 |
| HALT-2 | `latency > 15s` が 1 時間内に 10 回以上 | データ鮮度毀損でバックテスト前提が崩れる |
| HALT-3 | hot regime で `fallback 発火率 > 50%` | T1/T2 push 機能不全の確定 |

### 手動判断（継続可否をオペレーターが評価）

| ID | 条件 | 根拠 |
|----|------|------|
| MANUAL-1 | `operator_burden > 3/day` が **2 日連続** | 自動化が機能していない |
| MANUAL-2 | `false_positive_rate > 30%`（halt 閾値）が 1 日でも発生 | 配信品質の根本的問題 |
| MANUAL-3 | `reviews/day > 35` が 5 日連続（自動停止未到達でも疲弊リスク）| 疲弊による見逃しリスク |

---

## 3. Shadow Phase 定義

| Phase | 期間 | 主目的 | 成功基準 |
|-------|------|--------|----------|
| **Shadow-1** | 7 日 | 実データ vs synthetic 乖離測定（L1 解消）。latency ベースライン計測。 | 全 halt 条件に非該当 + `reviews/day` が synthetic 比 ±30% 以内（31.9 ×0.7〜1.3 = 22〜41/day の範囲） |
| **Shadow-2** | 7 日 | Canary 指標（1-A〜1-G）実測・warn 閾値内を確認。L2 OI/funding fix の効果検証。 | 全 warn 閾値内、`family_coverage ≥ 3/day`、`operator_burden = 0/day` |
| **Shadow-3** | 7 日 | T1/T2 精度検証（false_positive / missed_critical の実測）。 | `false_positive < 20%`、`missed_critical = 0`、全 halt 条件に非該当 |

全 3 Phase（計 21 日）をパスした時点で Production 昇格を検討する。

---

## 4. Phase 間ゲート

各 Phase 終了時に以下を実施してから次 Phase へ進む。

1. **クロスレイヤーバグ監査**: lessons-learned のパターン（特に「合成→実データ乖離」「L2 制約残留」）を確認。未解決の known_limits が本 Phase の成功基準に影響していないか検証。
2. **指標ダッシュボード確認**: 7 日分のログを集計し、全指標を本ドキュメントの閾値表に照らして Pass / Warn / Halt を判定。
3. **Warn 発生時**: パラメータ調整案を提示し、**ユーザー承認後**に調整→同 Phase を再実行。自動で次 Phase へは進まない。
4. **Halt 発生時**: 即停止→原因調査→修正→Phase-1 からやり直し。

---

## 5. 参照 config / run 一覧

| ファイル | 用途 |
|--------|------|
| [run034 recommended_config.json](runs/20260416T120000_run034_packaging/recommended_config.json) | 本 Shadow の凍結 config（T1/T2 閾値、suppressor、fallback 設定） |
| [run035 canary_decision.md](runs/20260416T160000_run035_live_canary/canary_decision.md) | Canary 指標の synthetic 実測値と閾値校正根拠 |
| [run035 live_delivery_metrics.csv](runs/20260416T160000_run035_live_canary/live_delivery_metrics.csv) | 20 seed × reviews/day の分布（基準値導出元） |
| [run035 fallback_usage.md](runs/20260416T160000_run035_live_canary/fallback_usage.md) | fallback 発火率の regime 別内訳 |
| [run035 family_coverage_live.md](runs/20260416T160000_run035_live_canary/family_coverage_live.md) | ファミリー coverage と L2 制約 |
| [run035 day_by_day.csv](runs/20260416_run035_live_canary/day_by_day.csv) | 7 日間 × regime 別の reviews/fallbacks 実測値 |
| [run034 known_limits.md](runs/20260416T120000_run034_packaging/known_limits.md) | L1〜L6 既知制約一覧（Shadow 中の想定外挙動判断基準） |

---

*このファイルは Shadow 開始前に確定済み。Shadow 期間中の指標結果が芳しくない場合でも、本ファイルの閾値を遡及的に変更してはならない。変更が必要な場合は新しい revision として追記し、変更前の基準を保持すること。*
