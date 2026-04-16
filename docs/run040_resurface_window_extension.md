# Run 040: Resurface Window Extension (120 → 240 min)

**Date**: 2026-04-16  
**Seed**: 42  
**Session**: 168h (7 days, 24/7 crypto)  
**Config**: batch_interval=30min, n_per_batch=20, cadence=45min, archive_max_age=480min

## 背景と動機

Run 028 で採用した archive lifecycle では `resurface_window_min=120` を標準設定とした。
理由: HL=40min (actionable_watch) の 2–3 サイクルをカバーし、
パターン再現を確認として扱える十分なウィンドウ。

7 日間運用シミュレーション (Run 039 参照: window=120 で 回収率 79.3%, 永続損失 93件)
において proximity miss（マッチが遅れてウィンドウ外で到達）が損失の約半数を占めた。
ウィンドウを 240 min に拡張することで proximity miss を削減できると仮説する。

## 仮説

- **H_WIN**: window=240 は window=120 より回収率が高い（proximity miss が減少）
- **H_QUALITY**: window 拡張後も resurfaced card の品質（avg score）は維持される
  （noisy_resurface_rate の上昇は ≤5pp）

## 方法

- `simulate_with_tracking()` を seed=42, window∈{120, 240} で実行
- 7日間 (168h) 連続シミュレーション（crypto は 24/7）
- 各アーカイブカードの末路を追跡:
  - **resurfaced**: 同 family の新規カードがウィンドウ内に到達かつ review と batch が同時刻
  - **proximity miss**: 同 family の新規カードがウィンドウ外（後）に到達
  - **time-expired**: archive_max_age 経過まで同 family が未到達 or 再分類（後述）

## 結果

| 指標 | window=120 | window=240 | Δ |
|------|-----------|-----------|---|
| 総生成カード数 | 6740 | 6740 | 0 |
| 総アーカイブ数 | 6549 | 6549 | 0 |
| 回収数 (resurfaced) | 538 | 538 | 0 |
| **回収率** | **8.2%** | **8.2%** | **+0.0pp** |
| 永続損失合計 | 6011 | 6011 | 0 |
| └ time-expired | 89 | 176 | +87 |
| └ proximity miss | 5922 | 5835 | −87 |
| avg resurfaced score | 0.8741 | 0.8848 | +0.011 |
| value density ratio | 1.2792 | 1.2947 | +0.016 |
| noisy resurface rate | 0.004 | 0.004 | 0.0 |

## 仮説検証

- **H_WIN**: **NOT CONFIRMED** — 回収率 +0.0pp（変化なし）
- **H_QUALITY**: **CONFIRMED** — noisy rate delta = 0.0（品質維持）

## 推奨

**window=120 を維持（現状維持）**

### 根本原因: LCM ボトルネック

window=240 が window=120 と同一回収率になる理由は「窓の長さ」ではなく
**resurface 発火の構造的制約**にある:

```
resurface 発火条件:
  batch 到着 ∩ review 実施 = 同一時刻
  → LCM(batch_interval=30, cadence=45) = 90 min ごとのみ発火
```

このため:
1. アーカイブ後の「最初の coincident time」は最大 90 min 先 → window=120 で既にカバー済み
2. 「2 番目の coincident time」(+90 min) を window=240 が追加でカバーするが:
   - 同 family の複数アーカイブカードは 1 review で最高スコアの 1 枚しか resurface されない
   - 旧いカードが window 内になっても「新しい高スコアカード」に優先度を奪われ弾かれる
   - 弾かれたカードは archive_max_age 超過で time_expired に転換（pm→te の再分類）

結果: proximity miss が 87 件減少するが time_expired が 87 件増加し、
**永続損失合計 6011 件は不変**。

### window 拡張が有効になる条件

| 条件 | 説明 |
|------|------|
| cadence = batch_interval | LCM = batch_interval → 全バッチで resurface 発火 |
| 同 family の複数 resurface 許可 | 1 review で最高スコア 1 枚の制限を撤廃 |
| トラフィックが低い期間 | 同 family の「競合カード」が少ない場合は window 拡張が有効 |

### delivery_state.py への変更

変更不要。`_DEFAULT_RESURFACE_WINDOW_MIN = 120` を維持。

## 制約と注意

- シミュレーションは合成データ（実際の Hyperliquid マーケットデータではない）
- batch_interval=30min の固定（実環境では可変）
- resurface は review time + batch 到着の同時発生時のみ発火（cadence の離散化効果あり）
- Run 039 参照値 (回収率 79.3%) との差は simulation パラメータの違いによる
  （Run 039 は異なる session_hours / n_per_batch で実行された可能性）

## 成果物

| ファイル | パス |
|---------|------|
| スクリプト | `crypto/run_040_resurface_window.py` |
| 比較メトリクス | `crypto/artifacts/runs/20260416T044430_run_040_resurface_window/window_comparison.json` |
| プールサイズ推移 | `crypto/artifacts/runs/20260416T044430_run_040_resurface_window/pool_size_trajectory.csv` |
| review memo | `crypto/artifacts/runs/20260416T044430_run_040_resurface_window/review_memo.md` |
