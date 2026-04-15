# Before / After Policy Map — J1 Special Case → R1 Instance

**Run:** 011 (Sprint K)  
**Change:** J1 inline gate in `chain_grammar.py` refactored to R1 `apply_r1()` call

---

## J1 Before (Sprint J, run_009 — inline in chain builder)

Location: `_e1_transient_aggression_chain` in `chain_grammar.py`

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

**Characteristics:**
- Logic: ad-hoc inline check
- Discoverability: must read the chain body to find it
- Reusability: zero — logic cannot be applied to other chains without copy-paste
- Log format: `j1_discriminative_gate=True` only; no structured R1 metadata
- Test coverage: test_sprint_j.py checks `j1_discriminative_gate=True`

---

## J1 After (Sprint K, run_011 — R1 instance)

### Module-level spec (new):

```python
# In chain_grammar.py — module level

_J1_R1_SPEC = R1PolicySpec(
    chain_type="beta_reversion_transient_aggr",
    regime_signals=["funding_extreme", "oi_accumulation"],
    regime_combinator="AND",
    expected_outcome="beta_reversion",
    contradicting_outcome="positioning_unwind",
    suppression_reason=(
        "funding extreme + OI accumulation both present — "
        "aggression is unwind-context signal, not transient beta_reversion"
    ),
    log_tag="j1_discriminative_gate",  # backward-compat alias
)
```

### Chain body (replaced):

```python
# J1 is now an instance of Meta-rule R1 (Regime Dominance Gate).
# Spec: _J1_R1_SPEC at module level.
if apply_r1(_J1_R1_SPEC, merged_kg, collections, [a1, a2], pair, log):
    return
```

**Characteristics:**
- Logic: delegated to `regime_dominance_gate.py`
- Discoverability: spec is at module level, importable by tooling / tests
- Reusability: full — other chains call `apply_r1(their_spec, ...)` or use `@regime_dominance_gate(...)`
- Log format: `j1_discriminative_gate=True` (compat) + `r1_regime_dominance_gate=True` + full R1 metadata
- Test coverage: test_sprint_j.py still passes (backward compat); test_sprint_k.py adds R1 coverage

---

## Suppression Log Entry Diff

### Before (Sprint J):
```json
{
  "chain": "beta_reversion_transient_aggr",
  "pair": "HYPE/SOL",
  "reason": "contradictory_evidence",
  "detail": "funding extreme + OI accumulation both present — ...",
  "neg_evidence_taxonomy": "contradictory_evidence",
  "j1_discriminative_gate": true
}
```

### After (Sprint K):
```json
{
  "chain": "beta_reversion_transient_aggr",
  "pair": "HYPE/SOL",
  "reason": "contradictory_evidence",
  "detail": "funding extreme + OI accumulation both present — ...",
  "neg_evidence_taxonomy": "contradictory_evidence",
  "r1_regime_dominance_gate": true,
  "r1_chain_type": "beta_reversion_transient_aggr",
  "r1_regime_signals": ["funding_extreme", "oi_accumulation"],
  "r1_expected_outcome": "beta_reversion",
  "r1_contradicting_outcome": "positioning_unwind",
  "j1_discriminative_gate": true
}
```

**New fields:** `r1_regime_dominance_gate`, `r1_chain_type`, `r1_regime_signals`,
`r1_expected_outcome`, `r1_contradicting_outcome`  
**Preserved fields:** all Sprint J fields unchanged

---

## Behavioral Equivalence

| Scenario | Sprint J output | Sprint K output | Same? |
|----------|----------------|-----------------|-------|
| funding_extreme=T AND oi_accum=T | Chain suppressed | Chain suppressed | ✓ |
| funding_extreme=T AND oi_accum=F | Chain proceeds | Chain proceeds | ✓ |
| funding_extreme=F AND oi_accum=T | Chain proceeds | Chain proceeds | ✓ |
| Neither condition met | Chain proceeds | Chain proceeds | ✓ |
| ETH/BTC (quiet regime) | Chain proceeds | Chain proceeds | ✓ |
| Pipeline: SOL confusion | 0 reroutes, 0 reject | 0 reroutes, 0 reject | ✓ |

**Verdict:** Behavioral equivalence confirmed. All Sprint J tests pass unchanged.

---

## How to Apply R1 to a Future Chain

1. Define an `R1PolicySpec` at module level (makes it introspectable):
   ```python
   _MY_R1_SPEC = R1PolicySpec(
       chain_type="my_chain_name",
       regime_signals=["funding_extreme"],   # or any registered signal
       expected_outcome="my_expected_branch",
       contradicting_outcome="dominant_branch_under_regime",
   )
   ```

2a. Inline pattern (existing chains):
   ```python
   def _my_chain(kg, merged_kg, collections, a1, a2, corr_nid, break_score, log):
       if apply_r1(_MY_R1_SPEC, merged_kg, collections, [a1, a2], f"{a1}/{a2}", log):
           return
       ...
   ```

2b. Decorator pattern (new chains, cleaner):
   ```python
   @regime_dominance_gate(
       chain_type="my_chain_name",
       regime_signals=["funding_extreme"],
       ...
   )
   def _my_chain(kg, merged_kg, collections, a1, a2, corr_nid, break_score, log):
       ...  # R1 runs automatically before this
   ```

3. Add test coverage in the relevant test_sprint_*.py:
   - Test suppression fires when all signals present
   - Test chain proceeds when any signal absent
   - Add pipeline regression assertion for 0 reroutes / 0 reject_conflicted
