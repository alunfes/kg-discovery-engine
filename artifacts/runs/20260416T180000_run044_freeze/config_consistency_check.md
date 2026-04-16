# Config Consistency Check — Run 044

**Date:** 2026-04-16  
**Purpose:** Verify that code, config (recommended_config.json), and docs are consistent with the frozen policy stack.

---

## Files Checked

| File | Role |
|------|------|
| `crypto/src/eval/push_surfacing.py` | Delivery trigger implementation |
| `crypto/src/eval/delivery_state.py` | Archive lifecycle implementation |
| `crypto/src/eval/surface_policy.py` | Surface pruning (crypto branch) |
| `src/scientific_hypothesis/surface_policy.py` | Surface pruning (scientific pipeline) |
| `crypto/recommended_config.json` | Operator-facing config reference |
| `docs/run031_push_default_shadow.md` | Delivery policy documentation |
| `docs/run036_regime_aware_fallback.md` | Regime-aware fallback documentation |
| `docs/run038_surface_pruning.md` | Surface pruning documentation |
| `docs/run040_resurface_window_extension.md` | Archive window documentation |

---

## Delivery Policy Checks

### T1 Threshold

| Source | Value | Match? |
|--------|-------|--------|
| `push_surfacing.py:HIGH_CONVICTION_THRESHOLD` | 0.74 | — |
| `push_surfacing.py:HIGH_PRIORITY_TIERS` | {actionable_watch, research_priority} | — |
| `recommended_config.json:T1_high_conviction_threshold` | 0.74 | ✓ |
| `recommended_config.json:T1_high_priority_tiers` | [actionable_watch, research_priority] | ✓ |
| `docs/run031_push_default_shadow.md` | 0.74 | ✓ |

**Result: CONSISTENT**

---

### T2 Threshold

| Source | Value | Match? |
|--------|-------|--------|
| `push_surfacing.py:FRESH_COUNT_THRESHOLD` | 3 | — |
| `recommended_config.json:T2_fresh_count_threshold` | 3 | ✓ |

**Result: CONSISTENT**

---

### T3 Lookahead ⚠️ PRE-444 DISCREPANCY (now fixed)

| Source | Value | Match? |
|--------|-------|--------|
| `push_surfacing.py:LAST_CHANCE_LOOKAHEAD_MIN` | 5.0 | — |
| `push_surfacing.py` comment | "Run 031: locked to Variant A (5 min)" | — |
| `recommended_config.json:T3_last_chance_lookahead_min` (pre-Run 044) | **10.0** | ✗ MISMATCH |
| `recommended_config.json:T3_last_chance_lookahead_min` (post-Run 044) | **5.0** | ✓ |
| `docs/run030_t3_tuning.md` | Variant A = 5 min | ✓ |
| `docs/run031_push_default_shadow.md` | LAST_CHANCE_LOOKAHEAD=5 min | ✓ |

**Issue:** The recommended_config.json was not updated after Run 031 locked T3 at 5 min.  
**Fix applied:** Updated `T3_last_chance_lookahead_min` from 10.0 → 5.0 in `crypto/recommended_config.json`.

---

### Rate Limit (S3)

| Source | Value | Match? |
|--------|-------|--------|
| `push_surfacing.py:MIN_PUSH_GAP_MIN` | 15.0 | — |
| `recommended_config.json:rate_limit_gap_min` | 15.0 | ✓ |

**Result: CONSISTENT**

---

### Fallback Cadence ⚠️ PRE-444 DISCREPANCY (now fixed)

| Source | Value | Match? |
|--------|-------|--------|
| `docs/run036_regime_aware_fallback.md` | quiet=60, hot/trans=45 | — |
| `recommended_config.json:baseline_fallback_cadence_min` (pre-Run 044) | **45** (global only) | ✗ PARTIAL — missing regime-aware split |
| `recommended_config.json` (post-Run 044) | `fallback_cadence_quiet_min: 60, fallback_cadence_hot_min: 45` | ✓ |

