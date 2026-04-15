# Run 013 -- Half-Life Analysis

Analysis of half-life adequacy relative to observed time-to-outcome.

- **avg_time_to_outcome_min**: 14.9
- **avg_half_life_remaining_min**: -9.6
- **half_life_adequacy_rate**: 53.3%
- **recommendation**: Consider increasing half-life; many events exceed current window.

## Half-Life Distribution (minutes -> N cards)

| Half-Life (min) | N Cards |
|----------------|---------|
| 40 | 6 |
| 50 | 30 |
| 60 | 24 |

## Adequacy Note

Adequacy rate = fraction of tracked cards where time_to_outcome < half_life.
Cards with no outcome event contribute half_life_remaining = -half_life,
pulling the average negative. For cards that DID hit, events arrived well
within the window (avg_tte << half_life). The negative adequacy reflects
that miss/expired cards (HYPE/ETH/BTC branches) never find events regardless
of window length -- not a half-life calibration failure.
