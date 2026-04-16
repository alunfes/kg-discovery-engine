# Run 028 詳細分析レポート — Push-based Surfacing + Archive Policy

**作成日**: 2026-04-16  
**対象**: `run_028_push_surfacing` (2026-04-15 実行)  
**目的**: 他AIによる分析のための包括的技術レポート

---

## 1. 実験の背景と目的

### Run 027 からの流れ

Run 027 (charming-burnell) は delivery-layer の固定ポーリングカデンスを最適化する実験だった。
Run 027 の最終結論（`crypto/artifacts/runs/run_027_delivery/delivery_policy_recommendation.md`）:

| 指標 | cadence=30min | cadence=45min | cadence=60min | cadence=120min |
|------|--------------|--------------|--------------|---------------|
| stale_rate | 0.065 | 0.210 | 0.9025 | 1.0 |
| precision | 1.000 | 0.560 | 0.000 | 0.000 |
| reviews/day | 48 | 32 | 24 | — |
| items/review (collapsed) | 4.85 | 4.85 | 4.85 | 1.75 |

**Run 027 の結論**:
- cadence=30min: quality-optimum (stale=6.5%, precision=1.0) だが 48 reviews/day で重すぎる
- cadence=45min: pragmatic pick (32 reviews/day, precision=0.56)
- cadence=60min: precision=0.0（HL=40min の actionable_watch カードがレビュー時点で全て aging 化）
- ファミリー崩壊により 76% 削減: 20 items → 4.85 items/review
- Run 027 の推奨: 「push-only が実現すれば 30min cadence が viable」

### Run 028 の目的

Run 027 で示された課題を解決する:

**目標**: 30min クオリティ（precision~1.0, stale<10%）を <20 reviews/day で実現する

具体的な検証内容:
1. Push-based surfacing vs 45min poll（現行 pragmatic pick）
2. Card archive policy: expired→archived ライフサイクル + 再浮上メカニズム
3. Operator burden score（reviews/day × avg items/review）
4. False-negative risk（push フィルタで critical カードを見逃すリスク）

**重要**: Run 028 は delivery-layer のみの実験。コアスコアリングと half-life キャリブレーションは変更なし。

---

## 2. 実装設計詳細

### 2.1 Push Trigger Engine (`crypto/src/eval/push_surfacing.py`)

#### 4つの Signal Types

**T1 — High-conviction fresh card**

```python
HIGH_CONVICTION_THRESHOLD: float = 0.74
HIGH_PRIORITY_TIERS: frozenset[str] = frozenset(["actionable_watch", "research_priority"])
```

- **条件**: 新着バッチの中に `tier ∈ {actionable_watch, research_priority}` かつ `composite_score ≥ 0.74` のカードが存在
- **評価対象**: INCOMING バッチのみ（デッキ全体ではない）
- **設計理由**: デッキワイドで評価すると、以前のプッシュでレビュー済みの fresh カード（HL=40min なら 20min 間 fresh を維持）で再トリガーされる。incoming-only にすることで各 high-conviction カードは到着バッチ時に最大1回だけトリガー可能

**T2 — Fresh-card count threshold**

```python
FRESH_COUNT_THRESHOLD: int = 3
```

- **条件**: 新着バッチ内の high-priority カード数 ≥ threshold
- **評価対象**: INCOMING バッチのみ
- **設計理由**: デッキワイドで評価すると、前バッチの累積 fresh カードが常に閾値を超えるため毎バッチで発火してしまう。incoming-only で「このバッチはレビューに値するほど活発か？」を正確に判定

**T3 — Aging last-chance** ⚠️ **実装バグあり（後述）**

```python
LAST_CHANCE_LOOKAHEAD_MIN: float = 10.0
```

- **条件**: aging 状態のカードが digest_only 遷移まで ≤ 10分
- **評価対象**: デッキ全体（aging リスクは新着と無関係）
- **設計理由**: aging カードがオペレーターに見られずに digest_only に移行するのを防ぐ。絶対時間（10min）を使う理由: HL=40min なら 10min = 0.25 ratio units（meaningful）、HL=90min なら 0.11 units（小さい）。絶対時間の方が tier に依存しない一貫した緊急度信号を提供

