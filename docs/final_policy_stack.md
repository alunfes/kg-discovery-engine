# Final Policy Stack

**Date:** 2026-04-16  
**Status:** FROZEN (Run 044)  
**Scope:** Complete delivery / surface / archive / KG-science policy stack for Epic Allen series

---

## Layer 1: Delivery Policy — LOCKED

### Push Trigger Stack

```
Triggers (ANY fires a review):
  T1: high-conviction incoming card
      → tier ∈ {actionable_watch, research_priority}
      → composite_score ≥ 0.74

  T2: batch size threshold
      → count(high-priority incoming cards) ≥ 3

  T3: aging last-chance (safety net only; dormant in normal operation)
      → card in STATE_AGING
      → time remaining before digest_only transition ≤ 5 min

Suppressions (block review even if trigger fired):
  S1: no actionable cards in deck
      → all cards are digest_only / expired / archived

  S2: all fresh cards are low-priority digest duplicates
      → every fresh/active card is not in HIGH_PRIORITY_TIERS
        AND is part of a family with ≥ 2 members (would collapse)
      NOTE: S2 does NOT block T3 (aging urgency overrides noise suppression)

  S3: rate-limit
      → last push was < 15 min ago

Fallback (fires when no push for > cadence_min):
  quiet days  (hot_prob ≤ 0.25): cadence = 60 min
  hot/trans days (hot_prob > 0.25): cadence = 45 min
```

### Family Collapse

```
Enabled: YES
Min family size: 2
Rule: cards sharing (branch, grammar_family) with ≥ 2 members across assets
      → collapsed into DigestCard (lead = highest composite_score)
      → co-assets listed in one summary line
```

### Performance Targets (achieved)

| Metric | Target | Achieved |
|--------|--------|---------|
| reviews/day | < 25 | 21.0 (Run 031) |
| missed_critical | 0 | 0 (Runs 031, 035, 036) |
| burden vs poll_45min | ≤ poll | −21% (Run 031) |
| quiet-day fallbacks | minimize | −27.8% (Run 036) |

---

## Layer 2: Surface Policy — LOCKED

### Pruning Rules (applied before delivery)

```
Priority order (first matching rule wins):

  1. null_baseline → DROP
     Condition: single non-HYPE tradeable asset in provenance path
     Rationale: intra-asset sequences any naive baseline discovers;
                zero cross-domain signal; HYPE excluded (potential alpha)
     Impact: −5.1% surface, 0% value loss

  2. baseline_like → ARCHIVE
     Condition: secrecy_level == "shareable_structure"
                AND novelty_score ≤ 0.30
                AND NOT null_baseline
     Rationale: minimum-novelty structural patterns; known relationships;
                recoverable via resurface if family later proves important
     Impact: −5.6% surface, 0% action_worthy loss

  3. default → ACTIVE
     All other cards delivered normally
     Impact: 89.2% of input cards
```

### Pipeline Integration Point

```
hypothesis generation
  → value labeling (score_and_convert_all)
  → surface policy  ← HERE (apply_surface_policy + compute_surface_metrics)
  → delivery/surfacing (HypothesisStore.save_batch with active-only)
  → artifact output (_write_artifacts: surfaced / archived / policy_report)
```

### Audit Trail

- `generated_hypotheses.json`: ALL cards (pre-policy, for reproducibility)
- `surfaced_hypotheses.json`: ACTIVE cards only
- `archived_hypotheses.json`: ARCHIVE tier (promotable)
- `surface_policy_report.json`: full metrics

---

## Layer 3: Archive Lifecycle — LOCKED

### State Machine

```
fresh    (age/HL < 0.5)
  ↓ age
active   (0.5 ≤ age/HL < 1.0)
  ↓ age
aging    (1.0 ≤ age/HL < 1.75)   ← T3 monitors this zone
  ↓ age
digest_only (1.75 ≤ age/HL < 2.5)
  ↓ age
expired  (age/HL ≥ 2.5)
  ↓ age ≥ 5× HL
archived (explicit pool; hidden from delivery)
  ↓ same (branch, grammar_family) arrives within 120 min
re-surfaced as fresh (resurface_count++)
  OR
  ↓ archive_max_age elapsed (480 min)
hard-deleted (permanent removal)
```

### Archive Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Archive threshold | 5× half-life | 2.5× buffer beyond expiry; covers full trading session for HL=40 cards (~200 min) |
| Resurface window | 120 min | 2–3 detection cycles for HL=40 min tier; confirmed as LCM-effective |
| Archive max age | 480 min (8 h) | One full trading session horizon; older cards have no positioning relevance |
| Max resurfaces per review | 1 per (branch, grammar_family) | One historical confirmation per family per review |
| Family overrides | None | Uniform policy across all families |

### Accepted Structural Ceiling

