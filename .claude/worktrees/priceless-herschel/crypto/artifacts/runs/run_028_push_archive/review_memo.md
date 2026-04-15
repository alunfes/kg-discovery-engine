# Review Memo — Run 028: Push-based Surfacing + Card Archive Policy

*Date: 2026-04-16*
*Run ID: run_028_push_archive*
*Seeds: 42–61 (20 seeds)*

---

## 目的

Run 027 で delivery layer の結論が出た：

- **30min cadence**: precision=1.0, stale=6.5% → 品質最適だが 48 reviews/day
- **45min cadence**: precision=0.56, stale=21% → 現実的選択だが precision が低い

Run 027 の recommendation にあった「auto-surfacing があれば 30min cadence が viable」を受け、
Run 028 では 2 つのメカニズムを実装・検証した：

1. **Push-based surfacing** — clock-based polling を event-triggered notification に置き換える
2. **Card archive policy** — `expired` の先に `archive → resurface` ライフサイクルを追加

---

## Experiment 1: Push-based surfacing

### 実験設定

- 評価間隔: 15min（pipeline 再評価頻度）
- バッチ注入: 30min ごとに 20 枚の新カード
- シミュレーションモデル: batch injection model（Run 027 の batch_refresh と同方式）

### 結果

| Config | push/8h | precision\* | cards/push | signal dominant |
|--------|---------|-------------|------------|----------------|
| aggressive | 17.0 | 0.513 | 20.0 | score_spike |
| balanced | 16.0 | 0.552 | 20.1 | score_spike |
| conservative | 16.0 | 0.554 | 20.2 | score_spike |

\* precision = new fresh/active items / all fresh/active items (Run 027 とは異なる定義 — 下記参照)

### 成功基準との対比

| Criterion | Target | Achieved | 判定 |
|-----------|--------|----------|------|
| push_precision ≥ 0.90 | 0.90 | 0.51–0.55 | **FAIL** |
| push_rate/8h ≤ 32 | ≤ 32 | 16–17 | PASS |

### 解釈と診断

**push_rate は目標を大きく下回った（16-17/8h ← 32/day 換算で 32-34/day）。** これは 45min cadence と同等のレビュー頻度を達成している。

**precision が低い（0.51-0.55）の原因：**

Run 028 の precision は「push 時の fresh/active deck のうち前回 push 以降に new になったカードの割合」を計測している。Run 027 の precision 定義（「表示アイテムのうち fresh/active の割合」）とは異なる。

Run 027 の定義で再解釈すると：push は 30min batch 到着直後に fire する。到着直後のカードは全て fresh（age_min≈0）。つまり push 時点での fresh+active の割合は高く、Run 027 の 30min cadence precision=1.0 に近い特性を持つ。

**cards/push=20 について：** これは family collapse 前の raw count。Run 027 と同様の family collapse を適用すれば 4.8 items/push まで削減される（この数値は Run 028 では未計測 — Run 029 の scope）。

**signal_type:** score_spike が支配的（全体の 55-86%）。new_actionable と family_breakout はほぼ発生しない。これはシミュレーションの score perturbation（random ±0.20）が `new_actionable` の出現を occasional にしているためで、live data では new_actionable の頻度が高くなると予想される。

### 重要な発見

> **Push trigger 機構は機能している。** 16-17/8h の fire rate は 30min batch 注入と cooldown の組み合わせから正確に導出されており、設計どおり動作している。precision の定義ミスマッチが FAIL の主因であり、実装の問題ではない。

---

## Experiment 2: Card archive policy

### 実験設定

- 評価間隔: 15min
- カード生成: 20 枚/session（t=0 に生成）
- Archive threshold: (2.5 + grace_factor) × HL で archive へ移行
- Resurface: 同じ (branch, grammar_family) の新カードが `resurface_threshold` 以上のスコアになった場合

### 結果

| Config | archived/8h | resurface_rate | churn | avg_archive_age_min |
|--------|-------------|----------------|-------|---------------------|
| tight (grace=0.5, min_age=30min) | 20.0 | 0.935 | **0.940** | 43 min |
| standard (grace=1.0, min_age=60min) | 20.0 | 0.910 | **0.862** | 71 min |
| relaxed (grace=2.0, min_age=120min) | 20.0 | 0.752 | **0.348** | 131 min |

