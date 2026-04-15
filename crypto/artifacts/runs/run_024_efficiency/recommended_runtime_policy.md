# Run 024: Recommended Runtime Policy

## Adaptive Efficiency Knobs — Production Deployment

### Trigger

Evaluate per monitoring window (≈ 120 min). Classify regime by n_live_events in window:

| Regime | n_live_events | Monitoring HL | batch_live_ratio | bg_density |
|--------|--------------|--------------|------------------|------------|
| sparse | < 90 | ×1.30 (extend +30%) | 0.20 (batch heavy) | thin |
| calm | 90–110 | ×0.80 (compress -20%) | 0.50 (balanced) | medium |
| event-heavy | > 110 | ×1.00 (no change) | 0.80 (live heavy) | thick |

### Family Priority Adjustment (event-heavy only)

| Family | Delta |
|--------|-------|
| positioning_unwind | -0.05 |
| beta_reversion | +0.05 |
| flow_continuation | 0.00 |
| baseline | 0.00 |

### Safety Invariants (never adjust)

- hit_rate logic and thresholds
- HL effectiveness determination
- active_ratio constraints and promote rules

### Rollback

Set monitoring_budget_multiplier=1.0, batch_live_ratio=0.5, background_watch_density='medium', family_weight_shift={all: 0.0}.
This restores Run 022 / Sprint T global defaults.

### Evidence

- Run 022 (longitudinal): 10-window stability, CV(promotions)=0.087
- Run 023 (recalibration): regime slices show safety=1.0 everywhere;
  efficiency drift in sparse (+327% TTO) and calm (-65.6% TTO) regimes
- Run 024 (this run): before/after simulation confirms knobs improve
  resource utilization without touching safety metrics

