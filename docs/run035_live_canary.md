# Run 035: 7-Day Live Canary — Global Fallback Cadence Baseline

## Summary

7-day push+fallback simulation establishing the **global fallback_cadence_min = 45**
baseline.  Measures reviews/day, fallback activations, missed_critical, operator
burden, and family coverage across a synthetic week spanning quiet, transition,
and hot regime days.

**Verdict: system viable at cadence=45.  Quiet days carry disproportionate
fallback burden (avg 9 fallbacks/day vs 2.8 for hot/transition). No safety
events observed. Baseline handed to Run 036 for regime-aware tuning.**

---

## Configuration

| Parameter | Value |
|-----------|-------|
| Policy | global (fixed cadence) |
| fallback_cadence_min | 45 |
| Simulation window | 8h/day active trading |
| Days | 7 (seeds 42–48) |
| Quiet threshold | hot_prob ≤ 0.25 |
| Push surfacing | ON (immediate review on high-conviction card) |
| Half-life: push cards | 30 min |
| Half-life: important cards | 40 min |
| Half-life: normal cards | 70 min |

### 7-Day Regime Profile

| Day | Seed | hot_prob | Regime |
|-----|------|----------|--------|
| 1   | 42   | 0.08     | quiet |
| 2   | 43   | 0.13     | quiet |
| 3   | 44   | 0.42     | transition |
| 4   | 45   | 0.58     | transition |
| 5   | 46   | 0.71     | transition |
| 6   | 47   | 0.83     | hot |
| 7   | 48   | 0.92     | hot |

---

## Day-by-Day Results

| Day | Regime     | hot_prob | Reviews | Fallbacks | Push Rev | Missed | Burden |
|-----|------------|----------|---------|-----------|----------|--------|--------|
| 1   | quiet      | 0.08     | 11      | 10        | 1        | 0      | 23.0   |
| 2   | quiet      | 0.13     | 11      | 8         | 3        | 0      | 27.0   |
| 3   | transition | 0.42     | 24      | 2         | 22       | 0      | 75.0   |
| 4   | transition | 0.58     | 16      | 5         | 11       | 0      | 66.0   |
| 5   | transition | 0.71     | 18      | 5         | 13       | 0      | 75.0   |
| 6   | hot        | 0.83     | 33      | 1         | 32       | 0      | 125.0  |
| 7   | hot        | 0.92     | 35      | 1         | 34       | 0      | 131.0  |

---

## Aggregate Summary

| Metric | Value |
|--------|-------|
| Total reviews (7 days) | 148 |
| Total fallback activations | 32 |
| Total missed_critical | **0** |
| Total operator burden | 522.0 |
| Avg reviews/day | 21.14 |
| Avg fallbacks/day | 4.57 |

## Regime Breakdown

| Regime | Days | Avg Reviews/day | Avg Fallbacks/day | Avg Burden/day |
|--------|------|-----------------|-------------------|----------------|
| quiet | 2 | 11.0 | **9.0** | 25.0 |
| hot/transition | 5 | 25.2 | 2.8 | 94.4 |

---

## Key Observations

### 1. Quiet-day fallback dominance
On quiet days, push events are rare (1–3/day).  The 45-min scheduled fallback
fires 8–10 times per day, accounting for 73–91% of all reviews.  Operators on
quiet days are primarily responding to the clock, not to live signals.

### 2. Hot/transition days are push-driven
On hot/transition days, push events fire 11–34 times/day.  The fallback clock
rarely fires (1–5 times/day).  The cadence setting is largely irrelevant here —
push surfacing dominates.

### 3. Safety is intact
missed_critical = 0 across all 7 days.  Push surfacing guarantees that
high-conviction cards are reviewed immediately (age = 0 at first review).
Important cards (HL = 40 min) are always reviewed within cadence_min = 45 < 2×40 = 80.

### 4. Family coverage is complete
All 4 grammar families (positioning_unwind, beta_reversion, flow_continuation,
baseline) are surfaced on every day of the simulation.

---

## Baseline Numbers for Run 036

| Metric | Baseline (global 45) |
|--------|---------------------|
| Quiet-day avg fallbacks | **9.0 / day** |
| Quiet-day avg reviews | **11.0 / day** |
| Hot/transition fallbacks | 2.8 / day |
| Total fallbacks (7-day) | **32** |
| Total missed_critical | **0** |

Run 036 targets: fallback reduction on quiet days with missed_critical unchanged.

---

## Artifacts

| File | Description |
|------|-------------|
| `day_by_day.csv` | Per-day metrics |
| `summary.json` | Aggregate statistics |
| `review_memo.md` | Extended review notes |
| `run_config.json` | Experiment configuration |

Artifacts: `crypto/artifacts/runs/20260416_run035_live_canary/`
