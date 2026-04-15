# Recommended Rule Update — J1 Grammar Disambiguation

**Sprint:** J (run_009_20260415)  
**Author:** Claude (zen-curran worktree)  
**Status:** IMPLEMENTED and validated

---

## Problem Statement

In `run_008_sprint_i`, 6 beta_reversion SOL pairs (HYPE/SOL, ETH/SOL, BTC/SOL ×2 each)
were generated as hypothesis cards by E1 Chain 2 (`_e1_transient_aggression_chain`),
despite the same pairs having fully active E2 positioning_unwind chains. This created:
- 6 `reject_conflicted` cards (severity=6.0) — noise in the actionable tier
- 12 reroutes (6 beta→positioning_unwind + 6 beta→flow_continuation) — spurious reroute load
- Watchlist contamination (6 `discard_or_low_priority` entries)

---

## Root Cause Analysis

### Grammar Conflict Mechanism

```
For pair X/SOL with funding_extreme > 0 and OI_accumulation = True:

E1 Chain 1 (no_funding_oi):
  _scan_funding_extreme_kg(...) > 0 → BLOCK (contradictory_evidence: funding extreme present)
  ✓ Correctly suppressed.

E1 Chain 2 (transient_aggression):           ← BUG
  burst_min = min(burst_a1, burst_a2)
  SOL: burst_min = 4  (exactly at threshold, NOT > 4)
  → Proceeds to build NoPersistentAggressionNode
  → DOES NOT check funding_extreme or OI_accumulation
  → E1 hypothesis card generated despite E2 conditions being fully met

E2 Chain 1 (funding_pressure):
  _scan_funding_extreme_kg(...) > 0 → fires FundingPressureRegimeNode
  ✓ Correctly fires.

E2 Chain 2 (oi_crowding):
  SOL has 53 OI accumulation states (score=1.0, duration=69)
  → fires OneSidedOIBuildNode + PositionCrowdingStateNode
  ✓ Correctly fires.
```

### Feature Signature of Confusion Cases

| Feature | SOL confusion pairs | True beta_reversion (ETH/BTC) |
|---------|--------------------|-----------------------------|
| funding_extreme_count | 1–3 | 0 |
| has_oi_accumulation | True | False |
| oi_state_score | 1.0 | N/A |
| oi_build_duration | 69 | N/A |
| burst_min | 4 (boundary) | — (burst_min=5, already blocked) |
| has_premium_dislocation | True | True |
| E2 OI chain firing | Yes | No |
| E2 funding chain firing | Yes | No |
| E1 transient fires (before fix) | Yes (boundary) | No (burst>4) |

**Key insight:** The true discriminative boundary is `funding_extreme AND OI_accumulation`,
not burst count alone. When both are present, the "transient" aggression burst is
a component of the positioning_unwind pattern (OI crowding + funding pressure +
correlated aggression), not an independent transient signal.

---

## Implemented Fix

### Rule J1 — Discriminative Gate in `_e1_transient_aggression_chain`

**File:** `crypto/src/kg/chain_grammar.py`  
**Function:** `_e1_transient_aggression_chain`

```python
# J1: Discriminative gate — funding extreme + OI accumulation → unwind context,
# not transient beta_reversion.  This is the key SOL funding-extreme fix.
has_fund_extreme = _scan_funding_extreme_kg(merged_kg, [a1, a2]) > 0
has_oi_accum = _has_oi_accumulation(collections, [a1, a2])
if has_fund_extreme and has_oi_accum:
    log.append({
        "chain": "beta_reversion_transient_aggr", "pair": pair,
        "reason": "contradictory_evidence",
        "detail": (
            "funding extreme + OI accumulation both present — "
            "aggression is unwind-context signal, not transient beta_reversion"
        ),
        "neg_evidence_taxonomy": "contradictory_evidence",
        "j1_discriminative_gate": True,
    })
    return
```

**Placement:** Before burst_count check. This ensures the gate fires regardless of
burst count magnitude when the unwind context is confirmed.

### Defense-in-Depth — High-Confidence Reroute Rule

**File:** `crypto/src/eval/rerouter.py`

Added a new reroute rule with confidence=0.85 that fires when the J1 gate
suppression is detected (in case any beta_reversion card somehow survives
the chain_grammar fix). This is a safety net — it does not trigger in the
current run since no beta_reversion SOL cards are generated.

---

## Boundary Conditions

### True beta_reversion (E1 should fire):
- `funding_extreme = False` AND `OI_accumulation = False`
- burst_min > 0 AND burst_min <= 4 (transient signal)
- No E2 chain activation for the same pair
- **Example:** ETH/BTC (funding_extreme=0, OI_accum=False)

### True positioning_unwind (E2 should fire, E1 should not):
- `funding_extreme = True` OR `OI_accumulation = True`
  - J1 gate: **both** present → suppress E1 transient_aggression
  - E1 no_funding_oi gate: **either** present → suppress E1 Chain 1
- E2 chains (OI crowding + funding pressure) fully active
- **Example:** HYPE/SOL, ETH/SOL, BTC/SOL (funding_extreme>0, OI_accum=True)

### Boundary / Ambiguous:
- `funding_extreme = True` but `OI_accumulation = False`
  - E1 Chain 1: blocked (funding extreme)
  - E1 Chain 2 (transient_aggr): J1 gate does NOT fire (needs both), burst check applies
  - E2 funding_pressure chain: fires
  - E2 oi_crowding chain: blocked (no OI)
  - Result: E2 partial activation, rerouter may fire
- `funding_extreme = False` but `OI_accumulation = True`
  - E1 Chain 1: blocked (OI accumulation)
  - E1 Chain 2 (transient_aggr): J1 gate does NOT fire, burst check applies
  - E2 oi_crowding chain: fires
  - Result: depends on burst count; if burst_min <= 4, E1 may still fire → monitor

---

## Validation Results

| Metric | Before | After | Pass? |
|--------|--------|-------|-------|
| Reroute count beta→positioning_unwind | 6 | 0 | ✅ |
| Reroute count total | 12 | 0 | ✅ |
| reject_conflicted cards | 6 | 0 | ✅ |
| max contradiction_severity | 6.0 | 0.0 | ✅ |
| positioning_unwind_watch count | 30 | 30 | ✅ (not leaner) |
| beta_reversion_watch count | 2 | 2 | ✅ (preserved) |
| ETH/BTC beta_reversion preserved | actionable_watch (0.772) | actionable_watch (0.772) | ✅ |
| J1 gate fires for SOL pairs | — | 6 entries (3 pairs × 2 corr_break) | ✅ |
| J1 gate does NOT fire for ETH/BTC | — | 0 entries for ETH/BTC | ✅ |

---

## Future Recommendations

1. **Boundary monitoring** (ambiguous cases):
   - Add tracking for pairs where `funding_extreme=True` but `OI_accum=False`
   - These are not fixed by J1 and may still generate misattributed cards

2. **Burst count threshold review**:
   - The `burst_count > 4` threshold creates boundary sensitivity at burst_count=4
   - Consider lowering to `>= 4` (i.e., `>= 4` → failed_followthrough) to make the
     boundary more conservative

3. **Cross-run persistence**:
   - With reject_conflicted eliminated, run_010 will be the first run where the
     3 formerly-rejected SOL family IDs (beta_reversion:HYPE/SOL:E1, etc.)
     show zero persistence — confirming the fix is durable

4. **J1 gate generalization**:
   - Current J1 requires BOTH funding_extreme AND OI_accum
   - Consider a weighted version: if OI_accum score > 0.8 alone (without funding_extreme),
     also suppress E1 transient_aggression