**No-trigger（抑制）条件**

```python
MIN_PUSH_GAP_MIN: float = 15.0
```

| 条件 | 説明 |
|------|------|
| S1 | デッキ内にアクション可能カードが存在しない（全て digest_only/expired/archived） |
| S2 | fresh カードが全て低優先度 OR 既にファミリー崩壊済み（unique info なし） |
| S3 | 直前のプッシュから < MIN_PUSH_GAP_MIN (15min) — バースト防止レート制限 |

#### PushFilter の仕組み

`PushSurfacingEngine.evaluate()` の評価順序:

1. incoming バッチで T1, T2 チェック; デッキ全体で T3 チェック
2. いずれかが該当 → triggers リストに追加
3. triggers が空 → `suppressed=True, reason="no trigger condition met"`
4. S1 チェック → 該当なら suppressed
5. S2 チェック → 該当なら suppressed
6. S3 レート制限チェック → 直前プッシュからの経過時間が min_push_gap 未満なら suppressed
7. 全て通過 → プッシュ発火、`_last_push_time` 更新

### 2.2 Archive Policy State Machine (`crypto/src/eval/delivery_state.py`)

#### 6状態のライフサイクル

| 状態 | 条件（age/HL 比） | 実際の時間（HL=40min） | オペレーター表示 |
|------|-----------------|---------------------|----------------|
| fresh | ratio < 0.5 | age < 20min | あり（優先） |
| active | 0.5 ≤ ratio < 1.0 | 20-40min | あり（通常） |
| aging | 1.0 ≤ ratio < 1.75 | 40-70min | あり（最終確認） |
| digest_only | 1.75 ≤ ratio < 2.5 | 70-100min | ダイジェストのみ |
| expired | ratio ≥ 2.5 | age ≥ 100min | なし |
| **archived** | age_min ≥ 5.0 × HL | age ≥ 200min | なし（クエリ可） |

#### 遷移ルール（`ArchiveManager` クラス）

**expired → archived**
- 条件: `age_min >= _ARCHIVE_RATIO × half_life_min` （`_ARCHIVE_RATIO = 5.0`）
- HL=40min の場合: age ≥ 200min
- 効果: `archived_at_min` フィールドに現在時刻をセット; stale_count 分母から除外
- 設計理由: 2.5×（expiry閾値）に 2.0× バッファ = 5.0×、HL=40min の actionable_watch ティアに対して 200min（全取引セッション分）をカバー

**archived → fresh（再浮上）**
- 条件: 同じ `(branch, grammar_family)` を持つ新規カードが `resurface_window_min`（デフォルト: 120min）以内に到着
- 効果: アーカイブ済みカードのクローンを fresh（age_min=0）として注入; `resurface_count += 1`
- 実装: `new_card_id = f"{src.card_id}_rs{resurface_count + 1}"` でクローン識別
- 設計理由: card_id 整合性保持; 再浮上は新しいシグナルイベント

**archived → deleted（ハード削除）**
- 条件: `current_time - archived_at >= archive_max_age_min`（デフォルト: 480min = 8時間）
- 効果: プールから完全削除; 再浮上不可
- 設計理由: 1取引セッション（8h）が自然な保持ホライゾン

#### ArchiveManager 設計の決定

`ArchiveManager` を `DeliveryStateEngine` と分離した理由:
- `DeliveryStateEngine`: stateless（各レビュー時点のスナップショットモデル）
- `ArchiveManager`: stateful（どのファミリーが最近アーカイブされたかを記憶）
- 分離により、既存の first_review / batch_refresh シミュレーションを変更なしに archive semantics を opt-in 可能

---

## 3. 実験パラメータ（全値）

### 共通設定（全3回実行）

