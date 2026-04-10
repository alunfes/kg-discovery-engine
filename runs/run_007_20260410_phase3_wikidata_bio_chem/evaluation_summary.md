# Evaluation Summary — Phase 3 Run 1

| Condition | Pipeline | N | mean_total | mean_novelty | unique_to_multi |
|-----------|----------|---|-----------|-------------|-----------------|
| A_bio_only | single_op | 50 | 0.7266 | 0.8000 | — |
| A_bio_only | multi_op | 50 | 0.7266 | 0.8000 | 0 |
| B_chem_only | single_op | 4 | 0.7200 | 0.8000 | — |
| B_chem_only | multi_op | 4 | 0.7200 | 0.8000 | 0 |
| C_sparse_bridge | single_op | 60 | 0.7240 | 0.8000 | — |
| C_sparse_bridge | multi_op | 54 | 0.7261 | 0.8000 | 4 |
| D_dense_bridge | single_op | 67 | 0.7220 | 0.8000 | — |
| D_dense_bridge | multi_op | 54 | 0.7261 | 0.8000 | 4 |

## Reachability (most important metric)
- **A_bio_only**: unique_to_multi_op=0, contribution_rate=0.0000
- **B_chem_only**: unique_to_multi_op=0, contribution_rate=0.0000
- **C_sparse_bridge**: unique_to_multi_op=4, contribution_rate=0.0741
- **D_dense_bridge**: unique_to_multi_op=4, contribution_rate=0.0741