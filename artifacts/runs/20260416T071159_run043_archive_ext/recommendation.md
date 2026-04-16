# Recommendation — Run 043 Targeted Archive Extension

## Decision Criteria

| Criterion | Threshold | Actual | Pass? |
|-----------|-----------|--------|-------|
| recovery_rate improvement | > 0pp | +0.0pp | ✗ |
| noisy_resurface_rate Δ | ≤ +5pp | +0.0000 | ✓ |
| value_density_ratio Δ | ≥ −2% | +0.0000 | ✓ |
| pool bloat | ≤ +15% | +11.9% | ✓ |

## Verdict

**DO NOT ADOPT targeted archive extension**

- 0/15 MITIGATE cases recovered
- Permanent loss: 2400 → 2400 (+0)
- Recovery rate: 10.3% → 10.3% (+0.0pp)
- Pool bloat: +11.9%

## Root Cause — Why Extension Failed

The extension converted 15 time_expired cards into proximity_miss but created no new
resurfaces. The binding constraint is **resurface_window (120 min)**, not archive_max_age:

- MITIGATE cards had no same-family signal in the first 120 min after archival
- Same-family signals DO arrive in the 480–720 min window (confirmed by +15 proximity_miss)
- But (t - archived_at) > 120 min → outside resurface_window → pm, not resurface

Extending archive_max_age cannot recover cards whose resurface window has already closed.

## Next Steps

To recover proximity_miss losses, consider:
1. Wider resurface_window — but Run 040 confirmed LCM bottleneck blocks this
2. Review cadence alignment (cadence = batch_interval eliminates LCM gap)
3. Accept structural loss rate (~93.9% proximity_miss, ~6.1% isolated time_expired)

## Implementation

Apply `family_max_age_overrides` in `ArchiveManager` (delivery_state.py):
```python
ArchiveManager(
    archive_max_age_min=480,
    family_max_age_overrides={
        'cross_asset': 720,   # calm/active regime cards only
        'reversion':   720,   # calm/active regime cards only
    }
)
```
Note: In production, regime-conditional override requires the caller to
pre-screen families by regime before populating `family_max_age_overrides`.