```json
{
  "run_id": "run_028_push_surfacing",
  "seeds": [42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61],
  "cadences_poll": [30, 45, 60],
  "session_hours": 8,
  "batch_interval_min": 30,
  "n_cards": 20,
  "hot_batch_probability": 0.30
}
```

### Push Threshold Sweep 設定

| Label | high_conviction_threshold | fresh_count_threshold | min_push_gap_min |
|-------|--------------------------|----------------------|-----------------|
| default | 0.74 | 3 | 15.0 |
| sensitive | 0.70 | 2 | 10.0 |
| conservative | 0.80 | 5 | 20.0 |

### Archive Policy 設定（比較用3種）

| Label | resurface_window_min | archive_max_age_min |
|-------|---------------------|-------------------|
| tight | 60 | 240 (4h) |
| **standard** | **120** | **480 (8h)** |
| loose | 180 | 720 (12h) |

### Archive デフォルト値

```json
{
  "archive_ratio": 5.0,
  "resurface_window_min": 120,
  "archive_max_age_min": 480
}
```

### Hot Batch モデルの詳細

```python
HOT_BATCH_PROB = 0.30  # 30% of batches are "active regime"

# Hot batch: n_batch = 20, standard tier weights
# Quiet batch: n_batch = choices([0, 1, 2, 3, 4], weights=[3, 3, 2, 1, 1])
#   expected n = 0×0.3 + 1×0.3 + 2×0.2 + 3×0.1 + 4×0.1 = 1.3 cards avg
```

設計根拠: 実際の crypto 市場では ~70% の 30min ウィンドウにアクション可能な変化がない（ベースライン振動）。genuine regime activity は ~30% 程度。

---

## 4. 実験結果の生データ

### 4.1 3回の実行サマリー

Run 028 は同日（2026-04-15）に3回実行された。各回はコードの段階的修正を反映している。

| 実行 | タイムスタンプ | push_default reviews/day | 判定 |
|------|-------------|--------------------------|------|
| Run 1 | 20260415T143315 | **51.0** | FAIL |
| Run 2 | 20260415T143933 | **50.85** | FAIL |
| **Run 3 (正規)** | **20260415T144118** | **18.45** | **PASS** |

### 4.2 正規結果（Run 3: 20260415T144118）

#### Push vs Poll 比較（`push_vs_poll_comparison.csv`）

| approach | reviews_per_day | avg_stale_rate | avg_precision | avg_surfaced_after | avg_archived | missed_critical | model |
|----------|----------------|---------------|--------------|-------------------|--------------|-----------------|-------|
| poll_30min | 48.0 | 0.065 | 1.0 | 4.85 | 0.0 | n/a | poll_first_review |
| poll_45min | 32.0 | 0.21 | 0.56 | 4.85 | 0.0 | n/a | poll_first_review |
| poll_60min | 24.0 | 0.9025 | 0.0 | 4.85 | 0.0 | n/a | poll_first_review |
| poll_30min_archive | 48.0 | 0.6397 | 0.76 | 5.0 | 41.97 | n/a | poll_batch_archive |
| poll_45min_archive | 32.0 | 0.6457 | 0.666 | 5.0 | 36.72 | n/a | poll_batch_archive |
| poll_60min_archive | 24.0 | 0.6695 | 0.7475 | 5.0 | 46.84 | n/a | poll_batch_archive |
| **push_default** | **18.45** | n/a | trigger-only | 23.87 | n/a | **0** | push |
| push_sensitive | 19.05 | n/a | trigger-only | 23.5 | n/a | 0 | push |
| push_conservative | 16.95 | n/a | trigger-only | 25.05 | n/a | 0 | push |

#### Trigger Threshold Analysis（Run 3）

| Config | T1 score≥ | T2 count≥ | Gap min | Reviews/day | Missed critical | T1 events | T2 events | T3 events |
|--------|-----------|-----------|---------|-------------|----------------|-----------|-----------|-----------|
| default | 0.74 | 3 | 15.0 | **18.45** | 0 | 123 | 107 | **0** |
| sensitive | 0.70 | 2 | 10.0 | **19.05** | 0 | 127 | 109 | **0** |
| conservative | 0.80 | 5 | 20.0 | **16.95** | 0 | 107 | 106 | **0** |

