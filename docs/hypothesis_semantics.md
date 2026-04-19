# Hypothesis Semantics — Design Note

**Date**: 2026-04-19
**Status**: Foundation implemented, not yet connected to live pipeline

## Why Hypothesis Nodes Are First-Class Objects

The current pipeline produces HypothesisCards as output artifacts: immutable records of
discovered patterns. Cards are useful for logging but lack three properties needed for
a hypothesis operating system:

1. **Lifecycle**: Cards are static. Hypotheses transition through states
   (candidate → active → invalidated / rerouted / archived).
2. **Contradiction**: Cards have scores but no explicit contradiction mechanism.
   A high-scoring card with strong contradicting evidence is still "high-scoring."
3. **Competition**: Cards don't know about each other. Two cards explaining the same
   market state can't be compared, and the system can't recommend which to follow
   or what additional observation would distinguish them.

HypothesisNode addresses all three by making evidence, contradiction, invalidation,
and alternatives first-class attributes rather than derived metrics.

## How Hypotheses Differ from Signals / Cards / Events

| Concept | What it is | Lifecycle | Knows about alternatives |
|---------|-----------|-----------|------------------------|
| StateEvent | A detected market condition | None (fire-and-forget) | No |
| HypothesisCard | A scored discovery record | Immutable | No |
| ShadowSignal | A P&L-trackable directional bet | None (resolved after half-life) | No |
| **HypothesisNode** | A falsifiable claim about the market | Managed (candidate→active→...) | Yes |

The key distinction: **events are observations, cards are records, signals are bets,
hypotheses are claims that can be supported, contradicted, and replaced.**

## Semantic Relations

Eight new relation types extend the existing 14+ observation-level relations:

| Relation | Direction | Meaning |
|----------|-----------|---------|
| `supports` | evidence → hypothesis | This evidence strengthens the hypothesis |
| `contradicts` | evidence → hypothesis | This evidence weakens the hypothesis |
| `reroutes_to` | hypothesis → hypothesis | This hypothesis is better explained by another |
| `invalidates` | condition → hypothesis | This condition has falsified the hypothesis |
| `depends_on` | hypothesis → condition | This hypothesis requires this condition to hold |
| `explains` | hypothesis → observation | This hypothesis accounts for this observation |
| `co_occurs_with` | hypothesis ↔ hypothesis | These hypotheses coexist as alternatives |
| `requires_observation` | hypothesis → metric | This metric would help resolve uncertainty |

These compose with existing relations. For example:
- `exhibits_funding` (observation) + `supports` (semantic) links a funding observation to a hypothesis
- `transitions_to` (regime) + `invalidates` (semantic) links a regime shift to hypothesis invalidation

## How Rerouting and Contradiction Work

**Contradiction** is incremental: each contradicting evidence adds to `contradiction_pressure`.
When `contradiction_pressure` exceeds `evidence_strength`, the hypothesis's `net_evidence()`
goes to zero and it is no longer actionable.

**Rerouting** is structural: when hypothesis A's evidence is better explained by hypothesis B,
A gets status=REROUTED and a `reroutes_to` edge points to B. This preserves the evidence
trail while redirecting attention to the stronger interpretation.

Neither operation destroys data. Invalidated and rerouted hypotheses remain in the graph
for postmortem analysis and pattern learning.

## Invalidation Conditions

Each hypothesis can carry explicit `InvalidationCondition` objects:

```python
InvalidationCondition(
    description="funding rate normalizes within 2h",
    metric="funding_rate_1h",
    operator="lt",
    threshold=0.0001,
    window_min=120.0,
)
```

These are not automatically evaluated yet (Phase 3 work), but their presence enables:
1. Manual review of "what would make this hypothesis wrong"
2. Future automated invalidation when regime graph is connected
3. Active experiment planning ("which observation would resolve this fastest")

## Connection to Future Phases

### Regime Graph (Phase 3)
HypothesisNode.regime_dependency specifies which regimes the hypothesis requires.
When the regime graph detects a regime shift, hypotheses depending on the old regime
can be automatically marked for re-evaluation or invalidation.

### Failure Graph (Phase 4)
Invalidated hypotheses become nodes in the failure graph. Patterns of invalidation
(e.g., "momentum hypotheses consistently fail during transition regimes") become
learnable failure knowledge.

### Research KG (Phase 5)
Research claims (from papers, review memos) map to hypothesis templates.
A research claim like "funding-spot arbitrage tends to normalize within 8h"
becomes a reusable hypothesis template with pre-configured invalidation conditions.

### Observation Planner (Phase 6)
`next_observations` and `requires_observation` edges feed the planner.
The planner ranks additional data collection by information gain:
"if we observe X, how much does it reduce uncertainty between competing hypotheses?"

## Compatibility Layer

`hypothesis_builder.py` provides adapters:
- `card_to_hypothesis()`: converts existing HypothesisCard → HypothesisNode
- `event_to_hypothesis()`: creates hypothesis candidates directly from StateEvents
- `link_alternatives()`: connects competing hypotheses bidirectionally
- `add_contradiction()`: records contradicting evidence with pressure accumulation

These adapters allow gradual migration: the live pipeline continues producing cards,
and the hypothesis layer wraps them without requiring pipeline changes.

## What Was Deliberately NOT Changed

- HypothesisCard is unchanged (backward compatible)
- KGNode / KGEdge / KGraph are unchanged (hypothesis nodes use them via `to_kg_node()`)
- Shadow trading pipeline is untouched
- Live pipeline flow (event → card → signal) is untouched
- Existing 14+ relation types are preserved; new semantic relations are additive
