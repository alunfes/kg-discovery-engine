# Run Notes
- Run ID: 20260411_224015_hyperliquid_mvp_real  Phase: evaluation

## KG Sizes

- microstructure: 21 nodes, 56 edges
- cross_asset: 21 nodes, 68 edges
- execution: 27 nodes, 28 edges
- regime: 6 nodes, 8 edges

## Operator Pipeline

1. Compose each KG individually (intra-domain)
2. align+union microstructure+cross_asset -> compose
3. align+union execution+regime -> compose
4. regime-microstructure difference -> compose

## Results

- Raw candidates: 178
- Hypothesis cards: 178

### Secrecy Distribution

- internal_watchlist: 39
- private_alpha: 34
- shareable_structure: 105
