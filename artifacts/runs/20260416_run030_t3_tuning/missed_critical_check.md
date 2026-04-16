# Missed Critical Check — Run 030

A critical card is a card in HIGH_PRIORITY_TIERS with composite_score >= 0.74.
A missed_critical is a critical card that was NOT covered by any push while still in STATE_FRESH.

| Variant | avg_missed_critical | vs baseline | Safety verdict |
|---------|--------------------|--------------|-----------------|
| baseline | 0.0 | — | SAFE |
| A_lookahead5 | 0.0 | — | SAFE |
| B_family_cooldown60 | 0.0 | — | SAFE |
| C_suppress_t1t2_30min | 0.0 | — | SAFE |
| D_digest_escalation60 | 0.0 | — | SAFE |

## Safety constraint

T3 tuning must not increase missed_critical above the baseline. A variant is SAFE if avg_missed_critical ≤ baseline. MARGINAL if ≤ 1.5× baseline. RISK if > 1.5× baseline.
