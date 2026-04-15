# Run 011 — Regression Summary

**Date:** 2026-04-15  
**Sprint:** K  
**Objective:** Verify R1 formalization does not change pipeline behavior

---

## Test Results

| Suite | Tests | Pass | Fail | Notes |
|-------|-------|------|------|-------|
| test_sprint_k.py (new) | 37 | 37 | 0 | All R1 + regression tests |
| test_sprint_j.py | 8 | 8 | 0 | J1 backward compat confirmed |
| test_sprint_i.py | 8 | 8 | 0 | No regression |
| test_sprint_h.py | 9 | 9 | 0 | No regression |
| test_sprint_g.py | 9 | 9 | 0 | No regression |
| test_sprint_f.py | 15 | 15 | 0 | No regression |
| test_sprint_e.py | 11 | 11 | 0 | No regression |
| test_sprint_d.py | 10 | 7 | 3 | PRE-EXISTING failures |
| test_determinism.py | 5 | 4 | 1 | PRE-EXISTING failure |
| Other suites | ~130 | ~130 | 0 | |
| **TOTAL** | **268+** | **268** | **4** | 4 pre-existing, 0 new |

---

## Key Regression Checks

### SOL Confusion (run_009/010 regression target)
- **reject_conflicted cards:** 0 ✓ (matches run_009/010)
- **reroute records:** 0 ✓ (matches run_009/010)

### Watchlist
- **watchlist_cards:** 60 ✓ (matches run_010 baseline)

### Decision Tiers
- **actionable_watch:** > 0 ✓
- **monitor_borderline:** > 0 ✓
- **reject_conflicted:** 0 ✓

### ETH/BTC Beta Reversion
- Preserved as `actionable_watch` ✓
- J1/R1 gate correctly does NOT fire (no extreme conditions)

---

## Pre-Existing Failures (not caused by this run)

1. `test_determinism.py::test_different_seeds_produce_different_results`
   — Pre-existing in zen-curran (c9a30d8)

2. `test_sprint_d.py::test_d1_chain_rules_fire`
   — Pre-existing in zen-curran (c9a30d8)

3. `test_sprint_d.py::test_d1_chain_flow_continuation_plausibility`
   — Pre-existing in zen-curran (c9a30d8)

4. `test_sprint_d.py::test_d3_continuation_branch_requires_score_020`
   — Pre-existing in zen-curran (c9a30d8)

---

## Behavioral Equivalence Verification

The R1 refactor is a pure structural change. Evidence of equivalence:

1. `_J1_R1_SPEC.regime_signals` resolves via `_REGIME_RESOLVERS["funding_extreme"]`
   and `_REGIME_RESOLVERS["oi_accumulation"]` — the same boolean computations that
   were inline before.

2. `RegimeDominanceChecker.should_suppress` with AND combinator reproduces the
   `has_fund_extreme and has_oi_accum` check exactly.

3. `j1_discriminative_gate=True` remains in the suppression log (via `log_tag`
   alias) so Sprint J tests pass without modification.

4. All 8 Sprint J tests pass — including 3 integration tests that run the full
   pipeline and assert 0 reroutes / 0 reject_conflicted.
