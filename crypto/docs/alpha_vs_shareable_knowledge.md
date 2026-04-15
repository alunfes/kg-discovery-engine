# Alpha vs. Shareable Knowledge — Crypto Subtree Reference

The canonical secrecy classification framework is in:
`docs/alpha_vs_shareable_knowledge.md` (repo root docs/)

This document records HYPE-specific classification rules and examples.

## HYPE-Specific Classification Rules

### Additional private_alpha conditions
A hypothesis is private_alpha if:
- It involves HYPE as a primary asset
- actionability_score >= 0.7 AND novelty_score >= 0.6
- The path contains at least one directional relation (leads_to, precedes_move_in, activates)
- The claim is specific enough that a reader could construct an entry condition

### Additional discard conditions
- Any hypothesis of the form "HYPE:X co_occurs_with HYPE:X" (tautology)
- Any cross-asset hypothesis where subject and object have the same state type
  (e.g., HYPE:vol_burst → BTC:vol_burst — this is the obvious correlation, not novel)
- Any pair hypothesis with provenance through >8 hops (too deep to be actionable)

## HYPE-Specific Shareable Structure Examples

These are appropriate for external publication or academic discussion:
- "Hyperliquid funding rates exhibit higher volatility than comparable perp venues"
- "HYPE price momentum tends to follow BTC momentum with a structural lag"
- "During high-funding regimes on Hyperliquid, cross-asset correlation compression
  is observed before large directional moves"
- "The Pair/RV KG operator pipeline discovers N% more cross-asset hypotheses
  than the single-asset microstructure baseline"

## Version Control Enforcement

Files containing private_alpha card content are excluded from git commits:
- `crypto/artifacts/runs/*/output_candidates_full.json` (contains private_alpha)
- `crypto/artifacts/runs/*/hypothesis_store/private_alpha/` directory

The committed version `output_candidates.json` has private_alpha cards redacted.
