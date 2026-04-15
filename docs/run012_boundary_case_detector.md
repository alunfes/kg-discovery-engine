# Run 012 — Boundary-Case Detector for Grammar Chains

**Date:** 2026-04-15  
**Sprint:** L  
**Branch:** `claude/friendly-kare`  
**Base:** Sprint K / run_011 (`claude/crazy-vaughan` @ `f6bf25a`)

---

## Objective

Implement a pre-adjudication warning system that detects near-threshold grammar chain
activations where a contradicting regime is simultaneously active — the R1-type
"threshold-boundary confusion" pattern.

The detector runs automatically inside `run_pipeline` and is also usable for retrospective
analysis of past runs.

---

## Design

### Problem Statement

Grammar chains activate when evidence crosses a minimum threshold. Borderline activations
(evidence barely above threshold) are weak. If a contradicting regime co-occurs, the
resulting hypothesis card will likely conflict with a stronger-evidence card downstream
→ `reject_conflicted` decision, spurious reroute.

Meta-rule R1 (run_011) addresses the strongest case (J1: E1 + funding_extreme + OI_accum).
Run 012 generalises the detection: capture ALL near-threshold activations, classify them
by regime-contradiction risk, and emit graded pre-adjudication warnings.

### Module: `crypto/src/eval/boundary_detector.py`

```
ThresholdSpec              — catalog entry for one activation threshold
CHAIN_THRESHOLDS           — production catalog (5 entries)
BoundaryActivationRecord   — one detected near-threshold activation
BoundaryWarning            — pre-adjudication warning with recommended action
BoundaryDetector           — detect_from_kg() + generate_warnings()
run_retrospective_analysis — apply to past run artifact directories
```

### Threshold Catalog (5 entries)

| Key | Chain | Threshold | Direction |
|-----|-------|-----------|-----------|
| `e1_transient_aggr_burst_upper` | E1 transient aggr | burst_count_max=4 | upper |
| `e1_transient_aggr_burst_lower` | E1 transient aggr | burst_count_min=1 | lower |
| `e2_funding_soft_gate` | E2 funding pressure | funding_confidence_min=0.30 | lower |
| `e2_oi_soft_gate` | E2 OI crowding | oi_confidence_min=0.30 | lower |
| `d3_continuation_break_score` | D3 continuation | corr_break_score_min=0.20 | lower |

### Boundary Proximity Formula

```
lower-bound: proximity = (actual - threshold) / threshold
upper-bound: proximity = (threshold - actual) / threshold
```
Near 0 = at the activation boundary. Proxmity ≥ 1.0 = far from boundary (suppressed).

### Warning Escalation Rules

| Condition | Level | Action |
|-----------|-------|--------|
| proximity < 0.20 AND regime_contradiction | HIGH | r1_candidate |
| proximity < 0.50 AND regime_contradiction | MEDIUM | manual_review |
| proximity < 0.20 (no contradiction) | LOW | monitor |
| proximity ≥ 0.50 | — | suppressed |

### Pipeline Integration

`run_pipeline` calls `BoundaryDetector.detect_from_kg` immediately after
`build_chain_grammar_kg`. Results are stored in `branch_metrics["run012_boundary_detection"]`
alongside all other run artifacts.

---

## Run Results (seed=42, 120 min, HYPE/ETH/BTC/SOL)

| Metric | Value |
|--------|-------|
| Activation records detected | 1 |
| Warnings generated | 0 |
| HIGH warnings | 0 |
| Chain exposed | `positioning_unwind_oi_crowding` (E2) |
| Pair exposed | ETH/BTC |

The single detected record is an E2 OI crowding activation at soft-gate boundary for ETH/BTC.
Since E2 chains have no contradicting signals (OI accumulation is the E2 trigger, not a
contradiction), no warnings are generated. This is the correct and expected result.

---

## Retrospective Analysis (run_009–011)

| Run | Records | Warnings | HIGH |
|-----|---------|----------|------|
| run_009 | 1 | 0 | 0 |
| run_010 | 1 | 0 | 0 |
| run_011 | 1 | 0 | 0 |
| **aggregate** | **3** | **0** | **0** |

