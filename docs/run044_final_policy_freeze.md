# Run 044: Final Policy Freeze

**Date:** 2026-04-16  
**Status:** Complete — FROZEN  
**Scope:** Delivery / Surface / Archive policy final verification and freeze  
**Baseline runs:** 028–043 (Epic Allen series)

---

## Objective

Freeze the validated delivery, surface, and archive policies documented across
Runs 028–043. Verify that config, docs, and code are consistent. Produce a
final conclusion stability map and policy stack for the project.

---

## Policy Freeze Summary

### 1. Delivery Policy — LOCKED

| Parameter | Locked Value | Source Run |
|-----------|-------------|------------|
| Delivery mode | push | Run 028 |
| T1 threshold | score ≥ 0.74 | Run 028 |
| T1 tiers | actionable_watch, research_priority | Run 028 |
| T2 threshold | ≥ 3 high-priority incoming cards | Run 028 |
| T3 lookahead | 5 min (Variant A) | Run 030–031 |
| S1 suppression | All cards digest_only/expired/archived → suppress | Run 028 |
| S2 suppression | All fresh cards low-priority or digest-collapsed → suppress | Run 028 |
| S3 rate-limit | min gap = 15 min between consecutive pushes | Run 028 |
| Family collapse | enabled, min_family_size = 2 | Run 027–028 |
| Fallback cadence (quiet) | 60 min (hot_prob ≤ 0.25) | Run 036 |
| Fallback cadence (hot/transition) | 45 min (hot_prob > 0.25) | Run 035–036 |

**Performance validated** (Run 031, 5-day shadow):

| Metric | Value | vs. poll_45min |
|--------|-------|----------------|
| reviews/day | 21.0 | −34% |
| missed_critical | 0 | = |
| operator burden | −21% | — |
| T3 fraction | 0.0% (safety net only) | — |

### 2. Surface Policy — LOCKED

| Rule | Condition | Action | Affected % | Value loss |
|------|-----------|--------|-----------|-----------|
| null_baseline | Single non-HYPE asset in provenance path | DROP | 5.1% | 0% |
| baseline_like | shareable_structure + novelty ≤ 0.30 | ARCHIVE | 5.6% | 0% |
| default | All others | ACTIVE | 89.2% | — |

**Performance validated** (Run 038–038b):
- Surface reduction: 10.8% (409 → 365 cards)
- Action-worthy preserved: 100% (190/190)
- Operator burden: −88 items/day (818 → 730)

### 3. Archive Policy — LOCKED

| Parameter | Locked Value | Source Run |
|-----------|-------------|------------|
| Archive threshold | 5× half-life | Run 028 |
| Resurface window | 120 min | Run 039–040 (LCM bottleneck; 240 min adds nothing) |
| Archive max age | 480 min (8 h) | Run 028, Run 039 |
| Max resurfaces per review | 1 per family per review | Run 028 code |
| Family overrides | None (uniform policy) | Run 039 |

**Performance validated** (Run 039, 7-day audit):
- Recovery rate: 79.3% (resurfaced/archived)
- Net value rate (resurfaced): 90.5%
- Action_worthy permanently lost: **0** (structural guarantee: baseline_like cap=0.62 < 0.74 threshold)

**Structural ceiling accepted** (Run 040):
- Permanent archive loss: ~14.5–20.7% of baseline_like cards
- Root cause: LCM(batch=30, cadence=45) = 90 min → only 2 resurface windows per 120-min window
- Extending window to 240 min does not improve recovery (proxy misses → time-expired)
- **Accepted**: design-correct behavior given crypto session horizon (8 h)

---

## Code ↔ Config ↔ Docs Consistency Check

See `artifacts/runs/20260416T180000_run044_freeze/config_consistency_check.md` for full detail.

### Summary

| Component | Status | Notes |
|-----------|--------|-------|
| `push_surfacing.py` | ✓ CORRECT | T1=0.74, T2=3, T3=5min, S1/S2/S3 all present |
| `delivery_state.py` | ✓ CORRECT | resurface=120, max_age=480, family collapse |
| `surface_policy.py` (crypto) | ✓ CORRECT | null_baseline DROP, baseline_like ARCHIVE |
| `surface_policy.py` (src/scientific_hypothesis) | ✓ CORRECT | Matches crypto version |
| `recommended_config.json` (pre-044) | ⚠️ STALE | T3 was 10.0 (code had 5.0); fallback global only |
| `recommended_config.json` (post-444) | ✓ UPDATED | T3=5.0, regime-aware fallback, frozen for Run 044 |

**Action taken:** Updated `crypto/recommended_config.json` to reflect:
1. `T3_last_chance_lookahead_min: 5.0` (was 10.0; code had 5.0 since Run 031)
2. Regime-aware fallback: `fallback_cadence_quiet_min: 60`, `fallback_cadence_hot_min: 45`
3. Updated provenance to Run 044

---

## Conclusion Stability

See `docs/final_conclusion_stability_map.md` for full classification.

**Summary counts:**
- **Robust** (confirmed across ≥2 independent runs): 14 conclusions
- **Conditional** (true under tested conditions, may change with live data): 8 conclusions
- **Superseded** (corrected by later bug fixes or reruns): 7 claims

---

## What Remains Open

| Topic | Status | Reasoning |
|-------|--------|-----------|
| Real-data validation | Open | All validation is synthetic (Hyperliquid mock) |
| Per-family cadence tuning | Open | Run 037 recommended; not yet executed |
| vol_burst detection | Open | Always 0 in synthetic data; unknown on real data |
| HttpMarketConnector testing | Open | Mock only; real connector untested end-to-end |
| Run 040 LCM cadence fix | Open | Aligning cadence=batch_interval would close 87% of proximity misses |
| P11 pre-filter cold-start | Open | Run 043 recommended P11-A/B |

---

## Artifacts

| File | Description |
|------|-------------|
| `artifacts/runs/20260416T180000_run044_freeze/config_consistency_check.md` | Code/config/doc alignment check |
| `artifacts/runs/20260416T180000_run044_freeze/robust_vs_conditional_table.csv` | Structured conclusion stability table |
| `artifacts/runs/20260416T180000_run044_freeze/superseded_claims.md` | Claims corrected by bug fixes |
| `docs/final_conclusion_stability_map.md` | Full conclusion stability narrative |
| `docs/final_policy_stack.md` | Complete policy stack (locked/open/ceiling) |
| `crypto/recommended_config.json` | Final frozen config |
