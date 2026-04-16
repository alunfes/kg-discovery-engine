# Run 020 — Suppression / De-prioritisation Examples

Cards that received `contradict` or `expire_faster` transitions.

## Scenario A_flow_continuation_vs_sell

### fc_actionable (flow_continuation, HYPE)

| Field | Before | After | Change |
|---|---|---|---|
| Tier | `actionable_watch` | `monitor_borderline` | DOWNGRADED |
| Score | 0.85 | 0.6 | -0.2500 |
| Half-life (min) | 40.0 | 20.0 | halved |

Rules fired: contradict, contradict, expire_faster

- `HYPE_sell_burst_1700100000000_0`: sell_burst(HYPE) contradicts flow_continuation → actionable_watch→research_priority
- `HYPE_spread_widening_1700100600000_1`: spread_widening(HYPE) contradicts flow_continuation → research_priority→monitor_borderline
- `HYPE_book_thinning_1700101200000_2`: book_thinning(HYPE) invalidates premise; hl 40.0→20.0min

### fc_monitor (flow_continuation, HYPE)

| Field | Before | After | Change |
|---|---|---|---|
| Tier | `monitor_borderline` | `monitor_borderline` | unchanged |
| Score | 0.58 | 0.43 | -0.1500 |
| Half-life (min) | 60.0 | 7.5 | halved |

Rules fired: expire_faster, expire_faster, expire_faster

- `HYPE_sell_burst_1700100000000_0`: sell_burst(HYPE) invalidates premise; hl 60.0→30.0min
- `HYPE_spread_widening_1700100600000_1`: spread_widening(HYPE) invalidates premise; hl 30.0→15.0min
- `HYPE_book_thinning_1700101200000_2`: book_thinning(HYPE) invalidates premise; hl 15.0→7.5min

### fc_research (flow_continuation, HYPE)

| Field | Before | After | Change |
|---|---|---|---|
| Tier | `research_priority` | `monitor_borderline` | DOWNGRADED |
| Score | 0.72 | 0.52 | -0.2000 |
| Half-life (min) | 50.0 | 12.5 | halved |

Rules fired: contradict, expire_faster, expire_faster

- `HYPE_sell_burst_1700100000000_0`: sell_burst(HYPE) contradicts flow_continuation → research_priority→monitor_borderline
- `HYPE_spread_widening_1700100600000_1`: spread_widening(HYPE) invalidates premise; hl 50.0→25.0min
- `HYPE_book_thinning_1700101200000_2`: book_thinning(HYPE) invalidates premise; hl 25.0→12.5min

## Scenario B_positioning_unwind_vs_recovery

### pu_actionable (positioning_unwind, HYPE)

| Field | Before | After | Change |
|---|---|---|---|
| Tier | `actionable_watch` | `monitor_borderline` | DOWNGRADED |
| Score | 0.82 | 0.62 | -0.2000 |
| Half-life (min) | 40.0 | 40.0 | unchanged |

Rules fired: contradict, contradict

- `HYPE_buy_burst_1700100000000_0`: buy_burst(HYPE) contradicts positioning_unwind → actionable_watch→research_priority
- `HYPE_oi_change_1700100600000_1`: oi_change(HYPE) contradicts positioning_unwind → research_priority→monitor_borderline

### pu_research (positioning_unwind, HYPE)

| Field | Before | After | Change |
|---|---|---|---|
| Tier | `research_priority` | `monitor_borderline` | DOWNGRADED |
| Score | 0.7 | 0.55 | -0.1500 |
| Half-life (min) | 50.0 | 25.0 | halved |

Rules fired: contradict, expire_faster

- `HYPE_buy_burst_1700100000000_0`: buy_burst(HYPE) contradicts positioning_unwind → research_priority→monitor_borderline
- `HYPE_oi_change_1700100600000_1`: oi_change(HYPE) invalidates premise; hl 50.0→25.0min

## Scenario C_beta_reversion_vs_buy_pressure

### br_actionable (beta_reversion, HYPE)

| Field | Before | After | Change |
|---|---|---|---|
| Tier | `actionable_watch` | `monitor_borderline` | DOWNGRADED |
| Score | 0.8 | 0.6 | -0.2000 |
| Half-life (min) | 40.0 | 40.0 | unchanged |

Rules fired: contradict, contradict

- `HYPE_buy_burst_1700100000000_0`: buy_burst(HYPE) contradicts beta_reversion → actionable_watch→research_priority
- `HYPE_buy_burst_1700100600000_1`: buy_burst(HYPE) contradicts beta_reversion → research_priority→monitor_borderline

### br_monitor (beta_reversion, HYPE)

| Field | Before | After | Change |
|---|---|---|---|
| Tier | `monitor_borderline` | `monitor_borderline` | unchanged |
| Score | 0.55 | 0.45 | -0.1000 |
| Half-life (min) | 60.0 | 15.0 | halved |

Rules fired: expire_faster, expire_faster

- `HYPE_buy_burst_1700100000000_0`: buy_burst(HYPE) invalidates premise; hl 60.0→30.0min
- `HYPE_buy_burst_1700100600000_1`: buy_burst(HYPE) invalidates premise; hl 30.0→15.0min

