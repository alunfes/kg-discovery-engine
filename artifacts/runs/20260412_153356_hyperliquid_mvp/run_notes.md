# Run Notes
- Run ID: 20260412_153356_hyperliquid_mvp  Phase: evaluation

## KG Sizes

- microstructure: 28 nodes, 179 edges
- cross_asset: 28 nodes, 132 edges
- execution: 31 nodes, 36 edges
- regime: 6 nodes, 8 edges

## Operator Pipeline

1. Compose each KG individually (intra-domain)
2. align+union microstructure+cross_asset -> compose
3. align+union execution+regime -> compose
4. regime-microstructure difference -> compose

## Results

- Raw candidates: 409
- Hypothesis cards: 409

### Secrecy Distribution

- internal_watchlist: 88
- private_alpha: 102
- shareable_structure: 219
