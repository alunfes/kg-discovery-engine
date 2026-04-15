# R1 Formal Specification — Regime Dominance Gate

**Rule ID:** R1  
**Status:** Formalized (Sprint K, run_011)  
**First instantiation:** J1 (Sprint J, run_009)  
**Implementation:** `crypto/src/kg/regime_dominance_gate.py`

---

## 1. Problem Statement

Grammar chains activate when their evidence crosses a minimum threshold. When the
evidence is borderline (at or near the minimum), the activation is weak — the chain
fires, but the underlying signal is marginal. If simultaneously a strong contradicting
regime is present, the weak chain activation will produce a hypothesis card that
conflicts with the dominant regime evidence. This conflict propagates downstream as
`reject_conflicted` decisions and spurious reroutes.

**R1 prevents this by suppressing borderline activations when a dominant contradicting
regime is co-present.**

---

## 2. Formal Definition

### 2.1 Boundary-Activated Chain

A chain C is **boundary-activated** for a pair (a1, a2) when:
- C has cleared its minimum activation threshold (it would fire normally), AND
- The activation evidence is in the minimal / borderline zone rather than strongly
  confirming. For each chain type, the "borderline zone" is defined by its specific
  threshold parameters (e.g., burst_count ∈ [1, 4] for E1-transient_aggression).

The key property: a boundary-activated chain produces a hypothesis card, but the
card's evidence strength is dominated by the contradicting regime if present.

### 2.2 Dominant Regime Context

A regime R is **dominant** for a pair (a1, a2) when:
- One or more named regime signals are present for the assets in the pair, AND
- The signals match the pattern defined in an R1PolicySpec (AND or OR combinator).

**Built-in regime signals** (auto-resolved from KG / collections):
| Signal | Resolution | Meaning |
|--------|------------|---------|
| `funding_extreme` | Any `FundingNode(is_extreme=True)` for the pair's assets | Extreme funding rate — strong positioning signal |
| `oi_accumulation` | Any `OIState(is_accumulation=True)` in collections | Active OI build — strong unwind risk signal |

Additional signals can be registered via `register_regime_resolver(signal_name)`.

### 2.3 Contradicting Regime

A regime contradicts a chain's expected outcome when:
- The chain is expected to produce branch B (e.g., `beta_reversion`), AND
- The dominant regime signals are associated with a different branch B' (e.g.,
  `positioning_unwind`), AND
- Cards from B and B' for the same pair are structurally incompatible (they cannot
  both be actionable at the same time).

### 2.4 Suppression Action

When R1 triggers:
1. The chain body does **not** execute (no KG nodes/edges are created).
2. A structured suppression log entry is appended with:
   - `r1_regime_dominance_gate: True` — R1 tag (always present)
   - `chain`: chain type identifier
   - `pair`: asset pair
   - `reason: "contradictory_evidence"`
   - `neg_evidence_taxonomy: "contradictory_evidence"`
   - `r1_regime_signals`: the specific signals that triggered suppression
   - `r1_expected_outcome`: suppressed chain's normal outcome
   - `r1_contradicting_outcome`: dominant regime's outcome
   - `detail`: human-readable suppression reason
3. Optional chain-specific alias key (e.g., `j1_discriminative_gate: True`) for
   backward compatibility.

---

## 3. R1PolicySpec Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `chain_type` | `str` | Yes | Chain identifier (used as `chain` in log) |
| `regime_signals` | `list[str]` | Yes | Signal names to check |
| `regime_combinator` | `"AND"\|"OR"` | No (AND) | How to combine multiple signals |
| `expected_outcome` | `str` | No | Chain's normal branch label |
| `contradicting_outcome` | `str` | No | Regime-dominant branch label |
| `suppression_reason` | `str` | No | Log detail text (auto-generated if empty) |
| `log_tag` | `str` | No | Extra alias key in log (backward compat) |

---

## 4. Interface Summary

### Inline (chain builder pattern)
```python
from ..kg.regime_dominance_gate import R1PolicySpec, apply_r1

_MY_R1_SPEC = R1PolicySpec(
    chain_type="my_chain",
    regime_signals=["funding_extreme", "oi_accumulation"],
    expected_outcome="beta_reversion",
    contradicting_outcome="positioning_unwind",
)

def _my_chain(kg, merged_kg, collections, a1, a2, corr_nid, break_score, log):
    if apply_r1(_MY_R1_SPEC, merged_kg, collections, [a1, a2], f"{a1}/{a2}", log):
        return
    # ... normal chain logic ...
```

### Declarative decorator (new chains)
```python
from ..kg.regime_dominance_gate import regime_dominance_gate

@regime_dominance_gate(
    chain_type="my_new_chain",
    regime_signals=["funding_extreme"],
    expected_outcome="beta_reversion",
    contradicting_outcome="positioning_unwind",
)
def _my_new_chain(kg, merged_kg, collections, a1, a2, corr_nid, break_score, log):
    # R1 check runs automatically; body only executes if R1 does not fire
    ...
```

---

## 5. Over-Suppression Risk

R1 must not be applied unconditionally to all chains. Cases where R1 should NOT
be applied:

1. **Chains whose expected outcome IS the positioning_unwind branch (E2 chains)**:
   E2 chains produce positioning_unwind cards. Applying R1 with `funding_extreme`
   as a signal to E2 would suppress the very chains that should fire under that
   signal. R1 is for the *contradicting* direction only.

2. **Chains with strong (non-boundary) activation evidence**: If burst_count = 20
   (clearly persistent), the evidence is not borderline. The R1 spec can be
   restricted to boundary-only firing via future threshold-range checking if
   needed (the current design applies R1 regardless of activation strength within
   the chain's valid range).

3. **OR combinator with broad signals**: Using OR with many common signals would
   suppress chains too aggressively. Use AND for precision.

4. **Novel chains without clear contradicting-regime semantics**: If it's unclear
   what regime contradicts the chain, do not add R1 — the risk of over-suppression
   is higher than the benefit.

---

## 6. Existing R1 Instances

| ID | Chain | Signals (combinator) | Suppresses | File |
|----|-------|---------------------|------------|------|
| J1 | `beta_reversion_transient_aggr` | `funding_extreme AND oi_accumulation` | `beta_reversion` card when unwind regime dominates | `chain_grammar.py:_J1_R1_SPEC` |

---

## 7. Candidates for Future R1 Application

| Chain | Threshold | Candidate Signals | Priority |
|-------|-----------|-------------------|----------|
| E1 persistent_aggression | persistence_min (TBD) | `funding_extreme AND oi_accumulation` | Medium — monitor; not yet hit boundary |
| flow_continuation | premium_min (TBD) | `oi_accumulation AND NOT funding_extreme` | Low — no confusion observed |
