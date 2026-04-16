# Production-Shadow Playbook

*Validated stack version: run034 (2026-04-16)*

This playbook is the operator-facing guide for daily use of the
production-shadow monitoring engine.  It covers the daily run procedure,
what outputs to review, when to activate fallback mode, and which metrics
signal stack degradation.

---

## 1. Daily Run Procedure

### Prerequisites

- shogun VPS accessible (test: `ssh -o ConnectTimeout=10 shogun echo ok`)
- Python 3.11+ in environment (`python --version`)
- Repo up to date (`git pull origin main`)

### Step-by-step

```bash
# 1. Navigate to the repo
cd ~/claude-dev/kg-discovery-engine

# 2. Run the production-shadow pipeline (standard push mode)
python -m crypto.run_production_shadow \
    --config crypto/artifacts/runs/20260416T120000_run034_packaging/recommended_config.json \
    --output-dir crypto/artifacts/runs/$(date +%Y%m%dT%H%M%S)_daily \
    --assets HYPE BTC ETH SOL

# 3. Open the daily summary
cat crypto/artifacts/runs/<today_timestamp>_daily/daily_summary.md
```

If the live connector is unavailable, run in synthetic fallback mode:

```bash
python -m crypto.run_production_shadow \
    --config crypto/artifacts/runs/20260416T120000_run034_packaging/recommended_config.json \
    --output-dir crypto/artifacts/runs/$(date +%Y%m%dT%H%M%S)_daily_synthetic \
    --assets HYPE BTC ETH SOL \
    --synthetic --seed 42
```

---

## 2. What Outputs to Check

After each run, review the following in order of priority:

### 2.1 Cards surfaced (`cards_surfaced.json`)

```
Key fields per card:
  card_id          — unique identifier
  tier             — actionable_watch | research_priority | monitor_borderline
  composite_score  — 0.0–1.0 (higher = stronger signal)
  grammar_family   — positioning_unwind | beta_reversion | flow_continuation | baseline
  asset            — HYPE | BTC | ETH | SOL
  branch           — hypothesis branch identifier
  age_min          — how old the card is at review time
  delivery_state   — fresh | active | aging
  push_trigger     — T1 | T2 | poll_fallback
```

**Act on**:
- `actionable_watch` cards with `composite_score ≥ 0.74` (T1 triggers)
- Any `research_priority` card regardless of score
- Cards in `aging` state — fewer minutes remain before digest_only

**Monitor only**:
- `monitor_borderline` cards
- Cards with `delivery_state = active` and `composite_score < 0.74`

### 2.2 Family digest (`family_digest.md`)

Shows collapsed cards grouped by `(branch, grammar_family)`.  When a family
has ≥ 2 cards (S2 suppression threshold), only the highest-scoring card is
shown with a count of collapsed duplicates.

Check:
- Which families are active today
- Whether any family is generating > 10 cards/window (high-cadence pair flag)
- Whether promotions are concentrated in one family (concentration risk)

### 2.3 Push event log (`push_events.csv`)

```
Fields: timestamp_min, trigger_type, trigger_detail, fresh_count,
        active_count, suppressed, suppress_reason
```

Check:
- `trigger_type` distribution (T1 vs T2 vs poll_fallback)
- `suppressed` rate — high suppression rate is healthy (S1/S2/S3 working)
- Any `suppress_reason = S3` entries at < 15 min gaps (rate limit firing)

### 2.4 Promotion / contradiction log (`fusion_events.csv`)

```
Fields: card_id, event_type, rule, score_delta, new_tier
  event_type: promote | reinforce | contradict | expire_faster
```

Check:
- `contradict` count — any contradiction is notable; review the card and
  the opposing live event that triggered it
- `promote` count — 7–8/window is normal (run_022 baseline)
- Zero `promote` across an entire day: pipeline may not be receiving events

### 2.5 Monitoring metrics (`monitoring_metrics.json`)

```json
{
  "reviews_today": ...,
  "reviews_per_day_rate": ...,
  "missed_critical": ...,
  "stale_rate": ...,
  "fallback_poll_count": ...,
  "fallback_poll_pct": ...
}
```

Compare against guardrail thresholds (see Section 4).

---

## 3. When to Use Fallback Poll Mode

The `poll_45min` fallback fires automatically when no push event has occurred
in the preceding 45 minutes.  This is **expected and healthy** behaviour — it
means the market has been quiet and T1/T2 triggers did not fire.

### Normal fallback (no action needed)

- Market is in sparse/quiet regime (no strong signals)
- Fallback fires 30–50% of reviews in a session
- Cards at review are digest-level or aging — operator confirms no action needed

### Elevated fallback (investigate)

