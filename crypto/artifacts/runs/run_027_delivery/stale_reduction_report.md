# Stale Reduction Report — Run 027

Stale = cards in **aging + digest_only + expired** state at review time.
Stale rate = stale_count / total cards.

| Cadence (min) | Avg Stale Rate | Avg Info Loss | Reviews/Day |
|--------------|----------------|---------------|------------|
| 30 | 0.065 | 0.685 | 48 |
| 45 | 0.210 | 0.684 | 32 |
| 60 | 0.903 | 0.684 | 24 |
| 120 | 1.000 | 0.095 | 12 |

## Stale Rate Threshold

- **Target**: stale_rate < 0.20 (< 20% of deck is stale at review time)
- **Critical**: stale_rate > 0.50 (majority of deck is stale — cadence too long)

## Info Loss Threshold

- **Acceptable**: info_loss < 0.35 (collapsed co-assets hold < 35% of total score)
- **High loss warning**: info_loss > 0.50 (collapse discards significant signal)
