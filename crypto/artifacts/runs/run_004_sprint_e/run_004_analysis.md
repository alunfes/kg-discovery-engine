# run_003 → run_004 Diff Analysis — Sprint E

**Date:** 2026-04-15
**Run:** run_004_sprint_e (seed=42, n_minutes=120, top_k=60)
**Prior run:** run_003_sprint_d (seed=42, n_minutes=120, top_k=16)

---

## 1. Branch Entropy

| Metric | run_003 | run_004 | Delta |
|---|---|---|---|
| Total cards | 16 | 60 | +44 |
| Branch entropy | ~0.0 bits (single-branch) | **1.7651 bits** | +1.77 |
| Distinct branches | 1 (continuation) | 4 | +3 |

run_003 was effectively single-branch: 100% of cards were `continuation_candidate` or `D1_chain_flow_continuation`. The 1.7651-bit entropy in run_004 reflects a genuine 4-way split.

---

## 2. Continuation Bias Relief

| Branch | run_003 | run_004 |
|---|---|---|
| flow_continuation / continuation_candidate | 100% (16/16) | **13.3%** (8/60) |
| positioning_unwind | 0% | **50.0%** (30/60) |
| beta_reversion | 0% | **13.3%** (8/60) |
| other | 0% | 23.3% (14/60) |

The `flow_continuation` dominance is broken. Sprint E chain grammar nodes fire on the same 6 corr-break pairs that previously all routed to continuation.

---

## 3. New Chain Families: Fire Status

### E1 beta_reversion — FIRES
- 8 cards in top-60 (13.3%)
- Mean composite score: 0.665
- Tags present: `beta_reversion`, `E1`, `transient_aggression`, `negative_evidence`
- Firing conditions met: NoFundingShiftNode + NoOIExpansionNode created for pairs without OI accumulation; transient-aggression chain fires for SOL-pair (min per-asset burst count ≤ 4)

### E2 positioning_unwind — FIRES (dominant branch)
- 30 cards in top-60 (50%)
- Mean composite score: 0.702
- Tags present: `positioning_unwind`, `E2`, `funding_pressure`, `oi_crowding`, `premium_compression`
- Firing conditions met: SOL OI accumulation (monotonic from min 50) + elevated SOL funding (rate=0.0020 at min 75) create FundingPressureRegimeNode + OneSidedOIBuildNode for all 6 corr-break pairs

---

## 4. Suppression Reason Top-k

Total suppressions: 34

| Reason | Count | % |
|---|---|---|
| `insufficient_negative_evidence` | 26 | 76% |
| `no_trigger` | 6 | 18% |
| `missing_accumulation` | 2 | 6% |

**Interpretation:** `insufficient_negative_evidence` dominates because ~5 of 6 corr-break pairs involve ETH/BTC with ≥5 burst windows per asset — the transient-aggression E1 chain correctly classifies them as persistent and suppresses. `missing_accumulation` fires for ETH/BTC pairs where neither has OI accumulation.

---

## 5. Score Distribution

| Branch | Mean | Min | Max |
|---|---|---|---|
| positioning_unwind | 0.702 | 0.541 | 0.865 |
| beta_reversion | 0.665 | 0.600 | 0.730 |
| flow_continuation | 0.632 | 0.541 | 0.730 |
| other | 0.619 | 0.541 | 0.750 |

positioning_unwind scores highest — reflecting strong SOL OI accumulation + funding extreme evidence. No branch is pathologically low-scoring (all ≥ 0.541), confirming score calibration is reasonable.

---

## 6. Top-k Stability (vs run_003)

run_003 top-k was all continuation. run_004 top-60 is dominated by positioning_unwind. Stability across seeds/durations cannot be assessed yet (single run). The `survival_across_runs` field returns "N/A (single run)" as expected — requires multi-seed sweep in Sprint F.

---

## 7. Key Design Decisions Validated

1. **Per-asset burst count (min):** Counting burst windows per-asset and using the minimum correctly separates transient-aggression pairs (SOL involved, min=4) from persistent-aggression pairs (ETH/BTC, min=5+).
2. **Absolute rate fallback for is_extreme:** With only 1-2 funding epochs in 120-min data, rolling z_score is always 0. The `abs(funding_rate) > 0.001` fallback ensures FundingPressureRegimeNode fires correctly.
3. **OI accumulation threshold:** SOL's monotonic build from min 50 clears OI_ACCUM_THRESHOLD=3 consecutive growth windows with ≥5% cumulative change. HYPE/ETH/BTC do not accumulate.

---

## 8. Open Issues / Sprint F Targets

- **Suppression imbalance:** 76% of suppressions are `insufficient_negative_evidence`. Sprint F should explore whether the threshold (min burst_count ≤ 4) is too tight or whether the synthetic data needs a HYPE-specific lower-burst scenario.
- **positioning_unwind dominance (50%):** SOL's scenario fires for all 6 pairs. In real data, accumulation would be more selective. Consider pair-specific accumulation thresholds in Sprint F.
- **survival_across_runs:** Requires multi-seed runs to validate hypothesis stability.
