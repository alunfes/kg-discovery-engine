# Sprint T — Diminishing-Returns Factor for Batch-Live Fusion

## Objective

Prevent score saturation in the batch-live fusion adjudication layer
(introduced in Run 019) while preserving useful reinforcement signal.

Run 019 observed: all 10 batch cards reached `composite_score = 1.0` after 47
live events, collapsing rank spread to zero.  This made the fusion output
unactionable — every card was tied at maximum confidence.

---

## Root Cause

`_apply_reinforce` applied a flat delta of `0.07 × severity` on every call with
no diminishing-returns factor:

```python
# Run 019 (before Sprint T)
delta = round(0.07 * event.severity, 4)
new_score = round(min(1.0, score_b + delta), 4)
```

With 47 replay events per card (all `spread_widening` / `book_thinning` at
severity ≈ 0.4–0.5) this totals ≈ 1.3–1.6 points added, far exceeding the
[0, 1] range.  The `min(1.0, …)` cap merely determines *when* saturation is
reached, not *whether* it occurs.

---

## Mechanism Implemented (Sprint T)

Four inter-layered controls added to `_apply_reinforce`:

### 1. Novel Evidence Bonus
First time an event type (`event.event_type`) is seen on a card → full credit
(`decay = 1.0`).  Preserves initial signal diversity regardless of future decay.

### 2. Same-Family Count Decay
Cumulative count of prior reinforcements of the same event type controls the
decay coefficient:

| Occurrence | Decay Coefficient |
|---|---|
| 1st (novel) | 1.0 (via novel path) |
| 2nd | 0.7 |
| 3rd | 0.5 |
| 4th+ | 0.3 |

Rationale: the 5th `spread_widening` in a row adds less information than the
1st.  A stepwise function avoids continuous-decay complexity while being
interpretable.

### 3. Time-Window Deduplication
If the same event type fires again within **5 minutes** (300,000 ms) of the
previous reinforcement, `decay = 0.3` regardless of count.  This suppresses
microstructure bursts that fire many identical events in rapid succession.

Priority order: novel → time-window → count decay.

### 4. Ceiling Brake
When `composite_score > 0.9`, any computed decay is multiplied by **0.2x**:

```python
if score > 0.9:
    decay *= 0.2
```

This creates a soft barrier near the maximum without a hard ceiling, preserving
rank ordering among near-maximum cards.

---

## Implementation Details

### New constants (`fusion.py`)

```python
_DECAY_COEFFICIENTS: tuple[float, ...] = (1.0, 0.7, 0.5, 0.3)
_TIME_WINDOW_MS: int = 5 * 60 * 1_000
_TIME_WINDOW_CREDIT: float = 0.3
_CEILING_BRAKE_THRESHOLD: float = 0.9
_CEILING_BRAKE_FACTOR: float = 0.2
```

### New fields on `FusionCard`

```python
reinforce_counts: dict[str, int]     # per-event-type reinforcement count
last_reinforce_ts: dict[str, int]    # last reinforcement timestamp per type
seen_event_types: set[str]           # event types ever applied as reinforce
```

State is read **before** mutation so a novel event is not penalised against
itself.

### New helper functions

- `_compute_decay_factor(card, event) → float` — computes the decay multiplier
- `_apply_ceiling_brake(decay, score) → float` — applies the ceiling brake

### Updated `_apply_reinforce`

```python
decay = _compute_decay_factor(card, event)
decay = _apply_ceiling_brake(decay, score_b)
delta = round(0.07 * event.severity * decay, 4)
```

Promote, contradict, expire_faster, and no_effect rules are **unchanged**.

---

## Before / After Comparison (seed=42, 47 events)

| Metric | Run 019 (no decay) | Sprint T (decay) |
|---|---|---|
| Cards at score=1.0 | **10 / 10** | **0 / 10** |
| Rank spread (max − min) | 0.0000 | 0.0537 |
| Top-3 score gap | 0.0000 | 0.0388 |
| Promotions | 6 | **6 (retained)** |
| Reinforcements | 94 | 94 |

Score distribution (Sprint T, descending):

```
0.9613 · 0.9447 · 0.9225 · 0.9225 · 0.9194 · 0.9194 · 0.9128 · 0.9128 · 0.9128 · 0.9076
```

Cards cluster in the **0.907–0.961** range — well-reinforced but not saturated,
with meaningful rank spread.

---

## Promotion Retention

All 6 `research_priority → actionable_watch` promotions observed in Run 019 are
retained in Sprint T.  The promote rule uses `_apply_promote` which adds a flat
+0.05 unconditionally and does not pass through `_apply_reinforce`.  Promotion
eligibility (`severity >= 0.6 AND tier < actionable_watch`) is unchanged.

---

## Test Coverage (27 tests in `test_sprint_t.py`)

| Class | Tests |
|---|---|
| `TestComputeDecayFactor` | Novel, 2nd/3rd/4th+ count decay, time-window, priority, cross-type independence |
| `TestApplyCeilingBrake` | Below/at/above threshold, full-credit case |
| `TestApplyReinforceDecay` | Novel, 70% 2nd event, time-window, ceiling brake, state update, reason string, cap |
| `TestConsecutiveDecay` | 10-event no-saturation, monotone coefficients, cross-type novel |
| `TestPromotionRetention` | Promote unaffected, tracking state not updated, 6-promotion simulation |
| `TestRegressionOtherRules` | contradict, expire_faster, no_effect unchanged |

---

## Artifacts

- `crypto/artifacts/runs/sprint_t_fusion_decay/run_config.json`
- `crypto/artifacts/runs/sprint_t_fusion_decay/before_after_score_distribution.csv`
- `crypto/artifacts/runs/sprint_t_fusion_decay/saturation_reduction.md`
- `crypto/artifacts/runs/sprint_t_fusion_decay/promotion_retention.md`
- `crypto/artifacts/runs/sprint_t_fusion_decay/recommended_decay_rule.md`

---

## Design Decisions

**Why count-based decay instead of `delta × (1 − score)`?**

`delta × (1 − score)` (asymptotic approach) was considered but rejected:
- Score converges to 1.0 asymptotically — saturation is delayed, not prevented
- The convergence point depends on the geometric series sum, which varies with
  event severity and count in non-obvious ways
- Count-based decay is interpretable: "the 3rd event of this type gives 50%
  credit"

**Why 5-minute window?**

5 minutes matches the typical microstructure burst duration for HYPE spread
events in the 30-minute replay.  Most `spread_widening` clusters fire within
1–2 minutes then cease.

**Why not deduplicate to 0.0 (skip)?**

A burst of identical events may still capture different microstructure
snapshots (different order book depths, different OI levels).  0.3 credit
acknowledges partial confirmation while preventing flooding.

---

## Next Actions

1. **Multi-asset batch expansion** — all batch cards are HYPE; expand to
   BTC/ETH/SOL to exercise contradict/expire_faster in shadow mode.
2. **OI direction fallback** — classify `oi_change` as `reinforce` when
   `metadata["direction"]` is absent.
3. **Time-window tuning** — for live production (faster event cadence),
   consider lowering window to 2 minutes.
