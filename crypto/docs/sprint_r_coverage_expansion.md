# Sprint R: Real-Data Coverage Expansion

## Objective

Extend the Run 017 single-snapshot shadow deployment to a multi-window real-data
pipeline that can detect grammar families beyond `beta_reversion`. Run 017 produced
only `cross_asset` and `beta_reversion` cards because three data gaps prevented
other families from firing.

## Coverage Gaps Fixed in Sprint R

### Gap 1: Funding History Too Short (0 epochs → 21 epochs)

**Root cause:** `fetch_funding` used a default of 10 epochs (80h lookback). The
Hyperliquid API returned 0 records in the Run 017 window, so z-scores were always
0.0 and `funding_extreme` never fired.

**Fix:** Extended default lookback to `max(n_epochs * 8h, lookback_days * 24h)` with
`lookback_days=7` (7 days = 21 funding epochs). New cache key prefix `funding7d_`
to avoid collisions with old 80h cache.

**Impact:** `FundingState.z_score` now computes against 21 real epochs. Combined with
the absolute-rate fallback (see threshold adjustments), `FUNDING_EXTREME_LONG/SHORT`
regimes can now fire.

### Gap 2: OI Flat Series (0 accumulation signal → volume proxy)

**Root cause:** `_ctx_to_oi_samples` generated a constant OI series from a single
snapshot. `build_streak` was always 0 → `is_accumulation=False` → `positioning_unwind`
and `one_sided_position` nodes never fired.

**Fix:** Added volume-based OI proxy in `RealDataAdapter._ctx_to_oi_samples`. For each
candle, excess volume above the window mean drives a small cumulative OI adjustment
(scale=0.001). This introduces realistic variability without synthetic inflation.

**Impact:** When candles show sustained volume buildup, `oi_change_pct` varies and
`is_accumulation=True` can fire with the real-data threshold (0.5%).

### Gap 3: Aggression States Capped (buy_ratio = 0.65 → magnitude-scaled)

**Root cause:** `_infer_buy_ratio` returned fixed values (0.65 up / 0.35 down)
regardless of move magnitude. `BUY_STRONG=0.70` was never exceeded → `is_burst=False`
for all candle-derived ticks → `flow_continuation` and E1 transient-aggression chains
couldn't fire.

**Fix:** Magnitude-scaled mapping in `_infer_buy_ratio`:
- Δ > 0.5% → 0.80 (STRONG_BUY → `is_burst=True`)
- Δ > 0.01% → 0.62 (MODERATE_BUY)
- Δ < -0.5% → 0.20 (STRONG_SELL → `is_burst=True`)
- Δ < -0.01% → 0.38 (MODERATE_SELL)

**Impact:** 0.5%+ crypto 1-min moves (common in active trading) now generate
`AggressionBias.STRONG_BUY/STRONG_SELL` states, enabling `flow_continuation` and
transient_aggression chains.

### Gap 4: Book Snapshot Parse Errors (all MISS)

**Root cause:** `_parse_book` only handled one response shape. Certain Hyperliquid
responses have `levels` with list-of-list format instead of list-of-dict.

**Fix:** Updated `_parse_book` to handle both dict format (`{px, sz}`) and list format
(`[price, size]`), plus list-wrapped responses.

**Impact:** Book availability improves for assets with non-standard response formats.

## Real-Data Threshold Adjustments

All adjustments are gated behind `real_data_mode=True` to preserve backward
compatibility with synthetic data tests.

| Threshold | Synthetic Value | Real-Data Value | Rationale |
|-----------|----------------|-----------------|-----------|
| `FUNDING_Z_WINDOW` | 10 | 5 (`FUNDING_Z_WINDOW_REAL`) | Shorter window for z-score usability with limited real history |
| `FUNDING_ABS_EXTREME` | N/A | 0.0003 | Absolute rate fallback when history < 5 epochs |
| `OI_BUILD_RATE` | 0.05 (5%) | 0.005 (0.5%) (`OI_BUILD_RATE_REAL`) | Real OI changes 0.1-1% per 20-min window |

These are applied in `extract_states(real_data_mode=True)` via `PipelineConfig.real_data_mode=True`.

## Multi-Window Architecture

