<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> claude/thirsty-heisenberg
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison
=======
>>>>>>> claude/sharp-kowalevski
=======
>>>>>>> claude/admiring-clarke
# Alpha vs Shareable Knowledge

## The Secrecy Dimension

Not all discoveries are equal from an information-asymmetry perspective.  The KG engine
classifies outputs on two axes: *value* and *sharability*.

```
                high value
                    |
  private_alpha ----+---- internal_watchlist
                    |
shareable_structure-+---- discard
                    |
                low value
```

## Classification Criteria

### private_alpha

- The hypothesis describes a specific, exploitable edge
- The edge would be reduced or eliminated if widely known
- Examples: exact threshold for a funding reversion trade, a specific pair spread
  convergence pattern with documented entry/exit rules

**Action:** Never publish.  Store encrypted.  Review quarterly for decay.

### internal_watchlist

- The hypothesis is plausible and potentially exploitable but needs more evidence
- Publishing would reduce the edge before it is confirmed
- Examples: a correlation break pattern seen in 2 runs but not yet `reproduced`

**Action:** Track internally.  Run more experiments.  Promote or discard.

### shareable_structure

- The hypothesis describes a structural property of the market
- Publishing does not reduce the edge (or the edge doesn't exist as a direct trade)
- Examples: "Funding extreme + low depth = adverse-selection regime" (widely studied)

**Action:** Suitable for papers, blog posts, open-source.

### discard

- The hypothesis is noise, already widely known, or contradicted by evidence
- Examples: "BTC price correlates with ETH price" (trivially known)

**Action:** Archive with reason.  Do not include in inventory for ranking.

## Secrecy Score Component

The `secrecy` dimension in the score bundle penalises hypotheses that are already
well-known (lower secrecy value).  This keeps the engine focused on discovering
non-obvious structure rather than rediscovering textbook microstructure.

Formula (applied in evaluator):
```
secrecy_score = 1.0  if secrecy_level == private_alpha
              = 0.75 if secrecy_level == internal_watchlist
              = 0.25 if secrecy_level == shareable_structure
              = 0.0  if secrecy_level == discard
```
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
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
>>>>>>> claude/gifted-cray
=======
>>>>>>> claude/thirsty-heisenberg
=======
>>>>>>> claude/elated-lamarr
=======
>>>>>>> claude/gracious-edison
=======
>>>>>>> claude/sharp-kowalevski
=======
>>>>>>> claude/admiring-clarke
