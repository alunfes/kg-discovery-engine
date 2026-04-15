# Run 009 — beta_reversion vs positioning_unwind Grammar Disambiguation

**Date:** 2026-04-15  
**Sprint:** J (Grammar Disambiguation)  
**Run ID:** run_009_20260415  
**Seed:** 42 | Duration: 120 min | Assets: HYPE/ETH/BTC/SOL | Top-K: 60

---

## Objective

Determine whether the systematic confusion between `beta_reversion` (E1) and
`positioning_unwind` (E2) grammars for SOL-involving pairs in funding-extreme
regimes can be resolved by a minimal discriminative rule.

**Success criteria:**
- Reroute count decreases measurably
- `positioning_unwind_watch` precision stays high (no false positives added)
- Contradiction severity drops
- Watchlist remains non-trivially populated (does not become too lean)

---

## Confusion Cases (Task 1)

**Source:** `run_008_sprint_i/h2_reroute_candidates.json`  
**Filter:** `original_branch=beta_reversion`, `reroute_candidate_branch=positioning_unwind`

6 confusion cases identified — all SOL-involving pairs in funding-extreme regime:

| Card | Pair | Original Score | Rerouted Score | Confidence |
|------|------|---------------|---------------|-----------|
| b5aeae03 | HYPE/SOL | 0.7412 | 0.5341 | 0.70 |
| 2222f417 | HYPE/SOL | 0.6346 | 0.4222 | 0.70 |
| 682c89ab | ETH/SOL | 0.6182 | 0.4050 | 0.70 |
| c36c522f | ETH/SOL | 0.6361 | 0.4238 | 0.70 |
| 4af68a0e | BTC/SOL | 0.6195 | 0.4064 | 0.70 |
| cd7a1976 | BTC/SOL | 0.6356 | 0.4233 | 0.70 |

All 6 are `reject_conflicted` (contradiction_severity=6.0). Reroute reason:
`"beta_reversion blocked by funding extreme → unwind candidate"`.

**Full analysis:** `run_009_20260415/confusion_cases.json`

---

## Feature Comparison (Task 2)

Triggering features extracted via pipeline introspection (seed=42, same state):

| Feature | HYPE/SOL | ETH/SOL | BTC/SOL | ETH/BTC (true β-rev) |
|---------|----------|---------|---------|---------------------|
| funding_extreme_count | 3 | 1 | 1 | **0** |
| funding_state_is_extreme | True | True | True | **False** |
| has_oi_accumulation | True | True | True | **False** |
| oi_state_score | 1.000 | 1.000 | 1.000 | N/A |
| oi_build_duration | 69 | 69 | 69 | N/A |
| aggression_burst_min | 4 | 4 | 4 | — (5, already blocked) |
| aggression_persistent_gt4 | False | False | False | — |
| e1_transient_aggr_fired | **True** | **True** | **True** | False |
| e2_oi_crowding_confirmed | True | True | True | True* |
| e2_funding_pressure_confirmed | True | True | True | False |
| discriminative_flag (fund∧OI) | **True** | **True** | **True** | **False** |

*ETH/BTC E2 OI crowding fires based on HYPE's OI accumulation (pair-level check)
 but ETH/BTC has no funding_extreme → E2 funding pressure does NOT fire → clean E1.

**Key discriminative boundary:**  
`funding_extreme AND OI_accumulation` is True for all 3 SOL confusion pairs and
False for the true beta_reversion pair (ETH/BTC). This is the minimal sufficient
condition to suppress E1 transient_aggression.

**Full table:** `run_009_20260415/feature_comparison.csv`

---

## Discriminative Rule (Task 3)

### Grammar Fix — J1 Gate in `_e1_transient_aggression_chain`

The core bug: E1 Chain 2 (`_e1_transient_aggression_chain`) checked burst count
(1–4 windows = transient) but did NOT check whether funding_extreme or OI_accumulation
were present. For SOL pairs with `burst_min=4` (exactly at the `>4` threshold
boundary), the chain fired and built `NoPersistentAggressionNode` nodes, which
the hypothesis generator used to produce E1 beta_reversion cards — despite the
E2 positioning_unwind chains being fully activated for the same pairs.

**Fix (chain_grammar.py):** Added the J1 discriminative gate as the **first check**
in `_e1_transient_aggression_chain`:

```
IF funding_extreme_count(pair) > 0 AND has_oi_accumulation(pair):
    → suppression: contradictory_evidence (j1_discriminative_gate=True)
    → E1 transient_aggression chain does NOT build nodes for this pair
    → No beta_reversion hypothesis card generated
    → No reroute triggered
    → E2 positioning_unwind hypothesis for same pair is undisturbed
```

**Defense-in-depth (rerouter.py):** Added a high-confidence (0.85) reroute rule
triggered by the J1 gate's suppression reason. This fires if any beta_reversion
SOL card somehow survives the chain_grammar fix in future runs.

### Boundary Conditions