**Issue:** Run 036 regime-aware policy was not reflected in recommended_config.json.  
**Fix applied:** Added `fallback_cadence_quiet_min: 60`, `fallback_cadence_hot_min: 45`, `fallback_quiet_threshold_hot_prob: 0.25`; removed scalar `baseline_fallback_cadence_min`.

---

### Family Collapse

| Source | Value | Match? |
|--------|-------|--------|
| `delivery_state.py:DeliveryStateEngine.__init__` default | collapse_min_family_size=2 | — |
| `recommended_config.json:family_collapse.enabled` | true | ✓ |
| `recommended_config.json:family_collapse.min_family_size` | 2 | ✓ |

**Result: CONSISTENT**

---

## Archive Policy Checks

### Resurface Window

| Source | Value | Match? |
|--------|-------|--------|
| `delivery_state.py:_DEFAULT_RESURFACE_WINDOW_MIN` | 120 | — |
| `recommended_config.json:archive_policy.resurface_window_min` | 120 | ✓ |
| `docs/run040_resurface_window_extension.md` | Window=120 maintained | ✓ |

**Result: CONSISTENT**

---

### Archive Max Age

| Source | Value | Match? |
|--------|-------|--------|
| `delivery_state.py:_DEFAULT_ARCHIVE_MAX_AGE_MIN` | 480 | — |
| `recommended_config.json:archive_policy.archive_max_age_min` | 480 | ✓ |

**Result: CONSISTENT**

---

### Archive Threshold

| Source | Value | Match? |
|--------|-------|--------|
| `delivery_state.py:_ARCHIVE_RATIO` | 5.0 | — |
| `recommended_config.json:archive_policy.archive_ratio_hl` | 5.0 | ✓ |

**Result: CONSISTENT**

---

## Surface Policy Checks

### null_baseline Rule

| Source | Condition | Match? |
|--------|-----------|--------|
| `crypto/src/eval/surface_policy.py:is_null_baseline` | len(syms)==1 AND "HYPE" not in syms | — |
| `src/scientific_hypothesis/surface_policy.py:is_null_baseline` | Same logic | ✓ |
| `docs/run038_surface_pruning.md` | "single non-HYPE tradeable asset" | ✓ |

**Result: CONSISTENT (both surface_policy.py files match)**

---

### baseline_like Rule

| Source | Condition | Match? |
|--------|-----------|--------|
| `crypto/src/eval/surface_policy.py:is_baseline_like` | secrecy=="shareable_structure" AND novelty_score ≤ 0.30 | — |
| `src/scientific_hypothesis/surface_policy.py:is_baseline_like` | Same logic | ✓ |
| `docs/run038_surface_pruning.md` | shareable_structure + novelty ≤ 0.30 | ✓ |

**Result: CONSISTENT (both surface_policy.py files match)**

---

## Provenance / Metadata Check

| Field | Pre-Run 044 | Post-Run 044 |
|-------|-------------|-------------|
| `_provenance` | "Run 028 final delivery recommendation (2026-04-15)" | "Run 044 final policy freeze (2026-04-16)" |
| `_frozen_for` | "Run 035 live canary" | "Run 044 — production shadow final" |
| `_policy_stack_version` | (absent) | "v2.0" |

---

## Summary

| Check | Pre-Run 044 | Post-Run 044 |
|-------|-------------|-------------|
| T1 threshold (0.74) | ✓ | ✓ |
| T2 threshold (3) | ✓ | ✓ |
| T3 lookahead (5 min) | **✗ config had 10.0** | ✓ fixed |
| S3 rate-limit (15 min) | ✓ | ✓ |
| Fallback cadence (regime-aware) | **✗ config missing quiet=60** | ✓ fixed |
| Family collapse (min=2) | ✓ | ✓ |
| Resurface window (120 min) | ✓ | ✓ |
| Archive max age (480 min) | ✓ | ✓ |
| Archive ratio (5×) | ✓ | ✓ |
| null_baseline DROP rule | ✓ (both files) | ✓ |
| baseline_like ARCHIVE rule | ✓ (both files) | ✓ |

**2 discrepancies found and corrected.** All other checks pass.  
Config, code, and docs are now fully consistent with the frozen policy stack.
