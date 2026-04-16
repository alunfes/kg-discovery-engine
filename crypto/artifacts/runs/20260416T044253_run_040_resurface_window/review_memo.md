# Run 040 Review Memo — Resurface Window 120 vs 240
*Date: 2026-04-16 | Seed: 42 | Session: 168h (7 days)*

## 実験目的

resurface_window_min を 120→240 に拡張した場合の効果を定量評価。
主な懸念: 永続損失の削減 vs noisy resurface の増加リスク。

## 結果サマリ

| 指標 | window=120 | window=240 | Δ (240-120) |
|------|-----------|-----------|------------|
| 総生成カード数 | 6740 | 6740 | 0 |
| 総アーカイブ数 | 20 | 20 | 0 |
| 回収数 (resurfaced) | 10 | 14 | +4 |
| **回収率** | **50.0%** | **70.0%** | **+20.0pp** |
| 永続損失 | 10 | 6 | -4 |
| └ time-expired | 0 | 0 | 0 |
| └ proximity miss | 10 | 6 | -4 |
| avg resurfaced score | 0.7276 | 0.7339 | 0.0063 |
| value density ratio | 1.0367 | 1.0458 | 0.0091 |
| noisy resurface rate | 0.2000 | 0.1429 | -0.0571 |

## 解釈

- **回収率**: window=240 は 50.0% → 70.0%（+20.0pp）
- **永続損失**: 10 → 6 (減少)
- **proximity miss 削減**: 10 → 6
  - ウィンドウ拡張で 4 件が回収に転換
- **Noisy resurface**: rate 0.200 → 0.143
  - スコア0.6未満の低品質 resurface が減少・同水準

## 判定

**推奨: window=240**

判定基準:
- 回収率改善 > 0pp → 有益
- noisy_resurface_rate の増加 ≤ 5pp → 許容範囲
- value_density_ratio の低下 ≤ 2% → 品質維持

## アーティファクト

| ファイル | 内容 |
|---------|------|
| window_comparison.json | window=120/240 の比較メトリクス |
| pool_size_trajectory.csv | 時系列アーカイブプールサイズ |
| run_config.json | 実験設定 |
