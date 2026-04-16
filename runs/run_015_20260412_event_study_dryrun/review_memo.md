# Run 015 — Event Study Scaffold Dry-Run

**Date**: 2026-04-12  
**Type**: scaffold validation (synthetic data)  
**Status**: dry-run complete — all pipelines executed without error

---

## 実施内容

event study scaffold をゼロから実装し、合成データで 3 候補の dry-run を実施。

### 実装ファイル

| ファイル | 内容 |
|---------|------|
| `src/eval/event_study.py` | core scaffold (370 行) |
| `tests/test_event_study.py` | 67 件 unit tests (TDD) |
| `configs/event_study_C1_*.json` | SOL funding_extreme → HYPE vol_burst (single) |
| `configs/event_study_C2_*.json` | ETH vol_burst → BTC vol_burst → HYPE pm (chained) |
| `configs/event_study_C3_*.json` | SOL funding_extreme → BTC pm → HYPE pm (chained) |
| `scripts/run_event_study_dryrun.py` | dry-run runner |

---

## Dry-Run 結果 (合成データ)

> ⚠️ 以下は合成データ (seed=42, N=1000 bars, ランダム walk) での動作確認。実際の仮説検証ではない。

| 候補 | event_count | hit_rate | mean_ret | p≈ | chain_count | concentration |
|------|-------------|----------|----------|----|-------------|---------------|
| C1 (single) | 33 | 42.4% | -0.0051 | 0.50 | — | — |
| C2 (chained) | 6 | — | — | 0.50 | 8 | 100% |
| C3 (chained) | 12 | — | — | 0.50 | 37 | 100% |

p≈0.50 は期待通り（合成データは null と同等のはず）。

---

## 仕様カバレッジ確認

| 仕様項目 | 実装状態 |
|---------|---------|
| config-driven (JSON) | ✅ 完全実装 |
| event extraction + intensity filter | ✅ 完全実装 |
| deduplication | ✅ 完全実装 |
| estimation / event window | ✅ 完全実装 |
| forward return | ✅ 完全実装 |
| abnormal return | ✅ SCAFFOLD (per-bar mean baseline) |
| volatility shift | ✅ 完全実装 |
| hit rate | ✅ 完全実装 |
| bootstrap / permutation | ✅ SCAFFOLD (empirical p-value, n=20) |
| chained event extraction | ✅ 完全実装 (再帰) |
| bridge metrics (freq/unique/concentration) | ✅ 完全実装 |
| null baseline ×4 | ✅ SCAFFOLD 4種実装 |
| regime slice | ✅ SCAFFOLD (アノテーションのみ、filter未適用) |
| provenance 保存 | ✅ 完全実装 |
| dedup (重複カウント抑制) | ✅ 完全実装 |
| report (markdown) | ✅ 完全実装 |
| run artifact 保存 | ✅ 完全実装 |

---

## SCAFFOLD として仮置きの項目

1. **abnormal return baseline**: 単純 per-bar 平均。CAPM / factor model に要差し替え
2. **null baseline 統計的严格性**: n=20 iterations、単純パーミュテーション。本番は n≥1000、bootstrap CI 要対応
3. **regime slice filter**: アノテーションのみ。`realized_vol_percentile` 等の実フィルタ未実装
4. **target event matching**: C1 では source event timestamp から HYPE return を計算しているが、target event (HYPE vol_burst) の発生有無を lead_lag 内でカウントする機能は未実装

---

## 次に固定すべき設定

本検証に進むために確定が必要な項目:

| 項目 | 現状 | 要決定事項 |
|------|------|-----------|
| estimation_window_bars | 168h (7d) | 適切か？実データの分布を見て調整 |
| event_window_bars | 24h | 適切か？ |
| dedup_window_bars | 4h | 適切か？ |
| null model | random / shuffled / matched_vol / matched_sym | どれを採用するか、または複数組み合わせ |
| p-value threshold | 未定義 | 0.05 or 0.10 or two-sided? |
| regime_slice filter | SCAFFOLD | 実データで実装するか / 当面スキップするか |
| n_iterations (null) | 20 (scaffold) | 本番は 1000+ 要 |

---

## 次に実行すべきコマンド

### 実データで検証に入る場合
```bash
# 1. 実データの state events を取得 (既存パイプライン利用)
# 2. 下記コマンドで dry-run を実データで実行
python scripts/run_event_study_dryrun.py
# (ohlcv_map と source_events を実データに差し替える)
```

### テストを再確認
```bash
python -m pytest tests/test_event_study.py -v
```

### 全テスト確認
```bash
python -m pytest tests/ -q
```