```
True beta_reversion (E1 allowed):
  - funding_extreme = 0 AND OI_accum = False
  - burst_min in [1,4]
  - E2 chains do NOT fire for the same pair

True positioning_unwind (E1 blocked):
  - funding_extreme > 0 AND OI_accum = True  ← J1 gate
  - E2 chains fully activated (OI crowding + funding pressure)

Ambiguous / not yet handled:
  - funding_extreme > 0 but OI_accum = False → J1 does NOT fire; burst count decides
  - funding_extreme = 0 but OI_accum = True → J1 does NOT fire; E1 Chain 1 blocks
```

---

## Before/After Adjudication (Task 4)

### Reroute Counts

| Direction | Before | After |
|-----------|--------|-------|
| beta → positioning_unwind | **6** | **0** |
| beta → flow_continuation | 6 | 0 |
| **Total** | **12** | **0** |

### Tier Distribution

| Tier | Before | After | Δ |
|------|--------|-------|---|
| actionable_watch | 7 | 6 | −1 |
| research_priority | 28 | 30 | +2 |
| monitor_borderline | 12 | 17 | +5 |
| baseline_like | 7 | 7 | 0 |
| **reject_conflicted** | **6** | **0** | **−6** |

### Contradiction Severity

| | Before | After |
|-|--------|-------|
| mean_severity | 0.600 | **0.000** |
| max_severity | 6.0 | **0.0** |
| n_cards_severity ≥ 5 | 6 | **0** |

### Watchlist

| Label | Before | After | Δ |
|-------|--------|-------|---|
| positioning_unwind_watch | 30 | 30 | 0 |
| monitor_no_action | 22 | 28 | +6 |
| **discard_or_low_priority** | **6** | **0** | **−6** |
| beta_reversion_watch | 2 | 2 | 0 |

### Success Criteria Assessment

| Criterion | Result |
|-----------|--------|
| Reroute count decreases | ✅ 12 → 0 (−100%) |
| positioning_unwind_watch precision | ✅ 30/30 unchanged (no false positives) |
| Contradiction severity drops | ✅ max 6.0 → 0.0 |
| Watchlist not too lean | ✅ 30 PU watch + 28 monitor = 58 active entries |
| beta_reversion preserved (ETH/BTC) | ✅ actionable_watch (0.772) unchanged |

All 4 success criteria met.

---

## Key Findings

1. **Root cause confirmed:** E1 Chain 2 (`_e1_transient_aggression_chain`) lacked
   the same `funding_extreme OR OI_accumulation` guard that E1 Chain 1
   (`_e1_no_funding_oi_chain`) already had. This was a consistency gap in the
   E1 chain grammar.

2. **Burst count boundary sensitivity:** `burst_min=4` (SOL pairs) sits exactly
   at the `> 4` threshold. The J1 gate resolves this by providing a
   feature-based override that does not depend on the burst count threshold.

3. **E2 chains unaffected:** All E2 positioning_unwind chains for SOL pairs
   continue to fire correctly after the fix. The 5 positioning_unwind
   actionable_watch cards are identical before and after.

4. **Hypothesis space cleaned:** Removing 6 reject_conflicted beta_reversion SOL
   cards freed 6 top-60 slots. Five new `Correlation break` monitor_borderline
   cards entered (raw corr_break placeholders, properly held at lower tiers).

5. **Zero false reroutes:** The rerouter's J1 safety-net rule (conf=0.85) did not
   trigger in run_009 — confirming the chain_grammar fix is the correct primary fix.

---

## Files Produced

| File | Location | Description |
|------|----------|-------------|
| confusion_cases.json | run_009_20260415/ | 6 confusion case records with enriched context |
| feature_comparison.csv | run_009_20260415/ | Feature table: confusion pairs vs true beta_reversion |
| before_after_decision_map.md | run_009_20260415/ | Full tier/watchlist/reroute before→after table |
| recommended_rule_update.md | run_009_20260415/ | Rule design, boundary conditions, future work |
| output_candidates.json | run_009_20260415/ | 60 hypothesis cards (post-fix) |
| i1_decision_tiers.json | run_009_20260415/ | Tier assignments (0 reject_conflicted) |
| h2_reroute_candidates.json | run_009_20260415/ | Empty (0 reroutes) |
| branch_metrics.json | run_009_20260415/ | Full metrics including J1 suppression entries |
| run009_grammar_disambiguation.md | crypto/docs/ | This document |

---

## Next Steps

1. **run_010** — First cross-run persistence test with clean baseline:
   - 3 SOL family IDs previously marked `primary_to_rerouted` will show persistence=0
   - The 5 positioning_unwind actionable_watch cards should persist (consecutive=2)

2. **Burst threshold hardening** — Consider `burst_count >= 4` → failed_followthrough
   to remove boundary sensitivity at exactly burst=4

3. **J1 generalization** — Consider applying J1 gate to `_e1_weak_premium_chain` as
   well (currently redundant since _e1_weak_premium_chain already checks funding_extreme)

4. **PR** — `claude/zen-curran` contains J1 discriminative fix + run_009 artifacts.
   Ready for merge to main via PR.
