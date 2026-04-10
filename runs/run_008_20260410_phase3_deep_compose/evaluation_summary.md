# Evaluation Summary — Run 008

## Pipeline Statistics

| Pipeline | N | Mean Total | Mean Novelty | Min | Max |
|----------|---|-----------|--------------|-----|-----|
| R1 single-op/shallow | 60 | 0.724 | 0.8 | 0.705 | 0.735 |
| R2 multi-op/shallow | 54 | 0.7261 | 0.8 | 0.705 | 0.735 |
| R3 multi-op/deep | 114 | 0.6953 | 0.8 | 0.615 | 0.735 |

## Reachability

| Metric | Value |
|--------|-------|
| R1 total pairs | 60 |
| R2 total pairs | 54 |
| R3 total pairs | 114 |
| Unique to R2 vs R1 | 4 |
| Unique to R3 vs R2 | 60 |
| Deep-only (R3 only) | 60 |

## Hypothesis Verdicts

- **H1''** (alignment enables unreachable paths): PASS — alignment enables reachability of new pairs
- **H3''** (deep compose finds new cross-domain candidates): PASS — deep compose (3-hop+) produces candidates unreachable by shallow multi-op
- **H4** (provenance-aware ranking improves deep top-k): FAIL — provenance-aware demotes deep candidates
