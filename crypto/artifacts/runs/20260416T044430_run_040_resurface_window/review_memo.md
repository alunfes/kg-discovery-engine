# Run 040 Review Memo — Resurface Window 120 vs 240
*Date: 2026-04-16 | Seed: 42 | Session: 168h (7 days)*

## 実験目的

resurface_window_min を 120→240 に拡張した場合の効果を定量評価。
主な懸念: 永続損失の削減 vs noisy resurface の増加リスク。

## 結果サマリ

| 指標 | window=120 | window=240 | Δ (240-120) |
|------|-----------|-----------|------------|
| 総生成カード数 | 6740 | 6740 | 0 |
| 総アーカイブ数 | 6549 | 6549 | 0 |
| 回収数 (resurfaced) | 538 | 538 | 0 |
| **回収率** | **8.2%** | **8.2%** | **+0.0pp** |
| 永続損失合計 | 6011 | 6011 | 0 |
| └ time-expired | 89 | 176 | +87 |
| └ proximity miss | 5922 | 5835 | −87 |
| avg resurfaced score | 0.8741 | 0.8848 | +0.0107 |
| value density ratio | 1.2792 | 1.2947 | +0.0155 |
| noisy resurface rate | 0.004 | 0.004 | 0.0 |

## 解釈

### 回収率
window=120 と window=240 で **回収率は同一 (8.2%)**。
proximity miss が 87 件減少するが、その分だけ time_expired が 87 件増加し、
永続損失の合計は 6011 件で変化なし。

### proximity miss → time_expired の再分類メカニズム
window=240 では、以前 proximity miss（window 外マッチ）と判定されていた 87 件のカードが
「in-window」扱いになる。しかし実際には resurface されず time_expired に転換する理由:

- resurface が発火するのは **バッチ到着と review が同時刻 (LCM(30,45)=90 min ごと)** のみ
- 90 min 以内にある「最初の coincident time」は window=120 でも window=240 でも等価
- 同 family の複数アーカイブカードは 1 review で **1 枚しか resurface されない**
  (スコア最高のカードが優先 → 古いカードは "in-window" になっても次点で弾かれる)
- 弾かれたカードは window=240 内に別の coincident time が来ないまま archive_max_age 超過 → time_expired

### Noisy resurface
両 window とも noisy rate = 0.4%（ほぼ同一）。
スコア 0.60 未満の低品質 resurface は発生しにくい設計。

## 判定

**推奨: window=120 (現状維持)**

window=240 への拡張は **7 日間高トラフィックシミュレーションで効果ゼロ**。

ボトルネックは window の長さではなく **LCM(batch_interval=30, cadence=45)=90 min** の
coincident-time 密度。window を伸ばしても coincident time の数は増えない。

### window 拡張が有効になる条件
- cadence を短縮（例: cadence=30 にすると LCM=30、full-coincidence）
- 同 family の複数カードを 1 review で複数 resurface 可能にする
- batch_interval を cadence と揃える

## アーティファクト

| ファイル | 内容 |
|---------|------|
| window_comparison.json | window=120/240 の比較メトリクス (詳細) |
| pool_size_trajectory.csv | 時系列アーカイブプールサイズ (両 window) |
| run_config.json | 実験設定 |
