# Next Actions — Run 008

## Summary of Findings

- H1'': PASS — alignment enables reachability of new pairs
- H3'': PASS — deep compose (3-hop+) produces candidates unreachable by shallow multi-op
- H4: FAIL — provenance-aware demotes deep candidates
- Deep-only candidates: 60
- Drift rate in 3-hop+ bucket: 66.7%

## Recommended Next Steps

1. **If deep_only > 0 and drift_rate < 0.5**: deep compose is producing real novel candidates
   → Run 009: validate deep-only candidates against literature / external KG
2. **If drift_rate >= 0.5 in deep bucket**: semantic drift is dominating deep paths
   → Run 009: add relation-type filtering to prune weak-relation paths before compose
3. **If H4 provenance-aware promotes deep candidates**: incorporate into default rubric
   → Update EvaluationRubric default to provenance_aware=True
4. **If H1'' confirmed**: alignment-induced reachability is the core multi-op value
   → Focus future experiments on alignment quality improvement
5. **If H3'' confirmed**: cross-domain deep paths exist without bonus manipulation
   → Phase 4: scale to larger Wikidata dataset (500+ nodes) to test robustness

## Experiment Hygiene

- random_seed=42 was used throughout
- All conditions derived from same Condition C (sparse bridge) base data
- No external API calls were made