#### Operator Burden Comparison（Run 3）

| Approach | Reviews/day | Items/review (報告値) | Burden score（報告値） | Stale rate | Precision |
|----------|------------|---------------------|----------------------|------------|-----------|
| poll_30min | 48.0 | 4.85 | 232.8 | 0.065 | 1.0 |
| poll_45min | 32.0 | 4.85 | 155.2 | 0.21 | 0.56 |
| poll_60min | 24.0 | 4.85 | 116.4 | 0.9025 | 0.0 |
| push_default | 18.45 | **23.87** | **440.5** | n/a | ~1.0 |

**注意**: push の items/review (23.87) は pre-collapse 値（後述の問題分析参照）

#### Poll Baseline Cadence（`poll_baseline_cadence.csv`）

| cadence_min | n_reviews | avg_stale_rate | avg_surfaced_before | avg_surfaced_after | avg_reduction | avg_precision | avg_info_loss |
|------------|-----------|---------------|--------------------|--------------------|--------------|--------------|--------------|
| 30 | 1 | 0.065 | 20.0 | 4.85 | 15.15 | 1.0 | 0.6848 |
| 45 | 1 | 0.21 | 18.7 | 4.85 | 13.85 | 0.56 | 0.6838 |
| 60 | 1 | 0.9025 | 18.7 | 4.85 | 13.85 | 0.0 | 0.6838 |

### 4.3 失敗した実行（Run 1, Run 2）の生データ

#### Run 1（20260415T143315）— push_vs_poll_comparison.csv

| approach | reviews_per_day | avg_stale_rate | avg_precision | avg_surfaced_after |
|----------|----------------|---------------|--------------|-------------------|
| poll_30min | 48.0 | 0.065 | 1.0 | 4.85 |
| poll_45min | 32.0 | 0.21 | 0.56 | 4.85 |
| poll_60min | 24.0 | 0.9025 | 0.0 | 4.85 |
| poll_30min_archive | 48.0 | **0.9324** | **0.0625** | 1.52 |
| poll_45min_archive | 32.0 | **0.9183** | **0.043** | 1.44 |
| poll_60min_archive | 24.0 | **0.9855** | **0.0** | 1.19 |
| push_default | **51.0** | n/a | trigger-only | 40.36 |
| push_sensitive | **51.0** | n/a | trigger-only | 40.36 |
| push_conservative | **51.0** | n/a | trigger-only | 40.36 |

Trigger分析（Run 1）: `default: T1=340, T2=340, T3=0 | sensitive: T1=340, T2=340, T3=0 | conservative: T1=320, T2=340, T3=0`

#### Run 2（20260415T143933）— push_vs_poll_comparison.csv

| approach | reviews_per_day | avg_surfaced_after |
|----------|----------------|-------------------|
| poll_30min_archive | 48.0 | 0.6397 (stale) / 0.76 (prec) |
| push_default | **50.85** | 42.68 |
| push_sensitive | **50.85** | 42.68 |
| push_conservative | **50.85** | 42.68 |

Trigger分析（Run 2）: `default: T1=285, T2=339, T3=0 | sensitive: T1=302, T2=339, T3=0 | conservative: T1=205, T2=339, T3=0`

### 4.4 Run 027 参照データ（比較用）

Run 027 cadence_comparison.csv (first_review / batch_refresh 両モデル):

| cadence | fr_stale | fr_prec | fr_surfaced_after | br_stale | br_prec | br_surfaced_after |
|---------|----------|---------|-------------------|----------|---------|-------------------|
| 30 | 0.065 | 1.0 | 4.85 | 0.9324 | 0.0625 | 1.52 |
| 45 | 0.21 | 0.56 | 4.85 | 0.9183 | 0.043 | 1.44 |
| 60 | 0.9025 | 0.0 | 4.85 | 0.9855 | 0.0 | 1.19 |
| 120 | 1.0 | 0.0 | 1.75 | 1.0 | 0.0 | 1.12 |

