# Rule Generalization Note — run_010 Grammar Hotspot Scan

**Date:** 2026-04-15  
**Scan covers:** run_006 → run_010 (5 runs, Sprint G through J)

---

## The Fix Pattern (J1)

Sprint J introduced a discriminative gate inside `_e1_transient_aggression_chain`
(`crypto/src/kg/chain_grammar.py`):

```
IF has_funding_extreme(pair) AND has_oi_accumulation(pair):
    suppress E1 transient_aggression chain
    tag: j1_discriminative_gate=True
```

**Rationale:** Transient aggression burst is a *transient beta noise* signal. When the
local regime shows both extreme funding AND active OI accumulation, the aggression
is more likely a *positioning unwind signal* (E2) being misread as noise. Allowing
E1 to fire under these conditions produces a card that is structurally incompatible
with the dominant regime evidence — the card then gets rerouted or hard-rejected.

---

## Is J1 a Local Fix or a Generalizable Pattern?

### Verdict: Generalizable pattern, local instantiation

The J1 fix is a specific instance of a broader principle:

> **Meta-rule R1 (Regime Dominance):**  
> When a chain fires at a threshold boundary AND the dominant local regime contradicts
> the expected outcome of that chain, suppress the boundary-activation and treat the
> chain as non-activated.

J1 is one instantiation of R1. The general form:

| Slot | J1 (specific) | R1 (general) |
|------|--------------|--------------|
| Chain | E1 transient_aggression | Any burst/threshold chain |
| Threshold param | burst_min=4 | Any at-floor activation |
| Contradicting regime | funding_extreme + OI_accumulation | Any strong opposing regime signal |
| Suppression action | return None (chain not activated) | suppress + tag |

### Applicability to Other Grammar Pairs

**1. E1 beta_reversion vs E2 positioning_unwind (CONFIRMED — J1 fixes this)**
- Site: E1 transient_aggression chain, SOL pairs, funding_extreme
- Status: Resolved

**2. E1 beta_reversion vs flow_continuation (NO action needed)**
- The flow_continuation reroute was a secondary target (conf=0.60) that existed only
  because CLUS-A was confusing E1 into the wrong category.  
- With J1 eliminating the source cards, CLUS-B automatically resolves too.
- No independent E1↔flow_continuation confusion observed.

**3. E2 positioning_unwind vs flow_continuation (NOT a confusion site)**
- 0 reroutes and 0 reject_conflicted across run_006-010 for this pair.
- E2 and flow_continuation serve structurally distinct regimes and do not compete
  for the same evidence chains.
- Monitoring recommended but no fix required.

**4. D1-chain vs E2 (NOT a confusion site)**
- D1 cards consistently land in monitor_borderline (scores 0.71-0.78).
- This is genuine uncertainty about chain completeness, not grammar confusion.
- Soft-gating handles D1 borderline cases correctly; no rerouting occurs.

**5. Other burst-threshold chains (FUTURE — monitor)**
- `_e1_persistent_aggression_chain` uses a separate threshold (persistence_min).
  If it ever fires at the floor value under conflicting regime context, R1 applies.
- `flow_continuation` chain uses a premium threshold. Under extreme-OI + low-premium
  conditions, a boundary activation could create confusion with E2 (which requires
  funding pressure, not premium). Recommend checking regime context if floor-activation
  is detected.

---

## Threshold-Boundary Risk Inventory

| Chain | Threshold param | Boundary value | Current status | R1 applicable? |
|-------|----------------|----------------|----------------|----------------|
| E1 transient_aggression | burst_min | 4 | Fixed (J1) | Yes — done |
| E1 persistent_aggression | persistence_min | TBD | No boundary hit observed | Yes (if hit) |
| flow_continuation | premium_min | TBD | No boundary confusion | Yes (if hit) |
| soft_gate (G2) | uplift_min | 0.05 | 2 cards/run borderline | No confusion, different mechanism |

---

## Proposed Reusable Meta-Rule (R1 Template)

```python
# Meta-rule R1: Regime Dominance Gate
# Apply to any chain that activates at its minimum threshold.
#
# Why: A threshold-boundary activation means the evidence is maximally weak for
# that chain. If simultaneously a strong contradicting regime is present, the
# weak activation is dominated by noise and the stronger regime signal should
# take precedence. Suppressing prevents downstream rerouting and reject_conflicted.
#
# Template:
def _regime_dominance_check(chain_name, pair, collections, merged_kg,
                             threshold_hit_at_boundary):
    if not threshold_hit_at_boundary:
        return False  # not a boundary case — no suppression needed
    # check for dominant contradicting regime signals
    # (customize per chain)
    has_contra_regime = _check_contradicting_regime(chain_name, pair,
                                                     collections, merged_kg)
    return has_contra_regime  # True → suppress chain
```

---

## Remaining Local Exceptions (Post-J1)

After run_009 and run_010, the following cases remain in the output and are
**correct behavior** (not bugs):

1. **E1 beta_reversion: (ETH,BTC) — no funding shift, no OI expansion**
   - Score: 0.772, tier: actionable_watch
   - Regime: funding_quiet + low_vol → true beta reversion, J1 gate correctly does NOT fire
   - Expected: ETH/BTC historically recouples within 2-4 epochs under these conditions
   
2. **Soft-gated cards (2/run)**
   - 2 cards per run have is_soft_gated=True and uplift < 0.05
   - These are uplift-borderline cases, not grammar confusions
   - Correct handling: demoted to monitor_borderline

No unresolved grammar confusion remains in the post-J1 codebase.

---

## Summary

| Question | Answer |
|----------|--------|
| Was SOL confusion a local bug? | Partially — triggered by SOL's specific regime profile |
| Is J1 generalizable? | Yes — as Meta-rule R1 (Regime Dominance) |
| Other grammar pairs affected? | None detected across 5 runs |
| Other threshold-boundary risks? | 2 chains to monitor; no active confusion |
| Remaining exceptions? | 2 cases; both are correct behavior, not bugs |