```
MultiWindowFetcher
├── Window 1h  (60 min,  6 funding epochs)
├── Window 4h  (240 min, 15 funding epochs)
├── Window 8h  (480 min, 21 funding epochs)
└── Window 7d  (10080 min, 21 funding epochs)
```

Each window fetches fresh candles; book/ctx are fetched once and shared.

### Why These Windows

| Window | Primary Benefit |
|--------|----------------|
| 1h | High-frequency aggression, spread patterns, fast momentum |
| 4h | Intraday correlation breaks, 4h trend alignment |
| 8h | One full funding epoch — funding z-score becomes meaningful |
| 7d | Full funding cycle — reliable `funding_extreme` detection |

## Coverage Tracker Output

Four artifacts written to `crypto/artifacts/runs/sprint_r_coverage/`:

| File | Content |
|------|---------|
| `family_coverage.csv` | Fire count per (window, family) |
| `regime_coverage.csv` | Observation count per (window, regime) |
| `missing_condition_map.md` | Absent families/regimes + root-cause analysis |
| `recommended_state_expansions.md` | Next state/detector additions for Sprint S |

## Offline Baseline Run Results

The offline run (no live API calls, using empty cache) establishes a degenerate
baseline that confirms the infrastructure works:

| Window | Cards | Families | Regimes |
|--------|-------|----------|---------|
| 1h | 18 | cross_asset | (none — no candle data) |
| 4h | 18 | cross_asset | (none) |
| 8h | 18 | cross_asset | (none) |
| 7d | 18 | cross_asset | (none) |

**Why cross_asset fires without data:** The cross_asset KG builder generates 6 asset
pairs × 3 branches = 18 baseline cards even with empty state collections (it uses asset
identity, not price data, for the correlation pair structure).

**Why beta_reversion absent (vs Run 017):** Run 017 had 121 candles in cache at the
Run 017 cache path. The Sprint R cache path is fresh. With live data, beta_reversion
will reappear alongside new families.

## Live Data Expected Coverage (vs Run 017)

| Family | Run 017 | Sprint R Live (expected) |
|--------|---------|--------------------------|
| beta_reversion | ✓ (10 cards) | ✓ (all windows) |
| cross_asset | ✗ | ✓ (18/window baseline) |
| positioning_unwind | ✗ | ✓ (8h/7d windows with funding) |
| flow_continuation | ✗ | ✓ (when 0.5%+ candles present) |
| baseline | ✗ | ✓ (fallback when no conflict) |

## New Files

| File | Purpose |
|------|---------|
| `crypto/src/ingestion/multi_window_fetcher.py` | Fetches data for 4 time windows |
| `crypto/src/coverage_tracker.py` | Aggregates coverage across windows |
| `crypto/run_sprint_r_coverage.py` | Multi-window pipeline runner |
| `crypto/tests/test_sprint_r.py` | 18 new tests for Sprint R changes |

## Modified Files

| File | Change |
|------|--------|
| `crypto/src/ingestion/hyperliquid_connector.py` | `fetch_funding` 7-day lookback, book parse fix |
| `crypto/src/ingestion/data_adapter.py` | Magnitude-scaled `_infer_buy_ratio`, OI volume proxy |
| `crypto/src/states/extractor.py` | `real_data_mode` flag, `FUNDING_Z_WINDOW_REAL`, `OI_BUILD_RATE_REAL` |
| `crypto/src/pipeline.py` | `PipelineConfig.real_data_mode` field |

## Running Sprint R

```bash
# Live data (recommended):
python -m crypto.run_sprint_r_coverage

# Offline test (uses API cache):
python -m crypto.run_sprint_r_coverage --offline

# Custom output:
python -m crypto.run_sprint_r_coverage --output-dir /tmp/sprint_r
```

## Next Steps (Sprint S)

1. **WebSocket trade feed** — real fill-level trades → reliable STRONG_BUY/STRONG_SELL
2. **OI WebSocket** — continuous OI time-series → ground-truth `is_accumulation`
3. **L2 book WebSocket** — rolling spread z-score → `SPREAD_WIDENING` regime
4. **Threshold calibration pass** — run 7-day live data, plot regime distribution,
   calibrate `CORR_BREAK_THRESHOLD` and `FUNDING_ABS_EXTREME` against actual values

See `recommended_state_expansions.md` in the artifacts for full detail.
