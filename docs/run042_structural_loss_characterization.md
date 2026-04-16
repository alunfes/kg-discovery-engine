# Run 042: Structural Loss Characterization

**Date**: 2026-04-16  
**Seed**: 42  
**Session**: 168h (7 days, 24/7 crypto)  
**Config**: batch_interval=30min, n_per_batch=20, cadence=45min, archive_max_age=480min, resurface_window=120min

## 背景と動機

Run 040 は resurface_window 拡張が永続損失を削減しないことを確認した（LCM ボトルネック）。
Run 041（仮）では proxy_miss と time_expired の構造的原因を仮説した。
本 Run では「どの家族・レジームで loss が集中しているか」を定量化し、
archive_max_age の targeted 延長で回収可能な MITIGATE ケースを特定する。

## 実験設計

- 7日間レジーム: sparse (day1-2), calm (day3-4), active (day5-6), mixed (day7)
- 各カードの archive 時の regime を記録
- 永続損失を time_expired / proximity_miss に分類
- MITIGATE 条件: time_expired AND family ∈ ['cross_asset', 'reversion'] AND regime ∈ ['active', 'calm']

## 結果

### 全体サマリ

| 指標 | 値 |
|------|---|
| 総生成カード数 | 2783 |
| 総アーカイブ数 | 2675 |
| 回収数 (resurfaced) | 275 |
| 回収率 | 10.3% |
| 永続損失合計 | 2400 |
| └ time_expired | 161 |
| └ proximity_miss | 2239 |
| **MITIGATE** | **15** |
| ACCEPT | 2385 |

### 家族 × 損失種別

| grammar_family | time_expired | proximity_miss | MITIGATE |
|----------------|-------------|----------------|---------|
| cross_asset | 45 | 353 | 10 |
| momentum | 16 | 380 | 0 |
| null | 27 | 357 | 0 |
| reversion | 35 | 351 | 5 |
| unwind | 38 | 798 | 0 |

### MITIGATE ケース詳細

**合計: 15 件**

| card_id | family | regime | archived_at (min) | score | tier |
|---------|--------|--------|-------------------|-------|------|
| 360_c005 | reversion | calm | 3570 | 0.6509 | monitor_borderline |
| 367_c012 | reversion | calm | 3570 | 0.6403 | monitor_borderline |
| 310_c000 | reversion | calm | 3600 | 0.4775 | baseline_like |
| 387_c012 | reversion | calm | 3600 | 0.6699 | monitor_borderline |
| 388_c013 | reversion | calm | 3600 | 0.6163 | monitor_borderline |
| 710_c000 | cross_asset | calm | 5100 | 0.4756 | baseline_like |
| 735_c018 | cross_asset | calm | 5130 | 0.7640 | research_priority |
| 797_c015 | cross_asset | calm | 5130 | 0.4943 | reject_conflicted |
| 729_c012 | cross_asset | calm | 5160 | 0.6542 | monitor_borderline |
| 765_c004 | cross_asset | calm | 5160 | 0.7969 | actionable_watch |
| 786_c004 | cross_asset | calm | 5220 | 0.8911 | actionable_watch |
| 776_c015 | cross_asset | calm | 5250 | 0.7206 | monitor_borderline |
| 810_c008 | cross_asset | calm | 5250 | 0.9293 | actionable_watch |
| 799_c017 | cross_asset | calm | 5265 | 0.6854 | research_priority |
| 800_c018 | cross_asset | calm | 5265 | 0.7142 | research_priority |

avg MITIGATE score: 0.6787

## 解釈

### MITIGATE ケースの構造

cross_asset および reversion 家族は calm/active レジームにおいて
シグナル間隔が 480–720 min に集中する（daily cycle による自然な間隔）。
archive pool が 480min で削除されることで、次のシグナルが到達する前に
pool から消えてしまう。これは window 問題ではなく **retention 問題**。

### ACCEPT ケース（変更不可）

proximity_miss (2239 件): 同家族シグナルは
window 内に到達しているが review×batch の LCM タイミングに外れている。
archive_max_age を延長しても回収不可（cadence 構造の問題）。

## 推奨

**Run 043**: cross_asset + reversion 家族を calm/active レジームで archive_max_age 480→720 min に延長し、15 件の MITIGATE ケース回収を検証。

## 成果物

| ファイル | 内容 |
|---------|------|
| artifacts/.../loss_breakdown.csv | 家族×レジーム×分類の集計 |
| artifacts/.../mitigate_cases.csv | MITIGATE 個別カード詳細 |
| artifacts/.../pool_size_trajectory.csv | プールサイズ推移 |