---

## 5. 成功基準と達成/未達の判定

### 設計上の成功基準（`final_delivery_recommendation.md` より）

| 基準 | 目標値 | 測定結果（Run 3 default config） | 判定 |
|------|--------|-------------------------------|------|
| Push reviews/day | < 20 | **18.45** | ✅ PASS |
| Missed critical | 0（5日間 shadow） | **0** | ✅ PASS |
| Operator burden score | ≤ 50% of 45min-poll（≤77.6） | **440.5**（報告値） / **~105.7**（修正値） | ⚠️ 要確認 |
| Archive re-surface rate | > 0 | **未測定** | ❓ UNKNOWN |

### 各成功基準の詳細評価

**reviews/day < 20 [PASS]**
- default: 18.45（目標の 7.75% 余裕）
- sensitive: 19.05（目標の 4.75% 余裕）
- conservative: 16.95（目標の 15.25% 余裕）
- Run 027 pragmatic pick（45min, 32回/day）比: **42.3% 削減**

**Missed critical = 0 [PASS]**
- 3 config 全て 0
- 全 20 seed で 0（シード間のばらつきなし）

**Operator burden ≤ 77.6 [要精査]**

報告値の問題（後述の問題分析 §6.2 参照）:
- 報告された push burden: 440.5 → 45min-poll(155.2) の 284%（FAIL に見える）
- 修正後の推定値: 18.45 reviews × (23.87 × 0.24) items = 18.45 × 5.73 = **105.7**
- 修正値での判定: 105.7 / 155.2 = **68.1%** → 50% 基準にはまだ未達
- ただし正確な post-collapse deck size の計測が必要

**Archive re-surface rate > 0 [UNKNOWN]**
- push シミュレーションに `ArchiveManager` が統合されていない
- `poll_batch_archive` シミュレーションでは archive_count=41.97/36.72 と記録されているが、push 試行での re-surface カウントは存在しない

---

## 6. 失敗分析

### 6.1 Run 1 の失敗原因：all-hot simulation バグ

**症状**: 全 3 config が完全に同一の結果（51.0 reviews/day、T2=340イベント）

**根本原因**: Run 1 の `run_config.json` に `hot_batch_probability` フィールドが存在しない。
コードには `HOT_BATCH_PROB = 0.30` と定義されているが、Run 1 実行時のコードでは
おそらく hot/quiet batch の切り替えロジックが未実装または未適用だった。

**証拠**:
- T2=340 events / 20 seeds = 17 events/seed = 8h×60/30min + 1 = 全バッチ数
- つまり T2 が全バッチで発火 → 全バッチが hot（20 cards × 全て high-priority）
- poll_archive の stale rate が異常に高い（0.9324 vs Run 3 の 0.6397）

**効果**: hot batch のみでは市場の 70% 静穏期間が再現されず、reviews/day が現実より 2.8× 過大評価

### 6.2 Operator Burden 報告値のバグ（全実行共通）

**症状**: `push_default` の items/review が 23.87（Run 3）と表示されるが、
これは pre-collapse 値であり、post-collapse 値ではない

**コード箇所** (`run_028_push_surfacing.py` L293-297):

```python
COLLAPSE_FACTOR = 0.24  # from Run 027: 20→4.8 items (76% reduction)
push_items_pre = push_result.avg_fresh_at_trigger + push_result.avg_active_at_trigger
push_items_collapsed = push_items_pre * COLLAPSE_FACTOR
push_burden = push_result.reviews_per_day * push_items_collapsed
```

計算上は `push_items_collapsed = 23.87 × 0.24 = 5.73` になるはず。
しかし報告テーブルには `avg_items_per_review = 23.87` と表示されている。

