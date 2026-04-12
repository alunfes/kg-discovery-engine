# Run Notes
- Run ID: 20260411_161857_hyperliquid_mvp  Phase: evaluation

## KG Sizes

- microstructure: 24 nodes, 89 edges
- cross_asset: 24 nodes, 104 edges
- execution: 27 nodes, 28 edges
- regime: 6 nodes, 8 edges

## Operator Pipeline

1. Compose each KG individually (intra-domain)
2. align+union microstructure+cross_asset -> compose
3. align+union execution+regime -> compose
4. regime-microstructure difference -> compose

## Results

- Raw candidates: 299
- Hypothesis cards: 299

### Secrecy Distribution

- internal_watchlist: 215
- private_alpha: 84
