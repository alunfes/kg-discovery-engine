# Run 042 Review Memo — Structural Loss Characterization
*Date: 2026-04-16 | Seed: 42 | Session: 168h (7 days)*

## 実験目的

archive_max_age=480min での永続損失を家族×レジーム軸で分解し、
MITIGATE（延長で回収可能）と ACCEPT（構造的損失）に分類する。

## 結果サマリ

| 指標 | 値 |
|------|---|
| 総生成カード数 | 2783 |
| 総アーカイブ数 | 2675 |
| 回収数 | 275 |
| 回収率 | 10.3% |
| 永続損失合計 | 2400 |
| └ time_expired | 161 |
| └ proximity_miss | 2239 |
| **MITIGATE** | **15** |
| ACCEPT | 2385 |

## MITIGATE 分類の根拠

対象: time_expired かつ grammar_family ∈ ['cross_asset', 'reversion']
かつ regime_at_archive ∈ ['active', 'calm']

これらのカードは calm/active レジームで cross_asset または reversion 家族の
シグナルが 480min 超のギャップを持つことで archive pool から削除される。
archive_max_age を 720min に延長することで同家族の次シグナルが到達するまで
pool に保持できる。

## MITIGATE ケース一覧

| card_id | family | regime | archived_at | score |
|---------|--------|--------|-------------|-------|
| 360_c005 | reversion | calm | 3570 | 0.6509 |
| 367_c012 | reversion | calm | 3570 | 0.6403 |
| 310_c000 | reversion | calm | 3600 | 0.4775 |
| 387_c012 | reversion | calm | 3600 | 0.6699 |
| 388_c013 | reversion | calm | 3600 | 0.6163 |
| 710_c000 | cross_asset | calm | 5100 | 0.4756 |
| 735_c018 | cross_asset | calm | 5130 | 0.7640 |
| 797_c015 | cross_asset | calm | 5130 | 0.4943 |
| 729_c012 | cross_asset | calm | 5160 | 0.6542 |
| 765_c004 | cross_asset | calm | 5160 | 0.7969 |
| 786_c004 | cross_asset | calm | 5220 | 0.8911 |
| 776_c015 | cross_asset | calm | 5250 | 0.7206 |
| 810_c008 | cross_asset | calm | 5250 | 0.9293 |
| 799_c017 | cross_asset | calm | 5265 | 0.6854 |
| 800_c018 | cross_asset | calm | 5265 | 0.7142 |

## 次アクション

Run 043: cross_asset + reversion 家族を calm/active レジームで
archive_max_age 480→720 に延長し、これら MITIGATE ケースが回収されるか検証。
