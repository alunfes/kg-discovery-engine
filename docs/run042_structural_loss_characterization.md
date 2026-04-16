# Run 042: Structural Loss Characterization

**Date**: 2026-04-16  
**Seed**: 42  
**Session**: 168h (7 days, 24/7 crypto)  
**Config**: batch_interval=30min, n_per_batch=20, resurface_window=120min, archive_max_age=480min

---

## Executive Summary

This run characterizes the 61 permanent losses (14.5% of 420 archived cards) from the Run 039 resurface policy. Recovery rate was 85.5%.

| Finding | Value | Classification |
|---------|-------|----------------|
| Total permanent losses | 61 (14.5%) | — |
| Time-expired losses | 3 (4.9%) | ACCEPT |
| Companion-preceded losses | 2 (3.3%) | ACCEPT |
| In-window non-resurfaces | 28 (45.9%) | ACCEPT |
| Proximity-miss losses | 28 (45.9%) | Mixed |
| **ACCEPT total** | **41 (67.2%)** | Structural; accept as spec |
| **MITIGATE total** | **19 (31.1%)** | Addressable by upstream change |
| **INVESTIGATE total** | **1 (1.6%)** | Unclear; needs more data |

**Key finding**: The majority of permanent losses are structural (ACCEPT). Only 31.1% of losses are addressable by upstream changes, and these are concentrated in high-value families (cross_asset, reversion) with short companion gaps in calm/active regimes.

---

## 1. Loss by Family

| Family | Lost | Total Archived | Loss Rate | Primary Mechanism |
|--------|------|---------------|-----------|-------------------|
| cross_asset | 17 | 88 | 19.3% | no_companion_window |
| null | 15 | 76 | 19.7% | proximity_miss |
| unwind | 13 | 95 | 13.7% | no_companion_window |
| momentum | 9 | 81 | 11.1% | proximity_miss |
| reversion | 7 | 80 | 8.8% | proximity_miss |

**Interpretation**: 
- Families with high loss rates in sparse regime are expected (structural noise suppression).
- High loss rates in cross_asset/reversion families with proximity_miss mechanism are the primary MITIGATE targets.

---

## 2. Loss by Regime Transition

| Transition | Count | % of Losses | Dominant Mechanism |
|-----------|-------|-------------|-------------------|
| sparse→sparse | 20 | 32.8% | proximity_miss |
| calm→calm | 19 | 31.1% | no_companion_window |
| active→active | 13 | 21.3% | no_companion_window |
| mixed→mixed | 5 | 8.2% | proximity_miss |
| sparse→calm | 2 | 3.3% | proximity_miss |
| mixed→preceded | 2 | 3.3% | companion_preceded |

**Key patterns**:
- `sparse→*` transitions dominate time_expired losses: sparse-regime cards age out before active companions arrive.
- `calm→*` and `active→*` transitions with proximity_miss are the MITIGATE targets: companion arrived slightly too late.
- `*→preceded` transitions represent cards born into already-active families.

---

## 3. Loss Timing

| Loss mechanism | Count | % | Gap range | Policy implication |
|----------------|-------|---|-----------|-------------------|
| time_expired | 3 | 4.9% | >480min | Structural; archive correctly expired |
| proximity_miss | 28 | 45.9% | 120–480min | Mixed ACCEPT/MITIGATE depending on family/regime |
| companion_preceded | 2 | 3.3% | N/A | Structural; card archived after companion left |
| no_companion_window | 28 | 45.9% | ≤120min | Winner-take-all: sibling won single resurface slot (Run 041 rules out multi-resurface) |

**Gap statistics** (N=59): mean=200min, median=150min, P75=285min, max=900min

---

## 4. Loss by Value

Baseline_like cards score 0.40–0.62 (by design; cap enforced by scorer). No permanently lost card is counterfactually action_worthy (requires score ≥ 0.74).

| Value bucket | Count | % of losses |
|-------------|-------|-------------|
| 0.40–0.50 (low) | 33 | 54.1% |
| 0.50–0.55 (mid) | 16 | 26.2% |
| 0.55–0.60 (high) | 10 | 16.4% |
| 0.60–0.62 (near-miss) | 2 | 3.3% |

**Counterfactually attention_worthy** (score ≥ 0.60): 2 (3.3%). These near-miss cards are the highest-priority MITIGATE targets.

---

## 5. ACCEPT / MITIGATE / INVESTIGATE Summary

| Classification | Count | % | Action |
|----------------|-------|---|--------|
| ACCEPT | 41 | 67.2% | No change needed |
| MITIGATE | 19 | 31.1% | Upstream change possible (see below) |
| INVESTIGATE | 1 | 1.6% | Collect more data |

### ACCEPT: Structural losses (do nothing)

- **Time-expired** (3): companion arrived after 480min archive expiry. By design — stale signal must not influence current decisions.
- **Companion-preceded** (2): family's action_worthy signal fired before this card was archived. Card born into stale family; no mechanism could catch it.
- **In-window non-resurfaces** (28): companion arrived within resurface window but a higher-scoring sibling card from the same (branch, grammar_family) took the single resurface slot. Winner-take-all policy is intentional; multi-resurface was ruled out in Run 041 (quality degrades).

### MITIGATE: Addressable losses

- **regime_aware_archival**: 10 recoverable losses
- **extend_archive_max_age_per_family**: 9 recoverable losses

**Recommended change**: For high-value families (cross_asset, reversion) in calm/active regimes, extend archive_max_age from 480min to 720min. This preserves the archive contract for sparse regime while extending retention for families with active companions.

**Expected impact**: recover ~19 losses (31.1% of total permanent losses). Net permanent loss would fall from 14.5% to ~10.0% of archived cards.

### INVESTIGATE: Unclear losses

- **1 losses** don't fit cleanly into ACCEPT or MITIGATE. 
- Primary pattern: proximity_miss in mixed regime or with unusual score/family combination.
- Recommendation: Run a focused 14-day simulation (mixed-regime extended) to gather more data before classifying these.

---

## Artifacts

| File | Path |
|------|------|
| Loss by family | `artifacts/runs/20260416T060512_run042_loss_map/loss_by_family.csv` |
| Loss by regime transition | `artifacts/runs/20260416T060512_run042_loss_map/loss_by_regime_transition.csv` |
| Timing distribution | `artifacts/runs/20260416T060512_run042_loss_map/loss_timing_distribution.md` |
| Value analysis | `artifacts/runs/20260416T060512_run042_loss_map/loss_value_analysis.md` |
| ACCEPT/MITIGATE/INVESTIGATE | `artifacts/runs/20260416T060512_run042_loss_map/accept_mitigate_investigate.md` |
| Run config | `artifacts/runs/20260416T060512_run042_loss_map/run_config.json` |
| Simulation code | `crypto/run_042_structural_loss.py` |
