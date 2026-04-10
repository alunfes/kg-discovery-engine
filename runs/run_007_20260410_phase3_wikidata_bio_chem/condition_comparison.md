# Condition Comparison — Phase 3 Run 1

## H1' analysis: multi-op advantage as function of bridge density

| Condition | bridge_density | Cohen's d | unique_rate | multi_op_wins |
|-----------|---------------|-----------|------------|---------------|
| A_bio_only | 0.0000 | 0.0000 | 0.0000 | False |
| B_chem_only | 0.0000 | 0.0000 | 0.0000 | False |
| C_sparse_bridge | 0.0500 | 0.0000 | 0.0741 | False |
| D_dense_bridge | 0.1461 | 0.0000 | 0.0741 | False |

**H1' supported**: False
**Interpretation**: H1' not confirmed — advantage pattern does not peak at sparse bridges

## H3' analysis: structural distance across conditions
- **A_bio_only**: cross_hops=0.0, same_hops=2.0, structural_dist=False
- **B_chem_only**: cross_hops=0.0, same_hops=2.0, structural_dist=False
- **C_sparse_bridge**: cross_hops=2.0, same_hops=2.0, structural_dist=False
- **D_dense_bridge**: cross_hops=2.0, same_hops=2.0, structural_dist=False