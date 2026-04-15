# Recommended Decay Rule — Sprint T

## Chosen Parameters

| Parameter | Value | Rationale |
|---|---|---|
| Same-family decay coefficients | (1.0, 0.7, 0.5, 0.3) | Stepwise to avoid discontinuity; 0.3 floor retains weak signal |
| Time-window dedup (ms) | 300,000 (5 min) | Matches typical microstructure burst duration |
| Time-window credit | 0.3 | Partial credit for burst events (vs 0.0 which would discard) |
| Ceiling brake threshold | 0.9 | Soft barrier preserving rank spread near max |
| Ceiling brake factor | 0.2 | 5× reduction prevents saturation without full suppression |

## Observed Effect

Run 019 saturation: 10/10 cards at 1.0

Sprint T saturation: 0/10 cards at 1.0

Rank spread (top−bottom): 0.0537

Top-3 score gap: 0.0388

## Tuning Guidance

- If too few promotions occur: lower _TIME_WINDOW_MS (e.g. 2 min)
- If saturation persists with diverse events: lower _DECAY_COEFFICIENTS[3]
  from 0.3 to 0.2
- If rank spread too small: lower _CEILING_BRAKE_THRESHOLD to 0.85
