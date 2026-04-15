# Candidate Future R1 Applications — Run 012

**Date:** 2026-04-15  
**Sprint:** L  
**Based on:** retrospective analysis of run_009–011 + live run_012 detection

---

## Summary

Run 012 boundary detection across 3 retrospective runs (run_009–011) and one live run
identified **1 chain type** with near-threshold activations:

| Chain | Threshold | # Activations | # High-Risk | Verdict |
|-------|-----------|--------------|-------------|---------|
| `positioning_unwind_oi_crowding` | `oi_confidence_min = 0.30` | 3 | 0 | LOW risk — monitor |

No HIGH-risk candidates (boundary_proximity < 0.20 + regime_contradiction) were found.  
The J1/R1 fix (Sprint J/K) is working correctly: SOL pairs with funding_extreme + OI produce
no NoPersistentAggressionNode → no spurious boundary records.

---

## Ranked Candidate List

### Rank 1 — `positioning_unwind_oi_crowding` (soft-gate activation)

| Field | Value |
|-------|-------|
| **chain_type** | `positioning_unwind_oi_crowding` |
| **threshold involved** | `soft_gate_confidence_min = 0.30` (SOFT_GATE_MIN) |
| **regime signals that could contradict** | None (OI accumulation is the trigger for E2, not a contradiction) |
| **estimated risk level** | LOW |
| **recommended action** | Monitor — track if soft-gated activations at ETH/BTC pair produce lower-quality cards |

**Why this is NOT an R1 candidate yet:**  
E2 chains are the *positioning unwind* chain family. OI accumulation is a *positive* signal for
E2, not a contradicting signal. Applying R1 to E2 chains based on OI accumulation would suppress
the exact chains that should fire under that regime — this is the over-suppression case explicitly
prohibited in `grammar_meta_rules.md` (R1 Over-Suppression Guard).

**When this could become a candidate:**  
Only if a clear *contradicting* regime signal for `positioning_unwind` were identified — e.g. a
signal that predicts beta_reversion is dominant when OI is borderline. No such signal is currently
registered. Track via persistence metrics (R2 candidate).

---

### Rank 2 — `beta_reversion_transient_aggr` (burst_count boundaries)

| Field | Value |
|-------|-------|
| **chain_type** | `beta_reversion_transient_aggr` |
| **threshold involved** | `burst_count_max = 4` (upper) and `burst_count_min = 1` (lower) |
| **regime signals that could contradict** | `funding_extreme AND oi_accumulation` |
| **estimated risk level** | MEDIUM (potential, not observed in runs 009–011) |
| **recommended action** | J1/R1 already handles the strongest case (both signals); this rank tracks the partial-signal case |

**Analysis:**  
J1/R1 (run_011) correctly suppresses E1 when BOTH `funding_extreme` AND `oi_accumulation` are
present. The remaining partial-signal case (only one signal active) was NOT observed causing HIGH
boundary warnings in runs 009–011. Therefore no new R1 instance is recommended at this time.

**Condition to promote to R1 candidate:**  
Observe ≥2 runs where `NoPersistentAggressionNode` exists for a pair with:
- `burst_count = 4` AND
- ONE of {`funding_extreme`, `oi_accumulation`} active (not both)
- AND resulting card reaches `reject_conflicted` tier

---

### Rank 3 — `continuation_candidate` (D3 corr_break_score boundary)

| Field | Value |
|-------|-------|
| **chain_type** | `continuation_candidate` |
| **threshold involved** | `corr_break_score_min = 0.20` |
| **regime signals that could contradict** | `funding_extreme` |
| **estimated risk level** | LOW |
| **recommended action** | Monitor — no boundary activations observed yet |

**Analysis:**  
D3 gates the continuation_candidate branch at corr_break_score ≥ 0.20. No near-threshold D3
activations with funding_extreme were observed in the retrospective runs. This chain is pre-
registered in CHAIN_THRESHOLDS for future monitoring but has no observed confusion yet.

---

## Not Recommended for R1

| Chain | Reason |
|-------|--------|
| `positioning_unwind_funding_pressure` (E2) | funding_extreme is the trigger, not a contradiction |
| `positioning_unwind_oi_crowding` (E2) | same as above |
| `beta_reversion_no_funding_oi` | Already has binary contradictory_evidence gate (line ~257 chain_grammar.py); R1 would be redundant |
| `beta_reversion_weak_premium` | Already has `_scan_funding_extreme_kg` guard (line ~377) |

---

## Over-Suppression Guard Reminder

Per `grammar_meta_rules.md`, R1 must NOT be applied to:
- E2 chains (they fire *because* funding_extreme / OI_accumulation is present)
- OR-combinator specs with broad signals (over-suppresses)
- Chains that already have dedicated contradictory-evidence gates
