# Run 025: Oscillation / Chatter Analysis

**Result: No chattering**

- Real switches (executed): 4
- Suppressed by dwell guardrail: 1
- Suppressed by hysteresis: 1
- Max switches in 30-min window: 2 (threshold=3)

No chatter intervals detected — guardrails effective.


## Guardrail Design

- **Dwell time**: 15 min minimum between switches
- **Hysteresis**: sparse→calm requires n_events ≥ 95 (vs normal threshold 90)

