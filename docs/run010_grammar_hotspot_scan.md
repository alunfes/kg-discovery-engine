# run_010 Grammar Hotspot Scan

**Date:** 2026-04-15  
**Sprint:** J (post-fix verification)  
**Runs analyzed:** run_006_sprint_g → run_010_hotspot_scan  
**Question:** Is the SOL confusion fixed by J1 a local bug, or a broader pattern?

---

## Executive Summary

The SOL grammar confusion (E1 beta_reversion firing on SOL pairs in funding_extreme
regime) is **locally rooted in one specific threshold-boundary interaction**, but the
*underlying failure mode* generalizes to a reusable meta-rule.

**Verdict:**

| Dimension | Finding |
|-----------|---------|
| J1 fix scope | Confirmed resolved — 0 reroutes, 0 reject_conflicted in run_009 and run_010 |
| Root cause | E1 transient_aggression fires at burst_min=4 boundary without regime check |
| Other grammar pairs affected | None detected (5 runs, 300 cards) |
| Generalizable pattern | Yes: Meta-rule R1 (Regime Dominance Gate) |
| Remaining exceptions | 2 correct-behavior cards; 0 unresolved bugs |

---

## 1. Hotspot Inventory (run_006 – run_010)

### 1.1 Reroute Record Counts

| Run | H2 Reroutes | reject_conflicted | Max severity | Grammar confusion |
|-----|------------|-------------------|--------------|-------------------|
| run_006 (Sprint G) | N/A (H2 not yet) | N/A (I1 not yet) | 6.0 (rank drop) | Beta_rev (HYPE/SOL) crashed from rank 8→55 (Δ=-47) |
| run_007 (Sprint H) | **12** | N/A (I1 not yet) | 6.0 | Beta_rev → positioning_unwind (6), → flow_continuation (6) |
| run_008 (Sprint I) | **12** | **6** | 6.0 | Same 6 families, now formally tier=reject_conflicted |
| run_009 (Sprint J) | **0** ✓ | **0** ✓ | **0.0** ✓ | J1 gate eliminates source chain |
| run_010 (this run) | **0** ✓ | **0** ✓ | **0.0** ✓ | Fix confirmed persistent |

### 1.2 Hotspot Table Summary

7 hotspot records (see `hotspot_table.csv` for full detail):

| Rank | Hotspot ID | Confusion pair | Affected assets | Runs active | Status |
|------|-----------|----------------|----------------|-------------|--------|
| 1 | HS-001 | beta_rev → positioning_unwind | HYPE/SOL | 007-008 | **resolved** |
| 2 | HS-002 | beta_rev → positioning_unwind | BTC/SOL | 007-008 | **resolved** |
| 3 | HS-003 | beta_rev → positioning_unwind | ETH/SOL (×2) | 007-008 | **resolved** |
| 4 | HS-004 | beta_rev → flow_continuation | HYPE/SOL | 007-008 | **resolved** |
| 5 | HS-005 | beta_rev → flow_continuation | BTC/SOL | 007-008 | **resolved** |
| 6 | HS-006 | beta_rev → flow_continuation | ETH/SOL (×2) | 007-008 | **resolved** |
| 7 | HS-007 | beta_rev → rank_crash | HYPE/SOL | 006 | **resolved** |

All 7 hotspots are resolved. No new hotspots in run_010.

---

## 2. Cluster Analysis

### 2.1 Cluster A — Primary confusion (E1→E2, conf=0.70)

- **Grammar pair:** beta_reversion (E1-transient_aggression) → positioning_unwind (E2)
- **Pairs:** HYPE/SOL, BTC/SOL, ETH/SOL
- **Regime:** funding_extreme + high_oi_growth
- **Threshold boundary:** all 6 families fired at burst_min=4 (minimum value)
- **Severity:** 6.0 (hard reject; highest observed)
- **Score drop on reroute:** −0.207 to −0.213 (rerouted score ~0.40–0.53, original ~0.62–0.74)
- **Runs active:** 007-008 (12 reroute records/run; 3 reject_conflicted/run)
- **Root cause:** E1 chain did not check for E2 regime dominance before firing.
  burst_min=4 is the weakest possible E1 activation; combined with funding_extreme
  + OI_accumulation (strong E2 signals), the hypothesis was structurally inconsistent.

### 2.2 Cluster B — Secondary confusion (E1→flow_continuation, conf=0.60)

- **Grammar pair:** beta_reversion → flow_continuation
- **Regime:** funding_extreme + strong_premium
- **Root cause:** Same source chain as Cluster A; rerouter offered flow_continuation
  as second-best target (lower confidence) because premium signal pointed there.
- **Score drop on reroute:** −0.244 to −0.248 (worse than CLUS-A; lower confidence)
- **Resolution:** Upstream J1 gate eliminates source chain → CLUS-B disappears automatically.
  No independent fix needed.

### 2.3 Cluster C — Pre-H2 signal (run_006 rank crash)

- The SOL confusion was already present in run_006, before H2 rerouting existed.
  It manifested as a massive conflict-rank drop (HYPE/SOL: raw rank 8 → conflict rank 55).
- H2 (Sprint H) made the confusion *visible* as explicit reroute records.
- I1 (Sprint I) made it *actionable* by classifying these cards as reject_conflicted.
- J1 (Sprint J) *eliminated* the source.

**Timeline:** confusion existed from Sprint G; detected via H2; classified via I1; fixed via J1.

---

## 3. Generalization Analysis

