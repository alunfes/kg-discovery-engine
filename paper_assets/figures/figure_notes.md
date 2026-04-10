# Figure Notes — KG Discovery Engine

Generated: 2026-04-10  
Script: `scripts/generate_figures.py`  
Resolution: 300 dpi, PNG

---

## Figure 1 — Pipeline Architecture (`figure1_pipeline.png`)

**What it shows**: End-to-end flow of the KG Discovery Engine from two domain-specific
KGs (G_bio, G_chem) through alignment → union → compose+filter → evaluate/rank to
ranked cross-domain hypothesis candidates.

**Claim supported**: Background / Methods (no quantitative claim; sets up the pipeline
structure needed to understand Claims 1–3).

**20-second takeaway**: Two KGs are merged via bridge nodes introduced by alignment.
The compose operator then enumerates multi-hop paths that cross the domain boundary.
Without the alignment step, these cross-domain paths are structurally unreachable.

**Design notes**: Conceptual diagram only; node count annotations (293/243) are for
Subset A (Run 009, the main scale-up experiment). No quantitative claim is asserted
in this figure.

**Data source**: Conceptual. Node counts from `final_metrics.json` →
`scale_progression.run_009_536n`.

---

## Figure 2 — Alignment Leverage (`figure2_alignment_leverage.png`)

**What it shows**: Bar chart of unique cross-domain candidate pairs produced per subset
(A=5, B=40, C=55), annotated with the unique/bridge ratio (0.7×, 8.0×, 6.1×) and
bridge class.

**Claim supported**: **Claim 1** — "Alignment unlocks otherwise unreachable cross-domain
paths, and this is the primary source of multi-operator value."  
Also supports **Claim 3** — "Bridge dispersion, not raw count, drives cross-domain yield."

**20-second takeaway**: Subset B has the *fewest* aligned bridges (5) yet produces 8×
more unique candidates than Subset A (7 bridges). This falsifies the naive prediction
that more bridges → more candidates, and points instead to bridge structural diversity
(NADH = 1 hub vs. 5 eicosanoids vs. 6–8 neurotransmitters).

**Data source**: `final_metrics.json` → `bridge_dispersion_analysis` (all three subsets).

| Field | Value |
|-------|-------|
| A: unique_to_alignment | 5 |
| B: unique_to_alignment | 40 |
| C: unique_to_alignment | 55 |
| A: aligned_pairs | 7 |
| B: aligned_pairs | 5 |
| C: aligned_pairs | 9 |
| A: unique_per_bridge | 0.7 |
| B: unique_per_bridge | 8.0 |
| C: unique_per_bridge | 6.1 |

---

## Figure 3 — Drift Rate by Depth (`figure3_drift_by_depth.png`)

**What it shows**: Line chart with three lines (one per subset A/B/C) showing drift
rate (fraction of candidates containing a low-specificity relation) as path depth
increases from 2-hop to 4–5-hop.

**Claim supported**: **Claim 2** — "Deep cross-domain discovery is possible, but only
becomes useful when combined with quality-aware filtering." Specifically supports the
motivation for the drift filter by showing that drift is a structural, depth-dependent
phenomenon, not a domain-specific artifact.

**20-second takeaway**: All three lines slope monotonically upward — drift is always
worse at deeper hops, in every domain pair. The pattern is robust across independent
domain pairs (3/3 subsets), confirming it is a structural property of the compose
operator rather than noise.

**Data source**: `final_metrics.json` → `reproducibility_run013` → per-subset
`drift_by_depth` (keys: 2hop, 3hop, 4_5hop).

| Subset / Depth | 2-hop | 3-hop | 4–5-hop |
|----------------|-------|-------|---------|
| A | 0.0883 | 0.1612 | 0.2372 |
| B | 0.1279 | 0.2203 | 0.2932 |
| C | 0.0562 | 0.1837 | 0.2953 |

---

## Figure 4 — Filter Effect (`figure4_filter_effect.png`)

**What it shows**: Stacked bar chart comparing quality composition of deep cross-domain
candidates before (Run 011 baseline, n=20) and after (Run 012 filtered, n=3) the
quality-aware drift filter.

**Claim supported**: **Claim 2** — "Deep cross-domain discovery is possible, but only
becomes useful when combined with quality-aware filtering."

**20-second takeaway**: The filter eliminates all drift-heavy (5→0) and weak-speculative
(12→0) candidates, while preserving every promising candidate (3→3). Zero false
negatives. The stacked bar makes the "no loss of signal, clean removal of noise"
story immediately visible.

**Data source**: `final_metrics.json` → `filter_effect_run012`.  
Segment counts (3 / 12 / 5) are derived from reported percentages applied to n=20:
  - promising: 15% × 20 = 3
  - weak_speculative: 60% × 20 = 12
  - drift_heavy: 25% × 20 = 5

These numbers are consistent with the Run 011 qualitative review (single reviewer)
documented in `runs/run_011_*/review_memo.md`.

---

## Reproduction

```bash
# From repo root
python scripts/generate_figures.py
```

All figures are deterministically regenerated. No external data fetches or random
seeds beyond `random.seed(42)` / `np.random.seed(42)` (which affect no content in
the current version, but are set for forward compatibility).

---

## Figure 5 — Phase 4 Full KG (`phase4_full_kg.png`)

**What it shows**: The maximum KG used in Phase 4 experiments (Run 009, Condition D).
536 nodes (bio=293, chem=243), 464 edges, 81 bridge/alignment-candidate nodes.

**Layout**: Domain-separated — biology nodes (blue) left cluster, chemistry nodes (orange)
right cluster, bridge nodes (gold) in the centre. Within each cluster, spring_layout with
seed=42. Bridge-adjacent edges drawn in gold; intra-domain edges in faint grey.

**Claim supported**: Background / Methods visual. Demonstrates scale and cross-domain
connectivity of the actual KG used in scale-up experiments.

**20-second takeaway**: Two distinct domain clouds connected by a dense gold bridge zone.
The bridge nodes are structurally central — removing them would disconnect the domains.

**Data source**: `src/kg/phase4_data.build_condition_d()` + `src/data/wikidata_phase4_loader`
(fallback curated dataset, deterministic).

**Variants**:
- `phase4_full_kg_preview.png` — 960×540 Twitter/Slack preview
- `phase4_kg_bio_only.png` — biology subgraph only (293 nodes)
- `phase4_kg_chem_only.png` — chemistry subgraph only (243 nodes)
- `phase4_kg_bridge_focused.png` — bridge nodes + 1-hop neighbours

**Generation**:
```bash
python scripts/generate_phase4_kg_viz.py
```
SEED=42, dpi=200 (main), dpi=150 (variants). Requires matplotlib, networkx, numpy.
