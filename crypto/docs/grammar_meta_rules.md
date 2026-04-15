# Grammar Meta-Rules

Meta-rules are policies that govern *when and how* grammar chain builders should
activate or suppress, independently of the chains' internal evidence logic.
They address failure modes that are structural (not evidence-specific) and
recur across multiple chain types.

Meta-rules sit one level above chain grammar:

```
Chain Grammar (E1/E2/D1/flow_continuation)
    ↑ governed by
Grammar Meta-Rules (R1, R2, ...)
    ↑ formalized in
regime_dominance_gate.py, [future meta-rule files]
```

---

## R1 — Regime Dominance Gate

**Status:** Active (Sprint K, run_011)  
**Implementation:** `crypto/src/kg/regime_dominance_gate.py`  
**First instantiation:** J1 gate (Sprint J, run_009)

### Problem

Grammar chains activate when evidence crosses a minimum threshold. Near-threshold
activations (borderline evidence) are weak. If a strong contradicting regime is
simultaneously present, the weak chain produces a card that conflicts with the
dominant regime evidence downstream — causing `reject_conflicted` decisions and
spurious reroutes.

### Rule

> **Suppress a grammar chain when:**
> 1. The chain's activation evidence is in its borderline / minimum zone, AND
> 2. A named set of regime signals is co-present (in AND or OR combination), AND
> 3. Those regime signals are associated with an outcome that contradicts the
>    chain's expected outcome.

### Interface

```python
from ..kg.regime_dominance_gate import R1PolicySpec, apply_r1, regime_dominance_gate

# Pattern A: inline (preferred for existing chains)
_MY_SPEC = R1PolicySpec(
    chain_type="chain_name",
    regime_signals=["funding_extreme", "oi_accumulation"],
    expected_outcome="beta_reversion",
    contradicting_outcome="positioning_unwind",
)

def _my_chain(kg, merged_kg, collections, a1, a2, corr_nid, break_score, log):
    if apply_r1(_MY_SPEC, merged_kg, collections, [a1, a2], f"{a1}/{a2}", log):
        return
    ...

# Pattern B: declarative decorator (preferred for new chains)
@regime_dominance_gate(
    chain_type="chain_name",
    regime_signals=["funding_extreme", "oi_accumulation"],
    expected_outcome="beta_reversion",
    contradicting_outcome="positioning_unwind",
)
def _my_chain(kg, merged_kg, collections, a1, a2, corr_nid, break_score, log):
    ...
```

### Built-in Regime Signals

| Signal | Condition |
|--------|-----------|
| `funding_extreme` | `FundingNode(is_extreme=True)` present for any pair asset |
| `oi_accumulation` | `OIState(is_accumulation=True)` present for any pair asset |

Register custom signals with `@register_regime_resolver("my_signal")`.

### Active R1 Instances

| ID | Chain | Signals | Outcome suppressed | Location |
|----|-------|---------|-------------------|----------|
| J1 | `beta_reversion_transient_aggr` | `funding_extreme AND oi_accumulation` | beta_reversion | `chain_grammar._J1_R1_SPEC` |

### Candidates for Future R1 Application

| Chain | Trigger condition | Priority |
|-------|-------------------|----------|
| E1 persistent_aggression | boundary hit under funding_extreme + OI | Medium (monitor) |
| flow_continuation | premium boundary under extreme OI | Low (no confusion seen) |

### Over-Suppression Guard

Do NOT apply R1 to:
- E2 chains (they fire *because* funding_extreme is present — R1 would suppress them wrongly)
- OR combinators with broad signals (over-suppresses)
- Chains without clear contradicting-regime semantics

Full discussion: `crypto/artifacts/runs/run_011_r1_formalization/rule_spec.md`

---

## Future Meta-Rules (candidates)

| ID | Name | Status | Problem addressed |
|----|------|--------|-------------------|
| R2 | Persistence Oscillation Guard | Candidate | Cards that flip tier across runs signal grammar instability |
| R3 | Soft-Gate Cascade Prevention | Candidate | Chains with two consecutive soft-gated nodes amplify uncertainty |

These are documented as candidates only; no implementation yet.
