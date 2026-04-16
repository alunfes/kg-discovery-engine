# Run 043 Review Memo — Targeted Archive Extension
*Date: 2026-04-16 | Seed: 42 | Session: 168h (7 days)*

## 実験目的

Run 042 で特定された MITIGATE ケースを archive_max_age 480→720min の
targeted 延長（cross_asset + reversion / calm + active レジーム）で回収する。

## 結果比較

| 指標 | Baseline (480) | Extended (720) | Δ |
|------|---------------|----------------|---|
| 総アーカイブ数 | 2675 | 2675 | +0 |
| 回収数 | 275 | 275 | +0 |
| 回収率 | 10.3% | 10.3% | +0.0pp |
| 永続損失 | 2400 | 2400 | +0 |
| └ time_expired | 161 | 146 | -15 |
| └ proximity_miss | 2239 | 2254 | +15 |
| avg resurfaced score | 0.7963 | 0.7963 | +0.0000 |
| value density ratio | 1.1993 | 1.1993 | +0.0000 |
| noisy resurface rate | 0.0945 | 0.0945 | +0.0000 |
| pool bloat | — | — | +11.9% avg |

## MITIGATE ケース回収

- Run 042 MITIGATE: 15 件
- 回収成功: **0 件**
- 回収失敗: 15 件（LCM タイミング制約またはウィンドウ外）

## 結論

targeted 延長により 0/15 MITIGATE ケースを回収。
永続損失 +0 件, 回収率 +0.00pp 改善。
pool bloat +11.9%（許容範囲内）。
Noisy resurface rate 変化: +0.0000
