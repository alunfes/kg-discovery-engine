# Run 038b: Surface Policy v2 Integration into mvp_runner.py

**Date:** 2026-04-16
**Status:** Complete
**Condition:** production-shadow (mock data, HYPE/BTC/ETH/SOL)
**Source run:** `20260416_033441_hyperliquid_mvp` (409 cards)
**Baseline:** `20260412_153356_hyperliquid_mvp` (Run 038 — no surface policy)

---

## Objective

Integrate `surface_policy.py` (Run 038) into the `mvp_runner.py` main pipeline,
so that the surface pruning rules are applied automatically before delivery and
artifact output — not just in offline audits.

---

## Pipeline Order After Integration

```
hypothesis generation
  → value labeling       (score_and_convert_all)
  → surface policy       (apply_surface_policy + compute_surface_metrics)  ← NEW
  → delivery/surfacing   (HypothesisStore.save_batch with active-only)
  → artifact output      (_write_artifacts with surface_tiers + metrics)
```

---

## Code Changes

### `src/scientific_hypothesis/surface_policy.py`

Added `compute_surface_metrics()` function (30 lines):
- Computes action_worthy, attention_worthy, redundant, archived counts
- Computes pruning_rate, operator_burden, missed_critical, resurface_potential
- Uses `_REVIEWS_PER_DAY = 2.0` as baseline review cadence

### `src/pipeline/mvp_runner.py`

| Change | Location | Description |
|--------|----------|-------------|
| Import | Lines 25–31 | Import `apply_surface_policy`, `compute_surface_metrics`, `SURFACE_ACTIVE/ARCHIVE/DROP` |
| New helper | `_policy_note_lines()` | Builds surface policy section for `run_notes.md` |
| Step 6.5 | `run_mvp()` | Apply surface policy after value labeling |
| Step 7 | `run_mvp()` | Store `surface_tiers[SURFACE_ACTIVE]` only (not all cards) |
| Step 8 | `run_mvp()` | Pass `surface_tiers` + `surface_metrics` to artifact writers |
| `_write_artifacts()` | Full rewrite | Writes `surfaced_hypotheses.json`, `archived_hypotheses.json`, `surface_policy_report.json` |
| `write_run_notes()` | +`surface_metrics` param | Includes Surface Policy section |

---

## Run 038 vs Run 038b Comparison

### Before/After Surface Policy

| Metric | Run 038 (no policy) | Run 038b (integrated) | Delta |
|--------|---------------------|----------------------|-------|
| total_input | 409 | 409 | 0 |
| total_surfaced | 409 | **365** | **−44 (−10.8%)** |
| action_worthy | 190 (102 PA + 88 IW) | **190** | **0 (0% loss)** |
| attention_worthy | 219 | **175** | −44 (−20.1%) |
| dropped (null_baseline) | 0 | **21** | +21 |
| archived (baseline_like) | 0 | **23** | +23 |
| reviews/day | 2.0 | 2.0 | 0 |
| operator_burden (items/day) | 818 | **730** | **−88 (−10.8%)** |
| missed_critical | N/A | **0** | Zero value loss |
| resurface_potential | N/A | 23 | — |

### Artifact Output

| File | Run 038 | Run 038b |
|------|---------|---------|
| `generated_hypotheses.json` | All 409 cards | All 409 cards (pre-policy audit) |
| `surfaced_hypotheses.json` | — | **365 active cards (new)** |
| `private_alpha_candidates.json` | 102 | 102 (unchanged; from active) |
| `shareable_structure_candidates.json` | 219 | 175 (active only) |
| `archived_hypotheses.json` | — | **23 baseline_like cards (new)** |
| `surface_policy_report.json` | — | **Full metrics dict (new)** |
| Inventory | 409 stored | **365 stored (active only)** |

---

## Key Findings

### 1. Zero missed_critical
All `private_alpha` (102) and `internal_watchlist` (88) cards are in
`SURFACE_ACTIVE`. The null_baseline rule (non-HYPE single-asset paths) and
the baseline_like rule (shareable_structure, novelty ≤ 0.30) do not affect
any action-worthy cards — by construction (HYPE paths are excluded from
null_baseline; baseline_like requires shareable_structure secrecy).

### 2. Operator burden reduction: −10.8%
Before: 2 reviews/day × 409 cards = 818 items/day
After: 2 reviews/day × 365 cards = 730 items/day
Reduction: 88 items/day eliminated without value loss.

### 3. Attention-worthy reduction: −20.1%
219 → 175 shareable_structure cards. The 44 removed cards are:
- 21 null_baseline (BTC/ETH/SOL single-asset microstructure/execution paths)
- 23 baseline_like (shareable_structure, novelty_score ≤ 0.30)

### 4. Resurface potential = 23
The 23 archived (baseline_like) cards are stored with resurface_potential=23.
These can be promoted if follow-up evidence confirms the structural pattern.

### 5. archive/resurface impact
- archived cards are written to `archived_hypotheses.json` (not surfaced)
- dropped (null_baseline) cards are excluded from all output files
- Archived cards remain queryable; dropped cards are audit-only in `generated_hypotheses.json`

---

## Surface Policy Configuration

| Rule | Condition | Action | Count |
|------|-----------|--------|-------|
| null_baseline | Single non-HYPE asset in provenance | DROP | 21 |
| baseline_like | shareable_structure + novelty ≤ 0.30 | ARCHIVE | 23 |
| default | Everything else | ACTIVE | 365 |

---

## Conclusion

Surface Policy v2 is now integrated as a first-class pipeline step in
`mvp_runner.py`. The integration achieves:

- **10.8% operator burden reduction** (818 → 730 items/day)
- **Zero missed_critical** — all private_alpha and internal_watchlist cards preserved
- **Artifacts reflect final state** — inventory, `surfaced_hypotheses.json`, and
  `run_notes.md` all show post-policy counts
- **Full audit trail maintained** — `generated_hypotheses.json` retains all 409
  pre-policy cards for reproducibility

The production-shadow condition is met: the policy runs inline with the real
pipeline using mock data, confirming the same pruning outcome as the Run 038
offline audit (10.8% reduction, 44 cards removed, 0 value loss).

---

## Artifacts

| File | Description |
|------|-------------|
| `artifacts/runs/20260416_033441_hyperliquid_mvp/surfaced_hypotheses.json` | 365 active cards |
| `artifacts/runs/20260416_033441_hyperliquid_mvp/archived_hypotheses.json` | 23 baseline_like |
| `artifacts/runs/20260416_033441_hyperliquid_mvp/surface_policy_report.json` | Full metrics |
| `artifacts/runs/20260416_033441_hyperliquid_mvp/generated_hypotheses.json` | All 409 (pre-policy) |
| `artifacts/runs/20260416_033441_hyperliquid_mvp/run_notes.md` | Run notes with policy section |
