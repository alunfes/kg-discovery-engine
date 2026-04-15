# Run 011 — R1 Regime Dominance Gate Formalization

**Date:** 2026-04-15  
**Sprint:** K  
**Branch:** `claude/crazy-vaughan`  
**Base:** `claude/zen-curran` @ c9a30d8

---

## Executive Summary

Run 011 formally promotes Meta-rule R1 (Regime Dominance Gate) from an ad-hoc
Sprint J fix (J1) into a first-class, reusable grammar policy. The J1 inline
check in `chain_grammar.py` is replaced by a call to `apply_r1(_J1_R1_SPEC, ...)`.
Behavior is identical; structure is now general. Future grammar chains can apply
R1 declaratively via `@regime_dominance_gate(...)`.

No regression: 0 reroutes, 0 reject_conflicted, 60 watchlist cards — identical
to run_009/010 baselines.

---

## Background

### The Problem R1 Was Invented to Solve

Run_006 (Sprint G) first showed SOL-pair `beta_reversion` cards being assigned
`reject_conflicted` with severity=6.0 and rerouted to `positioning_unwind`. The
root cause (found in Sprint J / run_009):

- `_e1_transient_aggression_chain` fires on SOL pairs when `burst_count` ∈ [1,4]
- SOL simultaneously has `funding_extreme=True` AND `OI_accumulation=True`
- Under this regime, the aggression burst is an *unwind signal* (E2), not *beta
  noise* (E1)
- The E1 card was structurally incompatible with the E2 card for the same pair

Sprint J introduced J1: a discriminative gate that suppressed E1 when both regime
signals were present. Runs 009 and 010 confirmed: 0 reroutes, 0 reject_conflicted.

### The Generalization

Run_010 hotspot scan identified J1 as an instance of a general pattern:

> **R1 (Regime Dominance Gate):** When a chain fires at a threshold boundary AND
> the dominant local regime contradicts the expected outcome of that chain, suppress
> the boundary activation.

This is now formalized in `crypto/src/kg/regime_dominance_gate.py`.

---

## Design Decisions

### Decision 1: J1 behavior unchanged, structure generalized

The refactor is a pure structural change. The same boolean conditions
(`funding_extreme AND oi_accumulation`) produce the same suppression.
Sprint J tests pass without modification. Risk: zero.

**Why not change the behavior?** Run_009 and run_010 proved the J1 conditions
work correctly. Changing them would require a new behavioral validation run.
Sprint K only formalizes the structure.

### Decision 2: log_tag="j1_discriminative_gate" preserved as backward-compat alias

`RegimeDominanceChecker.should_suppress` always emits `r1_regime_dominance_gate=True`.
When `log_tag` is a custom value (e.g., `j1_discriminative_gate`), it is added as
an *additional* key alongside the R1 key.

**Why:** test_sprint_j.py asserts `e.get("j1_discriminative_gate")`. Removing this
would break existing tests without behavioral benefit. The alias costs one dict key.

### Decision 3: Built-in resolvers in regime_dominance_gate.py (not chain_grammar.py)

`_scan_funding_extreme_kg` and `_has_oi_accumulation` logic is reproduced in
`regime_dominance_gate.py` as `@register_regime_resolver` functions, rather than
imported from `chain_grammar.py`.

**Why:** `chain_grammar.py` imports from `regime_dominance_gate.py` (for R1PolicySpec
and apply_r1). If `regime_dominance_gate.py` imported from `chain_grammar.py`, a
circular import would occur. The resolver logic only uses `KGraph` and
`MarketStateCollection` types — no chain-grammar-specific logic.

### Decision 4: decorator AND inline pattern both provided

The `@regime_dominance_gate(...)` decorator is for new chains (clean, declarative).
The `apply_r1(spec, ...)` function is for existing chains (minimal diff, keeps
function signatures untouched).

**Why both?** The decorator requires a fixed positional signature:
`fn(kg, merged_kg, collections, a1, a2, corr_nid, break_score, log)`.
All current chain builders match this, but future chains might not. The inline
pattern is always available as a fallback.

---

## Over-Suppression Risk

R1 is NOT a silver bullet. Risks:

1. **E2 chain suppression (critical):** If R1 is applied to E2 chains with
   `funding_extreme` as a signal, E2 would be suppressed exactly when it should
   fire. NEVER apply R1 to chains whose expected_outcome matches the contradicting
   regime.

2. **OR combinator overreach:** An OR spec with `funding_extreme OR oi_accumulation`
   would suppress chains for ~40% of SOL pairs (either condition is common). Only
   use AND for precision.

3. **Broad application to non-boundary cases:** If a chain has very strong evidence
   (e.g., burst_count=20), suppressing it under regime conditions may be incorrect.
   The current R1 implementation does not distinguish boundary strength within the
   chain's valid activation range. If this becomes a problem, add a
   `boundary_range` parameter to R1PolicySpec.

---

## Files Changed

| File | Change |
|------|--------|
| `crypto/src/kg/regime_dominance_gate.py` | NEW — R1 formal spec, checker, apply_r1, decorator |
| `crypto/src/kg/chain_grammar.py` | MODIFIED — J1 inline → apply_r1(_J1_R1_SPEC, ...) |
| `crypto/tests/test_sprint_k.py` | NEW — 37 tests for R1 + pipeline regression |
| `crypto/docs/grammar_meta_rules.md` | NEW — meta-rule catalog (R1 as first entry) |
| `crypto/artifacts/runs/run_011_r1_formalization/` | NEW — run artifacts |

---

## Test Coverage

| Test class | Coverage |
|-----------|---------|
| `TestR1PolicySpec` | Construction, validation, auto-generation |
| `TestRegimeDominanceCheckerAND` | AND combinator, missing keys |
| `TestRegimeDominanceCheckerOR` | OR combinator |
| `TestR1SuppressionLogFormat` | All log fields, custom log_tag, no duplicates |
| `TestApplyR1Integrated` | End-to-end with KG/collections, asset scoping |
| `TestRegimeDominanceGateDecorator` | Suppression, passthrough, spec introspection |
| `TestJ1BackwardCompat` | j1 + r1 flags, node suppression, false-positive guards |
| `TestJ1R1SpecExposed` | Module-level spec importability and field values |
| `TestRun011PipelineRegression` | 0 reroutes, 0 reject_conflicted, watchlist ≥ 60, tiers stable, ETH/BTC preserved |

**Total: 37 new tests. All pass.**

---

## Regression Results

- reject_conflicted: **0** ✓ (run_010: 0)
- reroutes: **0** ✓ (run_010: 0)
- watchlist_cards: **60** ✓ (run_010: 60)
- ETH/BTC beta_reversion: **actionable_watch** ✓
- Pre-existing failures: 4 (same as zen-curran baseline, not caused by this run)

---

## Next Steps (Sprint K candidates)

1. **Persistence-oscillation detection** (`persistence_tracker.py`): families
   that oscillate between tiers are a grammar-instability early-warning signal.
   Candidate for Meta-rule R2.

2. **Monitor E1 persistent_aggression** at boundary: if boundary hit is observed
   under funding_extreme+OI regime, apply R1 via `_J2_R1_SPEC` (same signals, new
   chain_type).

3. **PR merge**: crazy-vaughan (Sprint K / run_011) ready for PR to main.