- Fallback fires > 60% of reviews across two or more consecutive days
- This may mean:
  1. T1 threshold is too conservative for current market conditions
  2. Live data feed has reduced signal quality (funding gap, OI flat)
  3. Push engine misconfiguration

**Investigation steps:**
```bash
# Check if T1 cards are being generated but filtered
grep "high_conviction_threshold" crypto/artifacts/runs/<today>_daily/push_events.csv

# Check incoming card quality
cat crypto/artifacts/runs/<today>_daily/cards_surfaced.json \
    | python -c "import json,sys; cards=json.load(sys.stdin);
      print('mean_score:', sum(c['composite_score'] for c in cards)/len(cards))"
```

If mean incoming score drops below 0.60 (well below T1 threshold of 0.74),
the data feed may be degraded.  Switch to synthetic mode and compare.

### Force poll mode (temporary override)

To disable push and run pure 45min poll for a session:

```bash
python -m crypto.run_production_shadow \
    --config crypto/artifacts/runs/20260416T120000_run034_packaging/recommended_config.json \
    --force-poll-cadence 45 \
    --output-dir crypto/artifacts/runs/$(date +%Y%m%dT%H%M%S)_poll_override
```

Use this when:
- Debugging push trigger logic
- Comparing push vs poll on the same market window
- Initial shadow phase on a new data source

---

## 4. Metrics That Indicate Degradation

### Tier 1 — Immediate action required

| Metric | Threshold | Action |
|--------|-----------|--------|
| `missed_critical` | ≥ 1 | Stop and debug push trigger. Switch to poll_30min immediately. |
| `reviews_per_day_rate` | > 35 | Engine is spamming. Raise T1 threshold to 0.80, T2 count to 5. |
| `stale_rate` | > 0.30 at 45min fallback | Half-life / review cadence mismatch. Shorten cadence to 30min. |

### Tier 2 — Monitor and investigate

| Metric | Threshold | Likely Cause |
|--------|-----------|-------------|
| `reviews_per_day_rate` | > 25 | T1 threshold too low or market abnormally active |
| `fallback_poll_pct` | > 60% sustained | Signal quality degraded or T1/T2 thresholds miscalibrated |
| `promote` count | 0 for full day | Live event stream not reaching the fusion engine |
| `contradict` count | > 5/day | Regime flip or real opposing signal — review all contradicted cards |
| Family concentration > 95% | (one family dominates) | Synthetic-like condition; real data may not yet be producing variety |

### Tier 3 — Log and track

| Metric | Threshold | Notes |
|--------|-----------|-------|
| Archive resurface rate | 0 over 5 days | Expected if no recurring patterns yet; watch trend |
| S3 suppression rate | > 40% | Push gap too short; consider raising `min_gap_min` to 20 |
| `positioning_unwind×HYPE` recurrence | 100% of sessions | Pair-level suppression may be needed (see known_limits.md) |

### Summary: degradation checklist (run at end of each week)

```
□ missed_critical == 0 (every session this week)
□ reviews/day mean < 25
□ stale_rate mean < 0.15 at poll_45min check
□ at least 1 promote event per day
□ family mix includes at least 2 distinct families over the week
□ fallback_pct < 50% average
```

If ≥ 2 boxes are unchecked, file a calibration review before the next week.

---

## 5. Quick Reference Card

```
Trigger  What it means                    Normal rate
-------  -------------------------------- -----------
T1       High-score card arrived          3–6 / session
T2       Batch had ≥ 3 quality cards     2–5 / session
poll     45min elapsed, no push yet       5–12 / session (quiet market)

Suppress Reason                          Health signal
-------  -------------------------------- -----------
S1       No actionable cards              OK — quiet window
S2       All collapsed into digest        OK — low-diversity batch
S3       Rate-limited (< 15min gap)       OK up to 40%

Card tier        Act?    Half-life (default)
actionable_watch YES     40 min
research_priority YES    50 min
monitor_borderline NO    60 min
```

---

## 6. Configuration Reference

Canonical config: `crypto/artifacts/runs/20260416T120000_run034_packaging/recommended_config.json`

Key parameters to change for common situations:

| Situation | Parameter | Default | Change to |
|-----------|-----------|---------|-----------|
| Too many reviews/day | `T1.score_threshold` | 0.74 | 0.80 |
| Missing signals | `T1.score_threshold` | 0.74 | 0.70 |
| Large deck per review | `T2.fresh_count_threshold` | 3 | 5 |
| Burst push events | `S3.min_gap_min` | 15 | 20 |
| Persistent stale cards | `delivery.half_life_min` (per tier) | 40/50/60 | +20 each |
| Coverage gaps | `fallback_poll.cadence_min` | 45 | 30 |
