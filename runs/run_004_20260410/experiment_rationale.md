# Experiment Rationale — Run 004

**Date**: 2026-04-10
**Selected Experiment**: H4 verification with mixed-hop KG (strict single-op vs multi-op comparison on fixed inputs)
**Status**: Selected for execution

---

## Decision

**Run 004 will test: H4 provenance-aware evaluation with a purpose-built mixed-hop KG, combined with a strict same-input H1 comparison.**

Two sub-experiments, one run:
1. **H4 fix**: Build `build_mixed_hop_kg()` — a KG designed to generate 1-hop, 2-hop, and 3-hop hypotheses simultaneously. This makes naive and aware scoring differ for the first time.
2. **H1 strict**: Add `compose_cross_domain()` operator that filters compose output to cross-domain paths only. Test C2_xdomain (cross-domain only) vs C1 on the same KG to isolate the cross-domain advantage.

---

## Selection Criteria and Reasoning

### Option A: Strict single-op vs multi-op comparison (same input, same KG) — partial basis for H1

**What it would do**: Run C1 and C2 on identical, fixed input KGs without changing KG size between runs.
**What it addresses**: Removes the KG-expansion confound that makes Run 001–003 cross-run comparisons unclear.
**Why not selected as primary**: H1 has already been tested 3 times with consistent result (~3% gap). Without addressing the cross-domain ratio (42% vs needed ~60%), repeating the same comparison will produce the same FAIL. The KG expansion confound is a documentation issue, not a test design flaw — it doesn't explain why H1 fails.
**Decision**: Include as secondary (H1 strict comparison using compose_cross_domain).

### Option B: Same-domain vs cross-domain comparison (H3) — rejected

**What it would do**: Replicate H3 with a different method or KG.
**Why rejected**: H3 already achieved PASS in Run 003. Re-running H3 provides diminishing returns. The key caveat (tautological scoring) is documented but is not fixable without replacing the heuristic novelty scorer with an external standard — out of scope for Run 004.

### Option C: Provenance-aware vs naive ranking (H4 with mixed-hop KG) — PRIMARY

**What it would do**: Build a KG with explicit 1-hop direct relationships AND 2-hop AND 3-hop transitive paths. This makes naive scoring (all provenance → 0.7) differ from aware scoring (1-hop → 1.0, 2-hop → 0.7, 3-hop → 0.5).
**What it addresses**: The fundamental H4 test design flaw — the degenerate all-2hop condition that makes the test uninformative.
**Why selected**: This is the only H4 test that can provide a meaningful verdict. The infrastructure already exists; only the input KG is missing. Minimal code change required (one new toy_data function + one new runner function). Result is immediately interpretable.

---

## What Run 004 Will Produce

### H4 with Mixed-hop KG

- New function: `build_mixed_hop_kg()` in `toy_data.py`
  - ~10 nodes, explicit 1-hop paths (A→B direct, already exists in KG) AND 2-hop paths (A→B→C) AND 3-hop paths (A→B→C→D)
  - compose() on this KG generates candidates at multiple depths
  - naive: 1-hop→0.7, 2-hop→0.7, 3-hop→0.7 (flat)
  - aware: 1-hop→1.0, 2-hop→0.7, 3-hop→0.5 (depth-sensitive)
  - Gold standard: rank 1-hop > 2-hop > 3-hop (shorter = more direct support)

- New function: `run_h4_mixed_hop()` in `run_experiment.py`
  - Same structure as run_h4_provenance_aware() but uses mixed_hop_kg
  - H4 passes if spearman(aware_ranks, gold) > spearman(naive_ranks, gold)

### H1 with compose_cross_domain

- New function: `compose_cross_domain(kg, max_depth=3)` in `operators.py`
  - Wrapper around compose() that filters to hypotheses where subject.domain ≠ object.domain
  - Cleaner test of "does cross-domain only pipeline beat single-op?"

- New condition: `run_condition_c2_xdomain()` in `run_experiment.py`
  - Uses align → union → compose_cross_domain on biology+chemistry KGs
  - Directly tests whether cross-domain filtering alone produces 10% improvement

---

## Rejected Alternatives

### compose_cross_domain alone (without H4 fix)
- Would address H1 partially, but H1 has been tested 3× with consistent ~3% gap
- compose_cross_domain filtering would reduce candidate count further (subset of compose)
- Unlikely to flip H1 to PASS on mean total score — novelty improves but plausibility degrades
- Less informative than H4 fix given H4 is completely untested

### Increasing cross-domain ratio via more toy data
- More KG expansion risks further confounding cross-run comparisons
- The problem is not data size but test design clarity
- Run 003 already expanded to 12-node KGs; further expansion adds complexity without new insight

### Replacing testability placeholder
- Would require either an NLP-based testability measure (external dependency, violates project rules) or a hand-coded heuristic
- Any new heuristic would be as arbitrary as the current 0.6 constant
- Better to document the limitation than introduce an untested replacement

---

## Risk Assessment

| Risk | Probability | Mitigation |
|------|-------------|------------|
| H4 still fails with mixed-hop KG | Medium | If tie persists, investigate Spearman sensitivity; check if traceability weight (0.15) is too small to move rankings |
| compose() skips 1-hop paths (len<3 filter) | High | compose() currently requires path length ≥3 (skips direct 2-element paths). Need to ensure mixed-hop KG generates enough 3+ element paths, or relax path length constraint for 1-hop detection |
| compose_cross_domain returns too few candidates | Medium | May need to relax thresholds or accept smaller candidate pool for H1 cross-domain condition |
| New tests fail | Low | Tests are written alongside implementation; deterministic execution |
