# Run Notes

- Run ID: RUN-20260411-161248
- Started: 2026-04-11T16:12:48Z
- Completed: N/A
- Phase: evaluation

## KG Sizes

- microstructure: 4 nodes, 0 edges
- cross_asset: 4 nodes, 0 edges
- execution: 11 nodes, 4 edges
- regime: 6 nodes, 8 edges

## Operator Pipeline

1. Compose each KG individually (intra-domain)
2. align + union microstructure + cross_asset -> compose
3. align + union execution + regime -> compose
4. regime - microstructure difference -> compose

## Results

- Raw candidates: 16
- Hypothesis cards: 16

### Secrecy Distribution

- internal_watchlist: 8
- shareable_structure: 8