| Issue | Value | Accepted? |
|-------|-------|-----------|
| Permanent archive loss (baseline_like) | ~14.5–20.7% | YES — LCM bottleneck; design-correct |
| Sparse-regime recovery | 35–65% | YES — low-value signal in quiet markets; noise suppression working |
| Same-batch resurface rate | 63.9% (TTR=0) | YES — correct; hot batch triggers same-batch confirmation |
| Window=240 improvement | 0.0pp | YES — LCM makes 240 min identical to 120 min |

**LCM phase structure:**
- LCM(batch=30, cadence=45) = 90 min → resurface fires only at coincident review+batch times
- 120-min window covers exactly 1–2 opportunities; 240 min adds a 2nd slot but competing higher-score cards displace it
- Fix requires cadence=batch_interval (cadence=30) OR multi-resurface-per-review allowance

---

## Layer 4: KG Science Policy — LOCKED

### Design Principles (Confirmed)

```
Multi-domain-crossing principle (R-12):
  Any molecular family achieving STRONG_SUCCESS requires:
  1. Chemistry-domain bridge nodes (bio→chem AND chem→bio edges)
  2. 2024–2025 PubMed coverage for endpoint pairs
  These two conditions predict STRONG_SUCCESS regardless of domain.

Pre-filter policy (R-13):
  T3+pf selection (Run 043) preferred over B2 or plain T3:
  - T3+pf: inv=1.000, novelty_ret=1.238, long_share=50%
  - B2:    inv=0.9714, novelty_ret=1.000, long_share=0%
  - T3:    inv=0.8571, novelty_ret=1.342, long_share=50%

Pre-filter score formula:
  prefilter_score = 0.50 * recent_validation_density
                  + 0.20 * bridge_family_support
                  + 0.20 * endpoint_support
                  + 0.10 * path_coherence
```

---

## What Is Locked vs Open vs Accepted Ceiling

### LOCKED (do not change without new experimental evidence)

| Item | Value | Locked Since |
|------|-------|-------------|
| T1 threshold | 0.74 | Run 028 |
| T2 threshold | 3 | Run 028 |
| T3 lookahead | 5 min | Run 031 |
| S1/S2/S3 logic | as implemented | Run 028 |
| Fallback cadence quiet | 60 min | Run 036 |
| Fallback cadence hot | 45 min | Run 035–036 |
| Family collapse min_size | 2 | Run 027 |
| null_baseline DROP rule | HYPE-excluded single-asset | Run 038 |
| baseline_like ARCHIVE rule | shareable_structure + novelty ≤ 0.30 | Run 038 |
| Archive threshold | 5× HL | Run 028 |
| Resurface window | 120 min | Run 040 |
| Archive max age | 480 min | Run 028, 039 |
| Multi-domain-crossing design | bridge nodes + recent coverage | Runs 041, 043 |
| T3+pf pre-filter formula | 0.50/0.20/0.20/0.10 weights | Run 043 |

### OPEN (to be validated with real data or next experiments)

| Item | Reason Open | Next Step |
|------|-------------|-----------|
| Real-data delivery burden | hot_prob unknown on live Hyperliquid | Monitor after production shadow deployment |
| Per-family cadence tuning | Not yet tested (Run 037 recommended) | Run P-fallback-family experiment |
| vol_burst detection | Always 0 in synthetic data | Test with HttpMarketConnector on real data |
| HttpMarketConnector end-to-end | Mock only; real connector untested | Production shadow deployment |
| P11-A pre-filter cold-start | Cache dependency unknown | Run P11-A experiment |
| P11-B cache sensitivity | Minimum coverage threshold unknown | Run P11-B experiment |
| P11-C C_COMBINED (12 nodes) pre-filter | Not yet applied | Run P11-C experiment |

### ACCEPTED AS STRUCTURAL CEILING

| Item | Value | Why Accepted |
|------|-------|-------------|
| Archive permanent loss (baseline_like) | 14.5–20.7% | LCM bottleneck is structural; 0 action_worthy ever lost; design-correct |
| T3 dormancy rate | ~100% | 5-min window + 90-min LCM phase = extremely rare fire; retained as safety net |
| Sparse-regime recovery | 35–65% | Sparse baseline_like = noise suppression working; not a loss of value |
| Surface pruning irreversible drop | 10.8% (21 null_baseline) | null_baseline cards provably zero-value; DROP not archive |

---

## Policy Stack Version

```json
{
  "policy_stack_version": "v2.0",
  "frozen_date": "2026-04-16",
  "frozen_run": "Run 044",
  "delivery_version": "v1.3 (regime-aware fallback; Run 036)",
  "surface_version": "v2.0 (null_baseline + baseline_like; Run 038)",
  "archive_version": "v1.1 (window=120 confirmed; Run 040)",
  "kg_science_version": "v1.0 (domain-agnostic + pre-filter; Runs 041, 043)",
  "next_open_experiment": "P11-A (pre-filter cold-start) + production shadow real-data"
}
```
