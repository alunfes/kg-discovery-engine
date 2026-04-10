# Phase 3 Run 008 — Experiment Plan

**Date**: 2026-04-10
**Session**: stupefied-darwin
**Hypothesis focus**: H1'', H3'', H4

---

## Background: Run 007 Findings

Run 007 tested 4 bridge-density conditions (A/B same-domain, C/D cross-domain):
- same-domain (A/B): unique_to_multi = 0 — alignment provides no advantage within one domain
- cross-domain (C/D): unique_to_multi = 4 — alignment creates 2-hop shortcuts
- bridge density (5% vs 15%) did NOT differentiate: C = D = 4 unique candidates
- **Key corrected finding**: multi-op advantage depends on aligned shared concepts (ADP/ATP merge),
  not on bridge density

**What Run 007 could NOT test:**
- max_depth > 3 (only 2-hop paths were generated)
- 3-hop+ cross-domain novelty (H3'')
- provenance-aware ranking on deep candidates (H4 under deep composition)

---

## Hypothesis Restatements for Run 008

### H1'' (refined from H1')
> Multi-op advantage is an alignment-induced reachability gain.
> Value = (subject, object) pairs uniquely reachable via alignment-mediated paths.
> NOT measured as average score improvement.

### H3'' (refined from H3')
> Cross-domain novelty is only detected in deep composition chains (3-hop+).
> Shallow (2-hop) cross-domain candidates are alignment-enabled shortcuts, not novel chains.

### H4 (re-test under deep composition)
> Provenance-aware ranking improves top-k quality specifically for deep-path candidates.
> Under shallow compose, all 2-hop paths receive the same naive traceability (0.7),
> making naive = provenance-aware. Deep paths provide differentiation opportunity.

---

## Experiment Design

### Condition
Condition C (sparse bridge, bio+chem). Chosen because:
- Fewer explicit cross-domain bridges → more reliance on alignment mechanism
- Cleanest signal for H1'' (alignment contribution vs bridge contribution)

### 5 Result Sets

| ID | Pipeline | max_depth | Ranking | Purpose |
|----|----------|-----------|---------|---------|
| R1 | single-op | 3 (2-hop max) | naive | Baseline |
| R2 | multi-op  | 3 (2-hop max) | naive | Replicate Run 007 shallow result |
| R3 | multi-op  | 9 (5-hop max) | naive | Deep composition candidates |
| R4 | multi-op  | 9 (5-hop max) | naive  | Same as R3, explicit naive label |
| R5 | multi-op  | 9 (5-hop max) | provenance-aware | H4 test |

R3 = R4 (identical candidates, same rubric). R5 rescores R3/R4 with provenance_aware=True.

### depth param → max hop count mapping

| max_depth | Max hop count |
|-----------|--------------|
| 3 | 2 |
| 5 | 3 |
| 7 | 4 |
| 9 | 5 |

### Tracking Fields (per candidate)

- `path_length`: int (hop count)
- `operator_chain`: list[str]
- `alignment_used`: bool
- `alignment_count`: int (merged nodes in path)
- `merged_nodes_used`: list[str]
- `reachable_by_single`: bool
- `uniqueness_class`: one of {reachable_by_single, reachable_only_by_multi,
  reachable_only_by_alignment, reachable_only_by_deep_compose}
- `effective_path_length_after_alignment`: path_length minus aligned nodes in path
- `drift_flags`: list[str]
- `semantic_drift_score`: float [0,1]

### Semantic Drift Heuristics

Three binary flags → drift_score = n_flags / 3:
1. `relation_repetition`: same relation type appears 2+ times in path
2. `low_specificity_relations`: all relations are weak (relates_to, associated_with, ...)
3. `weakly_typed_intermediates`: all intermediate nodes have generic labels (process, entity, ...)

### Required Analyses

1. Depth bucket (1-hop, 2-hop, 3-hop, 4-5-hop) × {count, promising, novelty, drift, cross-domain}
2. Reachability: R1 vs R2 vs R3 unique pairs
3. Ranking comparison (R4 naive vs R5 provenance-aware): Jaccard, promotion/demotion of deep candidates
4. Hypothesis verdicts: H1'', H3'', H4
