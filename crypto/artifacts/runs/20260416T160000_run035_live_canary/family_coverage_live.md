# Family Coverage — Run 035 Live Canary

Simulated 20 seeds × 8h sessions (hot_batch_prob=0.3).

## Families Observed

| family | seeds surfaced | coverage% | known limit |
|--------|---------------|-----------|-------------|
| baseline | 0 | 0% |  |
| beta_reversion | 0 | 0% |  |
| cross_asset | 20 | 100% | L2 — funding/OI gap limits real-data coverage |
| flow_continuation | 0 | 0% | L2 — funding/OI gap limits real-data coverage |
| momentum | 20 | 100% |  |
| null | 20 | 100% |  |
| reversion | 20 | 100% |  |
| unwind | 20 | 100% | L3 — high cadence pair |

**Average families per session**: 5.0

## Known Limits Affecting Family Coverage

- **L2 (Funding/OI gap)**: In real-data mode, only beta_reversion reliably fires.
  Family diversity check (weekly) will surface this if < 2 families over 5 days.
- **L3 (positioning_unwind × HYPE)**: Expected to dominate due to
  high-cadence pair pattern.  Family collapse mitigates to 1 digest/window.