**Cross-run pattern:**  
All 3 records are `positioning_unwind_oi_crowding` at ETH/BTC — consistent across runs
because the synthetic data generator (seed=42) produces stable soft-gate OI patterns for
that pair. No HIGH-risk boundary cases in any run.

---

## SOL J1 Regression Sanity

**Test:** After J1/R1 fix (run_011), SOL pairs with funding_extreme + OI should produce
no HIGH boundary warnings because R1 suppresses the E1 chain before any
`NoPersistentAggressionNode` is created.

**Result:** ✓ CONFIRMED — 0 HIGH boundary warnings for SOL pairs in all 3 retrospective runs.
The J1 fix is working correctly.

---

## Chain Risk Ranking

See `crypto/artifacts/runs/run_012_boundary_detector/chain_risk_ranking.json`.

| Rank | Chain | Activations | High-Risk | Risk Score |
|------|-------|-------------|-----------|------------|
| 1 | `positioning_unwind_oi_crowding` | 3 | 0 | 0.0 |

Only 1 chain has near-threshold activations in runs 009–011. Risk score = 0 because no
regime contradictions were observed.

---

## Candidate Future R1 Applications

See `crypto/artifacts/runs/run_012_boundary_detector/candidate_r1_expansions.md`.

**No new R1 instances recommended** based on this run.  

Conditions that would trigger a new R1 instance:
1. `beta_reversion_transient_aggr` with burst_count=4 AND ONE of {funding_extreme, OI_accum}
   → observe ≥2 runs where this produces a `reject_conflicted` card
2. A registered regime signal that *contradicts* `positioning_unwind` is identified
   → only then would E2 soft-gate activations become R1 candidates

---

## Key Design Decisions

### 1. KG-node-based detection (not suppression-log-based)

**Decision:** Scan grammar KG nodes for activation values, not just the suppression log.  
**Why:** The suppression log captures chains that were *suppressed*; we need chains that
*activated* at near-threshold values. KG nodes carry the measured values (burst_count,
activation_confidence) that make proximity computation possible.

### 2. Non-invasive pipeline integration

**Decision:** BoundaryDetector is called after `build_chain_grammar_kg` in `run_pipeline`
without modifying the chain builder signatures.  
**Why:** Avoids signature changes that would require updating all chain builder call sites.
The detector reads the output KG, not the chain builder internals.

### 3. E2 chains excluded from R1 candidates

**Decision:** `contradicting_regime_signals = []` for all E2 chain threshold specs.  
**Why:** Funding extreme and OI accumulation are the *trigger* signals for E2 chains, not
contradictions. Applying R1 to E2 would suppress the exact chains R1 is designed to protect.
This matches the Over-Suppression Guard in `grammar_meta_rules.md`.

### 4. Retrospective via pipeline re-run (not JSON parsing)

**Decision:** `run_retrospective_analysis` re-runs the pipeline with the saved seed rather
than parsing JSON artifacts.  
**Why:** Grammar KG nodes and merged KG are not serialised in run artifacts. Re-running with
the same seed is deterministic and provides the exact intermediate state needed for regime
signal resolution.

---

## Test Coverage (Sprint L)

39 tests, all passing. Covers:
- ThresholdSpec construction
- `_compute_proximity` lower/upper bounds
- `BoundaryDetector.detect_from_kg` (node scan + soft-gate log scan)
- Regime contradiction flag (True/False cases)
- `generate_warnings` (HIGH/MEDIUM/LOW/suppressed + sort order)
- Serialisation helpers (JSON-safe)
- SOL J1 regression sanity (2 tests)
- Precision check: HIGH warnings bounded < 20 in standard run
- Pipeline regression: 0 reject_conflicted, watchlist ≥ 55
- Retrospective: structure + SOL regression

---

## Files Changed

| File | Type | Description |
|------|------|-------------|
| `crypto/src/eval/boundary_detector.py` | NEW | Boundary-case detector module |
| `crypto/src/pipeline.py` | MODIFIED | Calls detector after chain grammar; stores in branch_metrics |
| `crypto/tests/test_sprint_l.py` | NEW | 39 Sprint L tests |
| `crypto/artifacts/runs/run_012_boundary_detector/` | NEW | Run artifacts |
| `docs/run012_boundary_case_detector.md` | NEW | This document |