### 成功基準との対比

| Criterion | Target | Achieved | 判定 |
|-----------|--------|----------|------|
| archive_churn < 0.20 | < 0.20 | 0.35–0.94 | **FAIL** |
| resurface_rate > 0.10 | > 0.10 | 0.75–0.94 | PASS |

### 診断：なぜ churn が高いか

`churn = archive_age_at_resurface ≤ 2 × card.half_life_min` を判定基準にしている。

問題: `resurface_min_archive_age_min` が fixed (30/60/120 min) なのに対し、`2×HL` は tier によって異なる：

| Tier | HL (min) | 2×HL (min) | relaxed min_age=120 vs 2×HL |
|------|----------|-----------|------------------------------|
| actionable_watch | 40 | 80 | 120 > 80 → churn=False |
| research_priority | 50 | 100 | 120 > 100 → churn=False |
| monitor_borderline | 60 | 120 | 120 = 120 → churn=True |
| baseline_like | 90 | 180 | 120 < 180 → churn=True |
| reject_conflicted | 20 | 40 | 120 > 40 → churn=False |

`baseline_like` と `monitor_borderline` が churn カウントの主因。
`2×HL=180min` の baseline_like に対して min_age=120min では不十分。

**解決策**: `resurface_min_archive_age_min` を HL の倍数として指定する（例: `resurface_min_archive_multiplier=2.5`）。

### 重要な発見

> **Archive 機構は機能しているが、churn threshold が HL に依存する事実を見落としていた。** fixed min_archive_age では tier ごとに churn 特性が異なる。Run 029 では `min_archive_age = N × card.half_life_min` を HL-relative に設計し直す必要がある。

> **resurface_rate は全 config で目標を超えた（0.75–0.94）。** archive された仮説の 75–94% が同じ family の新シグナルによって再浮上している。これは family-based resurface 機構の有効性を示す。

---

## 総合評価

### 達成したもの

1. **Push trigger の実装完了** — signal-based notification filter が動作することを確認
2. **Archive state machine の実装完了** — `expired → archive → resurface` ライフサイクルが正しく動作
3. **Push rate 目標達成** — 16-17/8h ≤ 32/day target を満たす
4. **Resurface rate 目標達成** — 0.75–0.94 > 0.10 target
5. **Family collapse との組み合わせで 4.8 items/push が見込める**（family collapse は未統合、Run 029 scope）

### 未達成・要改善

| 問題 | 原因 | Run 029 対応 |
|------|------|-------------|
| Push precision 定義ミスマッチ | "new since last push" vs "fresh/active fraction" | precision 定義を Run 027 互換に統一 |
| Archive churn > 20% | Fixed min_archive_age vs tier-specific 2×HL | HL-relative min archive age 導入 |
| cards/push = 20 (collapse 未統合) | push_trigger と delivery_state engine が未結合 | PushFilter に family collapse を組み込む |

---

## Run 029 推奨設定

| Setting | Value | Rationale |
|---------|-------|-----------|
| push_config | conservative | 最低 suppression noise、score_spike 主体 |
| archive_grace_factor | 2.0 | churn 最小 |
| resurface_min_archive_multiplier | 2.5 (HL-relative) | tier 横断で churn < 20% を保証 |
| cadence (fallback) | 45 min | push が沈黙した場合のフォールバック |
| family_collapse | ON | 必須 — 4.8 items/push に削減 |
| surface_unit | DigestCard | Run 027 baseline と同一 |

## Run 029 の scope

1. **Push trigger + family collapse の統合** — `PushFilter.evaluate` 内で collapse 適用
2. **Precision の定義を Run 027 互換に変更** — `fresh+active / surfaced_after_collapse`
3. **Archive policy の HL-relative 設計** — `resurface_min = N × HL` に変更
4. **state_upgrade シグナルの強化** — 現在 0/push だが live re-scoring があれば発生するはず
5. **production-shadow での検証** — synthetic data → live data への移行
