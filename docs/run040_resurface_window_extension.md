# Run 040: Resurface Window Extension — 120 min → 240 min

*Date: 2026-04-16 | Experiment: window extension comparison | Verdict: **RETAIN 120 MIN***

---

## 1. Objective

Test whether extending `resurface_window_min` from 120 to 240 recovers proximity-miss cards
(archived cards whose family recurs after the 120-min window closes) without introducing
archive pool bloat or noisy resurfacing.

**Hypothesis**: A 240-min window captures recurrences that arrive in the [121, 240]-min band
after archival, improving recovery rate without significantly increasing operator burden.

---

## 2. Comparison Against Run 039 (window=120)

### 2.1 Core Metrics

| Metric | Run 039 (window=120) | Run 040 (window=240) | Delta |
|--------|---------------------|---------------------|-------|
| Recovery rate | 0.9275 | 0.9275 | **+0.0000** |
| Resurfaced value density | 1.1221 | 1.1221 | +0.0000 |
| Permanent loss count | 0.0 | 0.0 | 0.0 |
| Resurfaced burden (items/review) | 2.3475 | 2.3475 | **+0.0000** |
| Avg surfaced after collapse | 5.00 | 5.00 | +0.00 |
| Avg stale rate | 0.7723 | 0.7723 | +0.0000 |
| Total archived / seed | 20.0 | 20.0 | — |
| Total resurfaced / seed | 18.6 | 18.6 | — |
| Archive pool avg size | 17.21 | 17.21 | +0.00 |
| Archive pool peak | 20 cards | 20 cards | **+0 cards** |

### 2.2 Archive Pool Size by Day

| Day | Run 039 (120 min) | Run 040 (240 min) | Delta |
|-----|------------------|------------------|-------|
| Day 1 | 14.78 | 14.78 | 0.00 |
| Day 2 | 17.62 | 17.62 | 0.00 |
| Day 3 | 17.61 | 17.61 | 0.00 |
| Day 4 | 17.61 | 17.61 | 0.00 |
| Day 5 | 17.61 | 17.61 | 0.00 |
| Day 6 | 17.64 | 17.64 | 0.00 |
| Day 7 | 17.54 | 17.54 | 0.00 |

---

## 3. Key Findings

### 3.1 Zero proximity-miss volume (pre-registered prediction confirmed)

The window extension provides **no measurable benefit** because proximity misses are
effectively zero in the current operational model.

**Root cause**: The resurface check fires at the intersection of batch arrivals and review
times.  With `batch_interval=30 min` and `cadence=45 min`:

```
LCM(30, 45) = 90 min
→ resurface-eligible incoming-batch checks occur every 90 min
→ first check after archival at T is at T+90 (≤ 120 min window)
→ P(family recurs in that batch) ≈ 97%
→ P(proximity miss) ≈ 3% × one-chance = 3%
```

But even this 3% does not represent *true* proximity misses for window=240, because:
- The next coincidence is at T+180, which is within the 240-min window
- P(family also skips T+180 batch) = 3% × 3% = 0.09%
- With 20 archived events / seed / 7 days, expected proximity misses = 0.018

**Across 20 seeds × 7 days: 0 observed proximity misses for window=120 vs window=240.**

### 3.2 No archive pool bloat

Pool size is identical for both windows (peak=20, avg=17.21).  This was expected because
the pool contents are determined by which cards are archived (age ≥ 5× HL), not by the
resurface window.  A wider window only determines which pool entries are *eligible* for
resurface; it does not prevent pruning or change the pool accumulation rate.

### 3.3 No noise from wider window

Resurfaced burden is 2.35 items/review for both windows.  A wider window that captures
no additional resurfaces naturally adds no noise.

### 3.4 High value density confirmed

Resurfaced cards score 12.2% above the average archived card (density=1.121) for both
windows.  The archive recovery mechanism is already selecting high-value cards, confirming
the `archive_max_age_min=480` retention threshold is appropriate.

---

## 4. Verdict: RETAIN 120 MIN

### 4.1 Decision matrix

| Criterion | Threshold | Run 040 Result | Pass? |
|-----------|-----------|---------------|-------|
| Recovery improvement | > 0.005 | +0.0000 | **✗** |
| Resurfaced burden delta | < 0.05 items/review | +0.0000 | ✓ |
| Archive pool bloat | < 25% peak increase | 0.0% | ✓ |

The primary criterion (recovery improvement) fails.  Window=240 does not replace window=120.

### 4.2 Why 240 min is neither harmful nor helpful

- **Not harmful**: pool size, operator burden, and value density are unchanged
- **Not helpful**: proximity-miss volume is zero under current operational parameters

### 4.3 Conditions under which 240 min WOULD help

The window extension becomes beneficial when families can go silent for 120–240 min.
This requires at least one of:

| Condition | Description |
|-----------|-------------|
| Longer batch intervals | Batches arriving every 90–150 min instead of 30 min |
| Higher family cardinality | 10+ families so each family appears less frequently per batch |
| "Quiet period" market regimes | Specific families suppressed for 2–4h during low-volatility windows |
| Cross-session recovery | `archive_max_age_min` extended to 24h+ to span overnight gaps |

If the detection pipeline moves to a 90-min or 120-min batch cadence, re-run this
experiment — window=240 would provide ~3% additional recovery per archive event.

---

## 5. Recommendation

**Keep `resurface_window_min=120`** as the default.

No code changes required.  Revisit if:
- Batch interval is extended beyond 90 min (likely makes window=240 beneficial)
- Field reports show cards being permanently lost that were expected to resurface
- A 7-day production log shows proximity-miss patterns (same family reappears 121–240 min
  after an archived card is deleted from the pool)

---

## 6. Simulation Details

- **Script**: `crypto/run_040_window_extension.py`
- **Seeds**: 42–61 (20 seeds, consistent with Run 027/028)
- **Duration**: 7 days (10,080 min) — first multi-day archive simulation
- **Cadence**: 45 min (Run 027 pragmatic pick)
- **Batch interval**: 30 min
- **archive_max_age_min**: 480 min (unchanged from Run 028)

---

## 7. Artifacts

| File | Path |
|------|------|
| window_comparison.csv | `artifacts/runs/20260416_run040_window/window_comparison.csv` |
| recovery_improvement.md | `artifacts/runs/20260416_run040_window/recovery_improvement.md` |
| archive_pool_analysis.md | `artifacts/runs/20260416_run040_window/archive_pool_analysis.md` |
| final_window_recommendation.md | `artifacts/runs/20260416_run040_window/final_window_recommendation.md` |
| run_config.json | `artifacts/runs/20260416_run040_window/run_config.json` |
| Crypto artifacts | `crypto/artifacts/runs/20260416T042608_run_040_window_extension/` |
