# Loss Timing Distribution — Run 042

**Total permanent losses**: 61

**Cards with gap data** (companion arrived after archival): 59

**No post-archival companion** (companion_preceded / unknown): 2 (3.3%)

**In-window non-resurfaces** (no_companion_window): 28 (45.9%)

---

## Gap Distribution (archival → companion arrival)

_N with gap = 59_

| Metric | Value (minutes) |
|--------|-----------------|
| Mean | 199.8 |
| Median (P50) | 150.0 |
| P25 | 90.0 |
| P75 | 285.0 |
| P90 | 420.0 |
| P99 | 830.4 |
| Min | 30.0 |
| Max | 900.0 |

## Bucket Distribution

| Gap bucket | Count | % of losses-with-gap | Mechanism |
|-----------|-------|---------------------|-----------|
| ≤120min (within resurface window) | 18 | 30.5% | no_companion_window |
| 120–240min (1–2 LCM slots past window) | 21 | 35.6% | proximity_miss |
| 240–480min (approaching archive expiry) | 16 | 27.1% | proximity_miss |
| 480–960min (archive expired, 8–16h gap) | 4 | 6.8% | time_expired |
| >960min (very large gap, >16h) | 0 | 0.0% | time_expired |

## Key Thresholds

| Threshold | Value | Meaning |
|-----------|-------|---------|
| resurface_window_min | 120 min | Companion after this → proximity_miss |
| archive_max_age_min | 480 min | Companion after this → time_expired |
| LCM(batch=30, cadence=45) | 90 min | Resurface can only fire every 90 min |

## Interpretation

Cards with gap 0–120 min (no_companion_window) represent cases where the companion arrived within the resurface window but the card was not resurfaced. This is the LCM slot collision pattern: batch and review cadences are out of phase, so even a same-window companion misses the fire slot.

Cards with gap 120–480 min (proximity_miss) are the 'addressable' losses. The companion was too late for the window but the archive hadn't expired. These are candidates for regime-aware archival or family-specific archive_max_age.

Cards with gap >480 min (time_expired) and companion_preceded are structural: no policy change can recover these without breaking the archive retention contract.
