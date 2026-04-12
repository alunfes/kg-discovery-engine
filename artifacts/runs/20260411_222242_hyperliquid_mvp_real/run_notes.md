# Run Notes
- Run ID: 20260411_222242_hyperliquid_mvp_real  Phase: evaluation

## KG Sizes

- microstructure: 16 nodes, 35 edges
- cross_asset: 16 nodes, 52 edges
- execution: 22 nodes, 22 edges
- regime: 6 nodes, 7 edges

## Operator Pipeline

1. Compose each KG individually (intra-domain)
2. align+union microstructure+cross_asset -> compose
3. align+union execution+regime -> compose
4. regime-microstructure difference -> compose

## Results

- Raw candidates: 103
- Hypothesis cards: 103

### Secrecy Distribution

- internal_watchlist: 28
- private_alpha: 19
- shareable_structure: 56
