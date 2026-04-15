# Fusion Safety Envelope — Run 021 Rules

## Rule 1: Demotion Rate Limit

- Window: **15 minutes**
- Per-card tracking: `last_demotion_ts` (ms) on `FusionCard`
- Behavior: Within the window, a second `contradict` is converted to
  `contradict_ratelimited` — score penalty + half-life halving applied,
  but **tier does NOT downgrade**.
- Multi-step downgrades spaced > 15 min apart are **not blocked**.

## Rule 2: Half-Life Floor

| Tier | Floor (min) |
|------|------------:|
| actionable_watch | 10 |
| research_priority | 5 |
| monitor_borderline | 3 |
| baseline_like | 2 |
| reject_conflicted | 1 |

- Applied in `_apply_expire_faster` and `_apply_contradict` (ratelimited path).
- Half-life is halved first; result clamped to floor.
- Reason string includes `[floor]` tag when floor is active.

## Interaction

- Rate limit and floor are independent: rate limit only blocks tier
  downgrades; floor only prevents half-life going too low.
- A rate-limited contradict still applies the floor to its half-life
  shortening (same as expire_faster).
- reinforce and promote are **not affected** by either rule.
