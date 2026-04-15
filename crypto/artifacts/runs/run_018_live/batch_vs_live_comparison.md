# Batch (Sprint R) vs Live (Run 018) Comparison

## Family Coverage

| grammar_family | batch (Sprint R) | live (Run 018) |
|---|---|---|
| cross_asset | YES | NO |
| positioning_unwind | NO | YES |

## New Families in Live Mode

Families detected live but not in batch: **positioning_unwind**

## Detection Timing

Batch: data fetched and processed once per window (1h / 4h / 8h / 7d).
Live:  event fired within ~0ms of threshold crossing (replay latency = 0ms).

## Noise Level

Live total events: 24 across 2 cycles.
Batch: 1 batch per window → no intra-window events.