**問題の所在**: `push_result.avg_fresh_at_trigger + push_result.avg_active_at_trigger = 23.87/0.24 = 99.4`
という数値が `default_push_result` から返されている可能性。これは `generate_cards` 関数が
複数バッチの累積デッキ状態を `avg_fresh_at_trigger` として返しているためと考えられる。

**正確な push burden の推定**:
- avg_fresh_at_trigger: ~20（current hot batch の fresh cards）
- avg_active_at_trigger: ~4（直前バッチの残 active cards）
- pre-collapse: ~24 items
- post-collapse（×0.24）: ~5.76 items
- burst = 18.45 × 5.76 = **106.3** → 45min-poll(155.2) の **68.4%**

→ 成功基準の「≤50%」にはまだ未達だが、poll との比較で **33%の改善**

### 6.3 T3 トリガーの実装バグ（全実行共通）

**症状**: T3（aging last-chance）イベントが全実行・全 config で 0

**根本原因**: T3 チェックに論理的矛盾がある

`_check_t3` の実装（`push_surfacing.py` L258-263）:

```python
if c.delivery_state() != STATE_AGING:
    continue
# Time until card crosses into digest_only
digest_crossover_min = _DIGEST_MAX * c.half_life_min  # ← BUG
time_remaining = digest_crossover_min - c.age_min
if 0 < time_remaining <= self.last_chance_lookahead_min:
    last_chance.append(c)
```

**問題**: `_DIGEST_MAX = 2.5`、`_AGING_MAX = 1.75`

HL=40min の場合:
- STATE_AGING の範囲: `age_min ∈ [40, 70)` min（ratio 1.0〜1.75）
- T3 の最後チャンス条件: `age_min ≥ _DIGEST_MAX × HL - 10 = 100 - 10 = 90` min

これらの範囲は**重なりがない** → T3 は物理的に発火不可能

**正しい実装**:
```python
# AGING → DIGEST_ONLY の遷移点 = _AGING_MAX × half_life_min
digest_crossover_min = _AGING_MAX * c.half_life_min  # 1.75 × HL = 70min for HL=40
time_remaining = digest_crossover_min - c.age_min
# T3 fires when age_min ∈ [60, 70) for HL=40min (10min lookahead)
```

**影響評価**: T3 は T1/T2 が到達しないカードをカバーするための safety net。
T3 なしでも Run 3 では missed_critical=0 を達成したが、これは T1/T2 が十分カバーできている現状に依存している。
本番環境でのエッジケース（T1/T2 が発火せず、カードが静かに aging → digest_only に移行するケース）で
critical カードを見逃すリスクが残る。

### 6.4 poll_batch_archive モデルの stale rate 問題

**症状**: archive 付き poll の stale rate が異常に高い（0.64-0.99 vs first-review model の 0.065-0.90）

**Run 3 データ**:
- poll_30min（first_review）: stale=0.065, precision=1.0
- poll_30min_archive（batch_refresh）: stale=0.6397, precision=0.76

**分析**: batch_refresh モデルは異なる前提（定常状態の連続バッチ更新）で動作するため、
single-review の first_review モデルとは直接比較できない。archive 付きで stale rate が
高くなるのは、アーカイブ済みカードが stale_count の分母から除外された結果、
残りの非アーカイブカードの stale 比率が上昇するためと考えられる。

→ この数値は「archive によって stale が悪化」ではなく「分母の定義が変わった」効果

### 6.5 Threshold Sweep の無効化（Run 1 & Run 2）

**症状**: Run 1 では全 config が同一（51.0）、Run 2 では T2 が全 config で 339 events と同一

**Run 2 の詳細分析**:
- conservative config は T2 threshold=5 にもかかわらず T2=339（全バッチ）
- default (threshold=3): T2=339、sensitive (threshold=2): T2=339、conservative (threshold=5): T2=339

**原因仮説**: hot batch 20 cards では high-priority tier が threshold=5 を超えるカードを
常に生成している。または、T2 が incoming のみでなく deck-wide で評価されていた
（コード更新前のバグ）。Run 3 では T2 events に差異（107/109/106）が現れており、修正済み。

