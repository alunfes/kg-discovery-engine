# Experiment Rationale — Run 008

## Background

Run 007 established:
- same-domain (A/B): unique_to_multi = 0 (alignment provides no advantage)
- cross-domain (C/D): unique_to_multi = 4 (alignment creates 2-hop shortcuts)
- bridge density (5% vs 15%) did NOT affect the result
- The dominant mechanism is alignment-induced path shortening, not bridge density

## Run 008 Goals

1. Test whether deeper compose (3-5 hop) discovers genuinely new cross-domain candidates (H3'')
2. Test whether provenance-aware ranking improves top-k quality for deep paths (H4)
3. Separate alignment-induced candidates from mere chain explosion

## Condition Choice

Using Condition C (sparse bridge): more reliance on alignment mechanism,
fewer explicit cross-domain edges → cleanest signal for alignment contribution.

## Design

- R1: single-op baseline, depth=2
- R2: multi-op, depth=2 (replicates Run 007 shallow result)
- R3: multi-op, depth=5 (max_depth=9) — deep compose
- R4: R3 candidates, naive ranking (provenance_aware=False)
- R5: R3 candidates, provenance-aware ranking (provenance_aware=True)

Tracking fields added per candidate for path-level analysis.
