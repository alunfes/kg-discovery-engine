# run_007 → run_008 diff analysis — Sprint I Decision Framework

**Date:** 2026-04-15
**Comparison:** run_007_sprint_h (baseline) → run_008_sprint_i (Sprint I)
**Same seed/duration/assets:** seed=42, 120 min, HYPE/ETH/BTC/SOL, top_k=60

---

## Tier Distribution (I1) — NEW in Sprint I

Total cards: 60 (identical to run_007)

| Tier | Count | % |
|------|-------|---|
| research_priority | 28 | 46.7% |
| monitor_borderline | 12 | 20.0% |
| actionable_watch | 7 | 11.7% |
| baseline_like | 7 | 11.7% |
| reject_conflicted | 6 | 10.0% |

**Interpretation:** Nearly half the cards (47%) are research_priority — solid signal
but needing one more confirmation run. 10% are cleanly actionable (7 cards with
composite ≥ 0.74, positive uplift, low contradiction). 10% are reject_conflicted,
all beta_reversion cards with severity=6.0 (terminal gate blocked by funding extreme).

---

## Actionable Watch Top-5 (I1)

1. **positioning_unwind** — E2 (HYPE,ETH) one-sided OI build — score=0.865, uplift=+0.224
2. **positioning_unwind** — E2 (HYPE,SOL) funding pressure — score=0.806, uplift=+0.145
3. **positioning_unwind** — E2 (HYPE,ETH) premium compression — score=0.780, uplift=+0.139
4. **beta_reversion** — E1 (ETH,BTC) no funding shift — score=0.772, uplift=+0.111
5. **other** — Chain-D1 (HYPE,ETH) B3 chain — score=0.771, uplift=+0.070

All 7 actionable_watch cards clear the 0.74 composite threshold and have
uplift > 0.04 over their matched baseline. HYPE/ETH is the dominant pair across
actionable tiers (3 of top 5), indicating concentrated structural signal.

---

## Monitor Borderline Cases (I1)

5 Chain-D1 "other" branch cards (HYPE/BTC, HYPE/SOL, ETH/SOL, BTC/SOL, HYPE/ETH)
sit at monitor_borderline. None are soft-gated — they qualify via composite ≥ 0.60
but fall below the research_priority threshold (0.65). These B3 chain hypotheses
may graduate to research_priority with a more differentiated synthetic scenario.

---

## Reject Conflicted Cases (I1)

6 beta_reversion cards, all *SOL pairs (HYPE/SOL, ETH/SOL, BTC/SOL), with
contradiction_severity=6.0. These are the same cards that fell hardest in the G1
conflict ranking (up to Δ=-47 rank shift from raw to conflict-adjusted). The tier
framework correctly discards them: high raw score (0.63–0.74) but severe
terminal-gate contradiction means they cannot be acted on.

---

## Confusion Matrix (I3)

### branch_reroute_matrix
```
beta_reversion → positioning_unwind: 6
beta_reversion → flow_continuation:  6
```
All 12 reroutes originate from beta_reversion. No positioning_unwind → other direction
appears, confirming that the E1 grammar is the primary confusion site.

### contradiction_type × rerouted_branch
```
funding_oi_block → positioning_unwind: 12, flow_continuation: 12
premium_block    → positioning_unwind: 12, flow_continuation: 12
```
Both contradiction types drive both reroute targets equally. This is a matrix
artifact of the join: the same pair-level contradiction log entry is counted for
every reroute on that pair. The actual reroute split is 50/50 by rule confidence
(0.70 → positioning_unwind, 0.60 → flow_continuation).

### location_reroute_matrix
```
terminal_gate → positioning_unwind: 12, flow_continuation: 12
mid_chain     → positioning_unwind: 12, flow_continuation: 12
```
beta_reversion confusions hit at both terminal_gate (E1-chain-1 hop 3, blocked by
funding extreme) and mid_chain (premium check). Both locations produce identical
reroute output, indicating the confusion is structural (wrong branch for SOL pairs
in funding-extreme regime) rather than evidence-gathering noise.

**Key finding:** SOL pairs with HYPE-correlated funding are systematically
misrouted to beta_reversion. The grammar should either add a SOL-aware gating
rule or flag funding_extreme co-incident with SOL pairs as a hard E1 disqualifier.

---

## Persistence Tracking (I2) — First Run

This is the first persistence snapshot (run_007+ baseline). All 16 families
have consecutive_top_k_count=1 by definition.

**Promotions this run:**
- 3 families promoted to `primary_to_rerouted` (beta_reversion:HYPE/SOL:E1,
  BTC/SOL:E1, ETH/SOL:E1) — these are the reject_conflicted cards that have
  live reroute targets. When run_009 fires, these families will show whether
  the rerouted branch (flow_continuation) persists.

**No soft_gated → active promotions** in this run. All border-case activations
(if any) did not make the active tiers this seed.

---

## Watchlist Semantics (I4)

| Label | Count |
|-------|-------|
| positioning_unwind_watch | 30 |
| monitor_no_action | 22 |
| discard_or_low_priority | 6 |
| beta_reversion_watch | 2 |

**Urgency split:** high=7, medium=28, low=12, none=13

The watchlist is dominated by `positioning_unwind_watch` (50%) reflecting the
run_007 branch distribution (50% positioning_unwind). The 6 `discard_or_low_priority`
cards correspond exactly to the 6 reject_conflicted. The 2 `beta_reversion_watch`
cards are the only E1 hypotheses that passed the tier filter (ETH/BTC and
HYPE/ETH pairs, which lack the SOL funding extreme contradiction).

**Chain-D1 gap:** Chain-D1 "other" branch cards receive `monitor_no_action`
label despite reaching monitor_borderline tier. This is expected: the "other"
branch has no dedicated watch label. A future Sprint J could add a
`chain_grammar_watch` label for D1/B3 chain hypotheses.

---

## Summary

Sprint I converts the H-sprint hypothesis arbitration signals into an operational
decision framework. The key results:

- **7 cards actionable** (HYPE positioning unwind + ETH/BTC beta reversion)
- **6 cards cleanly discarded** (SOL beta_reversion with severe contradictions)
- **Grammar confusion is localized**: beta_reversion SOL pairs in funding-extreme
  regime are the single largest source of reroutes
- **Persistence baseline established**: run_009 will give the first cross-run
  persistence signal for the 16 identified families