---

## 7. Run 029 への具体的な改善案

### 優先度 HIGH

**[Fix-1] T3 実装バグの修正**

ファイル: `crypto/src/eval/push_surfacing.py` L258

```python
# Before (BUG):
digest_crossover_min = _DIGEST_MAX * c.half_life_min

# After (FIX):
digest_crossover_min = _AGING_MAX * c.half_life_min
```

テスト追加:
```python
# HL=40 でのT3発火検証
# age_min=65 (aging状態) で T3 が発火することを確認
# age_min=75 (digest_only状態) で T3 が発火しないことを確認
```

**[Fix-2] Operator Burden の post-collapse 計算修正**

`compute_operator_burden` 関数の `avg_items_per_review` を正確な post-collapse 値に修正。
`avg_fresh_at_trigger + avg_active_at_trigger` の内訳を別途計測し、
family collapse factor を正確に適用する必要がある。

**[Fix-3] Archive re-surface の push シミュレーション統合**

`simulate_push_surfacing` に `ArchiveManager` を組み込み、
`total_resurfaced` メトリクスを `PushSurfacingResult` に追加。
成功基準「archive re-surface rate > 0」を定量的に検証できるようにする。

### 優先度 MEDIUM

**[Exp-1] hot_batch_probability 感度分析**

目標: 0.20 / 0.30 / 0.40 / 0.50 での reviews/day, missed_critical を計測
- Run 3 は 0.30 で目標達成したが、市場状況が活発化（0.50+）した場合のロバスト性未確認
- expected: 0.50 で ~30 reviews/day（目標超過）となる閾値付近を特定

**[Exp-2] Archive re-surface 効果の定量評価**

tight/standard/loose 3種の archive config で re-surface rate を計測し、
「standard を推奨」の根拠を数値化する。

**[Exp-3] Precision 定義の統一**

- push の precision: "trigger-only"（質的定義、プッシュが発火した＝genuine signal）
- poll の precision: `fresh+active cards / all surfaced cards`（量的定義）

これらは異なる定義であり、直接比較できない。Run 029 では push precision も
`fired_events の fresh+active count / fired_events の total deck count` として
量的に計測することを検討。

### 優先度 LOW

**[Exp-4] Shadow テストの実装**

Final recommendation に記載された shadow フェーズ（push と poll を並走させ、
push イベントが 30min poll の高品質スナップショットと相関するかを検証）の
シミュレーション実装。

**[Exp-5] T3 修正後の missed_critical 再評価**

T3 修正後、missed_critical=0 が維持されるか検証。T3 fix により
一部の suppression 条件が変化する可能性があり、S3 rate limit との相互作用を確認。

---

## 8. 技術的アーキテクチャノート（他AI向け）

### モジュール関係図

```
run_028_push_surfacing.py  ← メインオーケストレーター
    ├── delivery_state.py   ← DeliveryCard, ArchiveManager, DeliveryStateEngine
    │   ├── generate_cards()          ← シンセティックデータ生成
    │   ├── run_multi_cadence()       ← poll baseline (first_review model)
    │   ├── simulate_batch_refresh()  ← poll batch model (no archive)
    │   └── simulate_batch_refresh_with_archive()  ← poll + archive model
    └── push_surfacing.py   ← PushSurfacingEngine, simulate_push_surfacing
        ├── PushSurfacingEngine.evaluate()  ← T1/T2/T3/S1/S2/S3 評価
        └── run_push_multi_seed()           ← multi-seed averaging
```

### 重要な定数一覧