### 3.1 Does J1 generalize to other grammar pairs?

**E1 vs E2 (DONE):** The confusion site. Resolved by J1.

**E1 vs flow_continuation:** No independent confusion — secondary target of CLUS-A.
Resolved as a side-effect of J1.

**E2 vs flow_continuation:** Not a confusion site. 0 reroutes across all 5 runs.
E2 (OI-driven crowding) and flow_continuation (premium-momentum) serve structurally
distinct regimes and do not compete for the same KG evidence chains.

**D1-chain vs E2:** D1 cards appear in monitor_borderline (soft_gated=False, scores
0.71-0.78) but this is *genuine hypothesis uncertainty*, not grammar confusion.
The soft-gate correctly handles borderline D1 cases without rerouting.

**Conclusion:** The SOL confusion was a *concentrated hotspot* in one grammar pair
(E1→E2) activated by one regime context (funding_extreme + OI_accumulation). It was
not a diffuse pattern across multiple pairs.

### 3.2 Is the underlying failure mode generalizable?

**Yes.** The failure pattern is:
> A threshold-boundary chain activation fires without checking whether a stronger
> contradicting regime signal dominates.

This is not E1-specific. Any burst-count or threshold chain that:
1. Activates at its minimum threshold, AND
2. Co-occurs with a strong regime context pointing to a different grammar

...is at risk of the same confusion.

**Meta-rule R1 (Regime Dominance Gate):**
> When a chain fires at a threshold boundary AND the dominant local regime contradicts
> the expected chain outcome, suppress the boundary-activation.

J1 is the first instantiation of R1. See `rule_generalization_note.md` for the
template and full applicability analysis.

### 3.3 Other threshold-boundary risks

| Chain | Threshold | Boundary hit observed? | Risk |
|-------|-----------|----------------------|------|
| E1 transient_aggression | burst_min=4 | Yes (run_006-008) | **Fixed** |
| E1 persistent_aggression | persistence_min | No | Monitor |
| flow_continuation | premium_min | No | Monitor |
| soft_gate | uplift_min=0.05 | Yes (2/run always) | Not a confusion — correct |

---

## 4. run_010 vs run_009 Diff

Both runs use identical config (seed=42, 120min, Sprint J codebase). Expected: identical output.

| Metric | run_009 | run_010 | Match? |
|--------|---------|---------|--------|
| Total cards | 60 | 60 | ✓ |
| Branch distribution | pos_unwind=30, beta_rev=2, other=20, flow_cont=8 | same | ✓ |
| H2 reroutes | 0 | 0 | ✓ |
| reject_conflicted | 0 | 0 | ✓ |
| Max severity | 0.0 | 0.0 | ✓ |
| Actionable_watch | 6 | 6 | ✓ |
| Best composite score | 0.865 | 0.865 | ✓ |
| Branch entropy | 1.5795 bits | 1.5795 bits | ✓ |

**Verdict:** run_010 is deterministically identical to run_009. Fix is stable.

---

## 5. Recommendations

### R1 (Done) — J1 Gate
Already implemented. E1 transient_aggression suppressed when funding_extreme +
OI_accumulation co-occur. Defense-in-depth rerouter rule at conf=0.85.

### R2 (Recommend) — Threshold-boundary audit hook
Add a lightweight audit log: whenever a chain activates at its minimum threshold,
record `(chain, pair, regime_flags, score)` to a `boundary_activations.log`.
This makes future boundary-confusion cases detectable before they produce reroutes.

```python
# Example tag to add in each chain's threshold-boundary branch:
if burst_count == burst_min:
    _log_boundary_activation(chain_name, pair, regime_flags, score)
```

### R3 (Monitor) — D1 borderline watch
D1 (Chain-D1) cards consistently land in monitor_borderline with scores 0.71-0.78.
They are not grammar confusions, but their borderline status means a small regime
shift could push them into actionable_watch. Track in persistence tracker; promote
to actionable if consecutive_top_k_count ≥ 2.

### R4 (Future) — Multi-run persistence as confusion detector
With ≥3 consecutive runs, persistence_tracker can flag families that *oscillate*
between tiers (e.g., research_priority → reject_conflicted → research_priority).
Oscillating families are a leading indicator of unresolved grammar confusion.
Implement persistence-oscillation detection in Sprint K.

---

## 6. Artifacts

| File | Description |
|------|-------------|
| `hotspot_table.csv` | Ranked hotspot records across run_006-010 |
| `reroute_clusters.json` | Cluster definitions with pairs, regimes, scores |
| `rule_generalization_note.md` | Meta-rule R1 template and applicability analysis |
| `review_memo.md` | Standard pipeline output (run_010_hotspot_scan) |
| `output_candidates.json` | 60 hypothesis cards |
| `i1_decision_tiers.json` | Tier assignments |

---

## 7. Conclusion

The SOL grammar confusion was:
- **Localized:** one grammar pair (E1→E2), one regime context (funding_extreme + OI_accumulation), one threshold boundary (burst_min=4)
- **Systematic:** affected all 3 SOL-containing pairs consistently across 3 runs
- **Fully resolved:** J1 gate eliminates the source; run_009 and run_010 are clean

The underlying failure mode **does generalize** as Meta-rule R1 (Regime Dominance Gate).
No other grammar pairs are currently confused. Two threshold chains warrant monitoring
in future sprints if they encounter boundary activations.

**Next sprint candidate (Sprint K):** persistence-oscillation detection as a
grammar-confusion early-warning system.
