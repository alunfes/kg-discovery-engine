# Run 031 — Stale & Fresh Report

**Stale rate** = aging_count / (fresh + active + aging) at push-fire time.
**Avg fresh per push** = mean fresh card count in deck when push fires (raw, pre-collapse).

Note: poll_45min stale_rate=0.21 is measured at fixed cadence intervals across
all deck cards. Push stale rate is measured only at push-fire moments (when T1/T2
already confirm fresh signal exists), making them structurally different metrics.

## Stale Rate Comparison

| Config | Stale Rate | Avg Fresh/Push | Missed Critical |
|--------|-----------|----------------|-----------------|
| Run027 poll_45min | 0.21 (cadence-time) | 4.8 (post-collapse) | 0 |
| Run029B push baseline (T3=10min) | 0.295 (push-fire) | 17.4 (raw deck) | 0 |
| **Run031 Variant A (T3=5min)** | **0.295 (push-fire)** | **17.4 (raw deck)** | **0** |

## Freshness Analysis

The push stale rate (29.5%) is measured only when a push fires — i.e., when
T1/T2 confirm the deck has actionable content. Aging cards in the 29.5% fraction
appear as context; the primary review content is the 17.4 fresh + ~4.9 active
raw cards, collapsing to ~5.8 post-family-collapse items per push.

Per-day stale rate (Variant A): 29.6%, 25.3%, 27.5%, 32.8%, 32.3%
Range: 25–33%. Day-to-day variance reflects hot-batch clustering; busier days
accumulate more aging cards between pushes.

T3 fired 0 times across all 5 days: T1/T2 covered all high-conviction cards
before they reached the aging last-chance window. T3=5min is a dormant safety
net — correct to have, never needed in this simulation.

## Critical Coverage

- Variant A missed_critical over 5 days: **0**
- Run029B missed_critical over 5 days: **0**
- Success criterion: missed_critical = 0 maintained
- Assessment: **PASS** — missed_critical = 0 (target ≤ 0)