| 定数 | 値 | 所在 | 意味 |
|------|----|------|------|
| `_FRESH_MAX` | 0.5 | delivery_state.py | fresh → active の age/HL 比閾値 |
| `_ACTIVE_MAX` | 1.0 | delivery_state.py | active → aging の閾値 |
| `_AGING_MAX` | 1.75 | delivery_state.py | aging → digest_only の閾値 |
| `_DIGEST_MAX` | 2.5 | delivery_state.py | digest_only → expired の閾値 |
| `_ARCHIVE_RATIO` | 5.0 | delivery_state.py | expired → archived の閾値（×HL） |
| `HIGH_CONVICTION_THRESHOLD` | 0.74 | push_surfacing.py | T1 score 閾値 |
| `FRESH_COUNT_THRESHOLD` | 3 | push_surfacing.py | T2 count 閾値（default） |
| `LAST_CHANCE_LOOKAHEAD_MIN` | 10.0 | push_surfacing.py | T3 lookahead 時間（分） |
| `MIN_PUSH_GAP_MIN` | 15.0 | push_surfacing.py | S3 rate limit（分） |
| `COLLAPSE_FACTOR` | 0.24 | run_028 script | Run 027 ファミリー崩壊率（4.85/20） |
| `HOT_BATCH_PROB` | 0.30 | run_028 script | active regime バッチの割合 |

### 実験的有効性の評価

Run 028 の最終有効実行（Run 3）は以下の点で科学的に有効:

1. **再現性**: seeds 42-61（20 seeds）で平均化、決定論的実行（seed 固定）
2. **比較設計**: poll baseline（Run 027 参照点）と push を同一シミュレーション環境で比較
3. **パラメータ sweep**: 3種の threshold config で感度を評価

限界:
1. **T3 バグ**: aging last-chance トリガーが全て発火していない（設計の一部が未検証）
2. **Archive 統合**: push シミュレーションに archive lifecycle が未統合
3. **hot_batch_probability の感度**: 0.30 での検証のみ（市場状況変化への頑健性未確認）
4. **Precision 定義の不整合**: push と poll で異なる precision の定義を使用

---

## 9. 推奨生産設定（Run 3 最終成果物より）

```json
{
  "delivery_mode": "push",
  "push_triggers": {
    "T1_high_conviction_threshold": 0.74,
    "T1_high_priority_tiers": ["actionable_watch", "research_priority"],
    "T2_fresh_count_threshold": 3,
    "T3_last_chance_lookahead_min": 10.0,
    "rate_limit_gap_min": 15.0
  },
  "archive_policy": {
    "archive_ratio_hl": 5.0,
    "resurface_window_min": 120,
    "archive_max_age_min": 480
  },
  "family_collapse": {
    "enabled": true,
    "min_family_size": 2
  },
  "baseline_fallback_cadence_min": 45
}
```

**注意**: T3 バグを修正するまでは `T3_last_chance_lookahead_min` は事実上機能していない。

---

## 10. ファイル索引

| ファイル | 説明 |
|---------|------|
| `crypto/run_028_push_surfacing.py` | 実験オーケストレーター |
| `crypto/src/eval/push_surfacing.py` | Push trigger engine（T1/T2/T3/S1/S2/S3） |
| `crypto/src/eval/delivery_state.py` | 6状態ライフサイクル + ArchiveManager |
| `crypto/artifacts/runs/20260415T143315_*/` | Run 1（失敗: all-hot bug） |
| `crypto/artifacts/runs/20260415T143933_*/` | Run 2（失敗: threshold sweep 無効） |
| `crypto/artifacts/runs/20260415T144118_*/` | **Run 3（正規結果）** |
| `crypto/artifacts/runs/run_027_delivery/` | Run 027 参照データ |

各アーティファクトディレクトリに含まれるファイル:
- `run_config.json` — 実験設定
- `push_vs_poll_comparison.csv` — 主要比較データ
- `trigger_threshold_analysis.md` — threshold sweep 結果
- `operator_burden_comparison.md` — 負荷スコア比較
- `archive_policy_spec.md` — archive state machine 仕様
- `final_delivery_recommendation.md` — 最終推奨設定
- `poll_baseline_cadence.csv` — poll baseline 詳細

---

*このレポートは Run 028 の全アーティファクトを読み込んで生成した包括的分析です。*  
*正規結果: `20260415T144118_run_028_push_surfacing/`*  
*生成: 2026-04-16*
