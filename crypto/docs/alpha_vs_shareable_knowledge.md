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
