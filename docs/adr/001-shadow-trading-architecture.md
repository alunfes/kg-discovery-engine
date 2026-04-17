# ADR 001: Shadow Trading 基盤アーキテクチャ

**ステータス**: Accepted  
**日付**: 2026-04-17  
**著者**: alunfes  

---

## Context

Run 022〜043 で仮説駆動型バックテストエンジンを確立。canary 指標（7 項目）を
de54528 コミットで凍結済み。次フェーズは **Shadow Trading**:

- KG パイプラインが生成するシグナル（HypothesisCard の surfacing 決定）を
  リアルタイムで記録する
- 実市場価格と突き合わせ「もし実行していたら」の仮想 P&L を計算する
- バックテスト予測精度 vs 実市場の乖離を定量化する
- canary 指標（false_positive_rate, missed_critical_rate など）を実データで計測する

---

## Decision

### Phase 1 — Shadow Trading 基本フレームワーク（本 ADR のスコープ）

```
crypto/src/shadow/
├── types.py           # ShadowSignal / VirtualTrade / PnLResult / CanarySnapshot
├── signal_logger.py   # JSONL 形式でシグナルを記録
├── price_fetcher.py   # Hyperliquid REST API でエントリ/エグジット価格を取得
├── pnl_calculator.py  # 仮想 P&L の計算
├── canary_monitor.py  # 7 指標の計算・閾値チェック
└── shadow_daemon.py   # パイプライン統合・オーケストレーション

crypto/run_shadow.py   # CLI エントリポイント
```

### ストレージ（Phase 1）

JSONL ファイル（stdlib のみ、外部依存なし）:

```
crypto/artifacts/shadow/
├── signals_YYYY-MM-DD.jsonl   # ShadowSignal レコード
├── pnl_YYYY-MM-DD.jsonl       # VirtualTrade レコード（P&L 確定後）
└── canary_YYYY-MM-DD.json     # 日次 canary スナップショット
```

Phase 2 で TimescaleDB へ移行（psycopg2 を追加依存として導入）。

### シグナル生成ロジック

1. パイプラインが StateEvent を検出 → HypothesisCard を生成
2. DeliveryStateEngine が surfacing 判定（push / drop / archive）
3. **Surfaced カード** → `ShadowSignal(surfaced=True)` + エントリ価格を記録
4. **Drop/Archive カード** → `ShadowSignal(surfaced=False)` を記録
   （missed_critical_rate 計算用）

### 方向推定（direction）

event_type / grammar_family から long / short / neutral を推定:

| grammar_family / event_type | direction |
|-----------------------------|-----------|
| flow_continuation / buy_burst | long |
| positioning_unwind / sell_burst / book_thinning | short |
| beta_reversion | short |
| oi_change (accumulation) | long |
| oi_change (unwind) | short |
| cross_asset_stress | short |
| spread_widening / null_baseline | neutral |

### P&L 計算

```
entry_price = mark price at signal_timestamp
exit_price  = mark price at signal_timestamp + half_life_min
pnl_pct     = (exit - entry) / entry   if direction == "long"
            = (entry - exit) / entry   if direction == "short"
            = 0.0                       if direction == "neutral"
pnl_usd     = pnl_pct × notional_usd × conviction
hit         = (pnl_pct > 0)
```

デフォルト `notional_usd = 100.0`。conviction は `StateEvent.severity`。

### Canary 指標の計算タイミング

- 毎サイクル末に増分更新 → 日次ロールアップで `CanarySnapshot` を生成
- halt 条件に到達した瞬間に `shadow_daemon.py` がループを停止し Discord に通知

---

## Phase 2（将来）

- TimescaleDB + psycopg2 でスケーラブルなストレージ
- hype-trading API との連携（ポジションサイジング改善）
- Streamlit ダッシュボード

## Phase 3（将来）

- アラート自動化（Discord / PagerDuty）
- 実注文への段階的移行（canary → live）

---

## Consequences

**Positive**:
- stdlib のみ → デプロイ容易、依存管理不要
- 既存 `pipeline_live.py` の `shadow_mode=True` と完全互換
- canary 指標をリアル市場データで初計測可能になる

**Negative**:
- JSONL は TimescaleDB より集計が遅い（Phase 2 で解決）
- direction 推定が heuristic ベース（backtested accuracy は別途検証が必要）

---

## Alternatives Considered

1. **既存 `run_017_shadow.py` の拡張** — P&L 計算ロジックが散在しており
   テスト困難。独立モジュールとして設計する方が clean。
2. **hype-trading API 経由で P&L を計算** — Phase 2 の選択肢として残す。
   Phase 1 では Hyperliquid REST を直接叩く方が依存が少ない。
