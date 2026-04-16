# Run 043: Targeted Archive-Age Extension

**Date**: 2026-04-16  
**Seed**: 42  
**Session**: 168h (7 days, 24/7 crypto)  
**Config**: batch_interval=30min, n_per_batch=20, cadence=45min, baseline_max_age=480min, extended_max_age=720min

## 背景と動機

Run 042 の構造的損失分析により、cross_asset および reversion 家族の
calm/active レジームにおけるカードが archive pool の 480min 制限で
削除されていることが判明（MITIGATE 分類: 15 件）。

本 Run では archive_max_age を家族×レジーム軸で targeted に延長し、
これらの MITIGATE ケースを回収できるか検証する。

## 変更内容

| 対象 | 変更前 | 変更後 |
|------|--------|--------|
| cross_asset + reversion (calm/active) | 480min | 720min |
| その他すべての家族/レジーム | 480min | 480min（変更なし）|

実装: `delivery_state.py` の `ArchiveManager` に `family_max_age_overrides` を追加。
シミュレーション: archive 時の regime を記録し prune 時に per-card max_age を適用。

## 結果

| 指標 | Baseline (480) | Extended (720) | Δ |
|------|---------------|----------------|---|
| 総生成カード数 | 2783 | 2783 | 0 |
| 総アーカイブ数 | 2675 | 2675 | +0 |
| 回収数 (resurfaced) | 275 | 275 | +0 |
| **回収率** | **10.3%** | **10.3%** | **+0.0pp** |
| 永続損失合計 | 2400 | 2400 | +0 |
| └ time_expired | 161 | 146 | -15 |
| └ proximity_miss | 2239 | 2254 | +15 |
| avg resurfaced score | 0.7963 | 0.7963 | +0.0000 |
| value density ratio | 1.1993 | 1.1993 | +0.0000 |
| noisy resurface rate | 0.0945 | 0.0945 | +0.0000 |
| avg pool size bloat | — | — | +11.9% |

## MITIGATE ケース回収検証

- Run 042 MITIGATE 件数: 15 件
- 回収成功: **0 件** (0.0%)
- 回収失敗: 15 件

## 根本原因分析 — なぜ延長は無効だったか

### te→pm 再分類現象

| 段階 | Baseline (max_age=480) | Extended (max_age=720) |
|------|------------------------|------------------------|
| archive後 0–120min | resurface_window内 → 回収対象 | 同左 |
| archive後 120–480min | window外到着 → proximity_miss | 同左 |
| archive後 480–720min | pool削除済み → time_expired | window外到着 → proximity_miss |
| archive後 720min以降 | — | pool削除 → time_expired |

15件のMITIGATEカードは:
1. archive後0–120minに同family信号なし（resurface発火不可）
2. archive後480–720minに同family信号が到着
3. **しかし到着時点で (t - archived_at) > 120min → resurface_window外 → proximity_miss**

`archive_max_age` を延長しても `resurface_window=120min` の制約は変わらないため、
延長は「time_expired→proximity_miss」の再分類のみをもたらし、回収には至らない。

### 結論: binding constraintは resurface_window

```
MITIGATE回収のための必要条件:
  same-family信号が archived_at + resurface_window 以内に到達すること
  ↑ archive_max_age延長では解決不可
  ↑ resurface_window拡張で解決可能だが、Run040でLCMボトルネック確認済み
```

永続損失2400件の真の内訳:
- **proximity_miss** (93.9%): 同family信号は到達するがresurface_windowまたはLCMで弾かれる
- **time_expired** (6.1%): 同family信号が一切到達しない（孤立シグナル）

## 副作用チェック

- **Pool bloat**: +11.9% avg → 許容範囲内
- **Noisy resurface**: rate Δ = +0.0000 → 問題なし
- **Value density**: ratio Δ = +0.0000 → 維持

## 推奨

**DO NOT ADOPT**: targeted archive_max_age 延長 (cross_asset/reversion, calm/active, 480→720min)

### delivery_state.py への変更

```python
# ArchiveManager に family_max_age_overrides を渡す（Run 043 で実装済み）
mgr = ArchiveManager(
    archive_max_age_min=480,
    family_max_age_overrides={
        'cross_asset': 720,
        'reversion':   720,
    }
)
```

## 成果物

| ファイル | 内容 |
|---------|------|
| before_after_loss.csv | Baseline vs Extended の全指標比較 |
| archive_pool_impact.md | プールサイズ影響分析 |
| recovered_cases.md | MITIGATE ケース個別回収確認 |
| recommendation.md | 採用判断基準と結論 |
| pool_size_trajectory.csv | 時系列プールサイズ (baseline vs extended) |
