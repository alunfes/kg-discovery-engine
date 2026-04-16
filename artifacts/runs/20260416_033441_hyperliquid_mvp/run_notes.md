# Run Notes
- Run ID: 20260416_033441_hyperliquid_mvp  Phase: evaluation

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

## Surface Policy (production-shadow)

- Input: 409 → Surfaced: 365 (10.8% pruned)
- action_worthy: 190  attention_worthy: 175
- dropped(null_baseline): 21  archived(baseline_like): 23
- missed_critical: 0  operator_burden: 730.0 items/day
- reviews/day: 2.0  resurface_potential: 23
