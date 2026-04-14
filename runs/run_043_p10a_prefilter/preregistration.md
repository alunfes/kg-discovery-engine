# Pre-Registration: run_043 P10-A Investigability Pre-Filter
*Registered: 2026-04-15 | Author: Claude Sonnet 4.6 | Phase: P10-A*

---

## Research Question

Can a lightweight investigability-aware pre-filter, applied as soft ranking **within** each T3
bucket, close the B2–T3 investigability gap observed in P9 (C_NT_ONLY: gap = −0.114) without
destroying T3's long-path diversity?

---

## Background

P9 (run_041) revealed a critical asymmetry:
- **B2** (global R3 ranking) achieves inv = 0.9714 with C_NT_ONLY (NT bridges only)
- **T3** (3-bucket stratification, L2=35/L3=20/L4+=15) drops to inv = 0.8571 — a gap of −0.114

Root cause: T3 forces 35 slots into L3/L4+ buckets. NT bridges create many L3/L4+ paths with
high e_score_min (good pre-2024 evidence), but those specific endpoint pairs are not actively
researched as novel 2024-2025 targets. B2's global ranking naturally avoids these because
investigated P7/ROS paths dominate the global score.

**Hypothesis**: A pre-filter that weights recent validation evidence within each bucket will
reorder L3/L4+ candidates to prefer investigated-likely paths, closing the gap while
preserving the bucket size guarantees (long-path diversity).

---

## Conditions (3, all using C_NT_ONLY — 5 NT bridge nodes only)

| ID | Selection | Ranker | Description |
|----|-----------|--------|-------------|
| B2 | global top-k | R3 | Structure+Evidence (0.4s + 0.6e), current standard |
| T3 | 3-bucket | e_score_min | L2=35, L3=20, L4+=15 sorted by min edge literature |
| T3+pf | 3-bucket + pre-filter | prefilter_score | Same buckets, internal order by investigability proxy |

**Fixed elements**: ranker=R3 for B2, P9 KG (223 nodes, 469 edges), novelty constraint ≥ 0.90,
TOP_K=70, SEED=42.

---

## Pre-Filter Score Definition

```
prefilter_score(c) = 0.50 * recent_validation_density
                   + 0.20 * bridge_family_support
                   + 0.20 * endpoint_support
                   + 0.10 * path_coherence
```

| Component | Formula | Rationale |
|-----------|---------|-----------|
| recent_validation_density | log10(pubmed_2024_2025+1)/4.0 if cached; else log10(ep+1)/5.0 × 0.6 | Strongest signal for investigability |
| bridge_family_support | min(1, e_score_min / 3.0) | Bottleneck edge literature proxy |
| endpoint_support | min(1, log10(endpoint_pair_count+1) / 5.0) | Pre-2024 endpoint pair density |
| path_coherence | cross_domain_ratio × (2 / path_length) | Structural quality, penalizes long uninformative paths |

**Design principle**: hard exclusion is forbidden. The pre-filter reorders candidates within
each bucket — bucket sizes (35/20/15) remain unchanged.

---

## Pre-Registered Predictions

### Primary hypothesis (H_P10A_1)
> T3+pf investigability ≥ 0.95 (closing the gap from 0.857 toward B2's 0.971)

| Metric | T3 baseline | B2 reference | T3+pf prediction |
|--------|-------------|--------------|-----------------|
| investigability | 0.857 | 0.971 | **≥ 0.95** |
| B2–(T3+pf) gap | −0.114 | 0 | **< −0.030** |

### Secondary hypotheses

| Hypothesis | Prediction | Rationale |
|-----------|------------|-----------|
| H_P10A_2: novelty_retention ≥ 1.0 | T3+pf novelty_ret ≥ 1.0 | Bucket sizes unchanged → diversity preserved |
| H_P10A_3: long_path_share ≥ 0.30 | L3+L4+ share ≥ 0.30 | 35/70 = 50%, cannot drop below 30% |
| H_P10A_4: survival_rate_L3 < 0.80 | Pre-filter reorders ≥ 20% of L3 bucket | NT-path reordering is measurable |
| H_P10A_5: survival_rate_NT_uninv < 0.50 | Uninvestigated NT paths drop out | Pre-filter correctly demotes them |

---

## Success Conditions

- investigability ≥ 0.95
- B2–(T3+pf) gap < −0.030 (from −0.114 baseline)
- novelty_retention ≥ 1.0
- long_path_share ≥ 0.30

## Failure Conditions

- T3+pf collapses to B2-like selection (long_path_share < 0.15 or L4+ depleted)
- novelty_retention < 1.0 (diversity loss)
- T3+pf investigability LOWER than T3 (pre-filter backfires)

---

## 7 Tracked Metrics

1. **investigability** — investigated/total for each selection
2. **novelty_retention** — mean_cdr(selection) / mean_cdr(B2_selection)
3. **long_path_share** — (L3+L4+ paths) / total
4. **survival_rate_by_bucket** — |T3 ∩ T3+pf| per bucket (overlap by endpoint pair)
5. **survival_rate_by_family** — per NT node: investigated_T3pf / investigated_T3
6. **B2–T3 gap** — T3_inv − B2_inv
7. **B2–(T3+pf) gap** — T3pf_inv − B2_inv

---

## Interpretation Table (pre-registered)

| T3+pf inv | B2 gap | Verdict |
|-----------|--------|---------|
| ≥ 0.957 | > −0.015 | STRONG_PREFILTER: matches B2 quality |
| ≥ 0.943 | > −0.030 | PREFILTER_SUCCESS: gap closed substantially |
| 0.900–0.943 | −0.030 to −0.071 | PARTIAL_IMPROVEMENT |
| < 0.900 | < −0.071 | PREFILTER_FAIL |

---

## Artifacts to Produce

- `run_config.json` — full configuration + results
- `comparison_table.json` — B2 × T3 × T3+pf across all 7 metrics
- `survival_analysis.json` — bucket and family survival rates
- `prefilter_score_distribution.json` — score statistics per bucket
- `top70_B2.json`, `top70_T3.json`, `top70_T3pf.json` — full selections
- `review_memo.md` — P10-A findings + P11 implications
