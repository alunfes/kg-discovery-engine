# run_038 Review Memo: P7 KG Expansion
*Date: 2026-04-14 | Phase: P7 | Outcome: STRONG_SUCCESS*

---

## 1. What This Run Tested

P7 tested whether adding chemistry-domain **metabolite bridge nodes** with:
- Incoming edges FROM biology (`bio:pathway:X → produces → chem:metabolite:Y`)
- Outgoing edges TO biology (`chem:metabolite:Y → activates → bio:disease:Z`)

...breaks the geometry ceiling identified in P6-A.

**Mechanism**: these nodes create multi-crossing paths:
```
chem:drug → [activates] → bio:pathway → [produces] → chem:metabolite → [affects] → bio:disease
 [chem]                   [bio]                       [chem]                         [bio]
```
This 3-hop path crosses the chemistry–biology boundary **3 times** → `cross_domain_ratio = 1.0`.

---

## 2. P7 KG Construction

| Item | Baseline | P7 |
|------|----------|----|
| Nodes | 200 | 210 (+10 metabolites) |
| Edges | 325 | 387 (+62) |
| Cross-domain edges | 126 | 188 |
| bio→chem edges | 0 | 26 **(new)** |
| chem→bio edges | 126 | 162 |
| cd_density | 0.388 | 0.486 |

**New metabolite nodes added** (chemistry domain):
NAD+, Glutathione, Ceramide, Prostaglandin E2, Nitric Oxide, cAMP, ROS,
Beta-Hydroxybutyrate, Kynurenine, L-Lactate

---

## 3. Geometry Metrics (H_P7_1 – H_P7_3)

| Metric | Baseline (P6) | P7 | Target | Status |
|--------|--------------|-----|--------|--------|
| M1 cd_density | 0.388 | 0.486 (1.25×) | > 1.5× | ✗ (partial) |
| M2 mean_cdr_L4p | 0.250 | **0.6525** | > 0.30 | ✓ |
| M3 max_L4p_quota | 0 | **70 (unconstrained)** | ≥ 5 | ✓ |
| M1' mean_cdr_L3 | 0.333 | **0.619** | ≥ 0.400 (H_P7_2) | ✓ |
| Unique endpoint pairs | 90 | **959** | ≥ 200 (H_P7_1) | ✓ |
| H_P7_3 L4+ quota > 20 | 0 | 70 | > 20 | ✓ |

**All 3 primary geometry hypotheses confirmed.**

Key finding: M2 = 0.6525 >> 0.30 target. The novelty constraint is **mathematically unconstrained**
at this cdr level — any combination of L2/L3/L4+ satisfies `novelty_retention ≥ 0.90`.

Multi-crossing paths discovered:
- L3 with ≥2 crossings: **190 / 443** (43%)
- L4+ with ≥2 crossings: **1044 / 1308** (80%)

---

## 4. Experiment Results (3 Conditions)

### Condition summary

| Condition | Inv rate | Novelty ret | Long-path share | Design |
|-----------|----------|-------------|-----------------|--------|
| B1_P7 | 0.8857 | 1.000 | 0.000 | global R1, all L2 |
| B2_P7 | 0.9714 | 1.000 | 0.000 | global R3, all L2 |
| **T3_P7** | **0.9857** | **1.319** | **0.500** | 3-bucket R2 (L2=35/L3=20/L4+=15) |

### T3_P7 stratum breakdown

| Stratum | n | Investigated | Inv rate | Mean cdr |
|---------|---|-------------|----------|----------|
| L2 | 35 | 34 | 0.9714 | 0.500 |
| L3 | 20 | **20** | **1.000** | **0.833** |
| L4+ | 15 | **15** | **1.000** | **0.800** |
| **Total** | **70** | **69** | **0.9857** | **0.660** |

**L3 and L4+ strata: 100% investigability.** The bridge paths are exceptionally well-supported.

### Key comparisons

| Comparison | Delta | Interpretation |
|------------|-------|----------------|
| T3_P7 vs B2_P7 | +0.0143 | Bucketed beats evidence-aware global ranker |
| T3_P7 vs P6-A T2 | +0.0571 | +5.7pp over previous best |
| T3_P7 vs P4 ceiling | +0.0457 | +4.6pp over historical 0.943 ceiling |
| B2_P7 vs P6-A B2 | +0.0285 | KG expansion ALSO improves baseline |

---

## 5. Outcome Determination

**Pre-registered success criteria (p7_preregistration.md §3):**

| Level | Criteria | Achieved |
|-------|----------|---------|
| **Strong success** | M4 > 0.943 AND M5 ≥ 0.90 AND M6 > 0.30 | **ALL MET** |
| Weak success | M4 > 0.929 AND M5 ≥ 0.90 | (superseded) |

**Verdict: STRONG_SUCCESS — P7 breaks the geometry ceiling.**

---

## 6. What Happened Mechanistically

### The geometry ceiling was broken by metabolite bridges

Before P7, every path had exactly 1 domain crossing:
```
chem_node → [single_crossing] → bio_node    (cdr = 1/L for all L)
```

After P7, multi-crossing paths exist:
```
drug → pathway → metabolite → disease       (3 crossings / 3 hops = cdr 1.0)
drug → pathway → metabolite → protein → disease (3 crossings / 4 hops = cdr 0.75)
```

The metabolite nodes act as **second domain-crossing anchors**, creating paths that oscillate
between chemistry and biology. This was the exact structural change needed to break the ceiling.

### Why L3/L4+ paths are 100% investigable

The bridge paths go through well-known metabolites (NAD+, ROS, ceramide, prostaglandins)
that have rich PubMed coverage. The `drug → metabolite → disease` connections are precisely
the type of translational hypotheses that active research investigates in 2024-2025.

Examples of multi-crossing bridge paths:
1. `metformin → [AMPK] → NAD+ → [sirt1] → Alzheimer's` (longevity-metabolism axis)
2. `curcumin → [NF-kB] → PGE2 → [inflammation] → rheumatoid arthritis` (anti-inflammatory)
3. `CoQ10 → [mitochondria] → ROS → [oxidative stress] → Parkinson's` (neuroprotection)

### Why T3 beats B2 on investigability

In P6-A, T2 was 0.6pp BELOW B2 (0.929 vs 0.943). In P7, T3 is 1.4pp ABOVE B2 (0.986 vs 0.971).
The change: P7 bridge paths are **MORE investigable** than L2-only paths. The metabolite
intermediates provide PubMed-searchable anchors that make the endpoint pairs easy to find
in validation literature.

---

## 7. Conclusion

> **P7 STRONG_SUCCESS: The geometry ceiling is broken.**
>
> KG expansion with cross-domain metabolite bridge nodes creates multi-crossing paths
> with cdr >> 0.333. The novel T3 bucketed selection (L2/L3/L4+) achieves:
> - investigability = 0.9857 (69/70) — exceeds the 0.943 P4 historical ceiling
> - novelty_retention = 1.319 — MORE diverse than the L2-only baseline
> - long_path_share = 50% — half the selected candidates are multi-hop bridge paths
>
> The ceiling (1/L) was a structural property of the single-bridge KG. Adding biology-producing
> metabolite nodes creates a multi-bridge KG where longer paths can have higher cdr than
> shorter ones.

---

## 8. Implications for P8

| Finding | P8 Direction |
|---------|-------------|
| T3 beats B2 | Bucketed selection is now the recommended standard |
| L3/L4+ inv = 1.0 | Go deeper: test L5+ paths (max_depth extended) |
| Mean_cdr_L3 = 0.833 | Further KG expansion can add more metabolite diversity |
| 959 unique pairs | Pool is rich enough for multi-seed experiments |
| B2_P7 also improved | KG expansion helps even naive global ranking |

**Recommended P8 direction:**
1. Extend to L5/L6 paths (increase MAX_DEPTH to 6)
2. Test whether 3-bucket or 4-bucket (L2/L3/L4/L5+) further improves M4
3. Add more metabolite bridge types (e.g., neurotransmitters, lipid signaling molecules)
4. Formal statistical tests (Fisher exact) with larger N

---

## 9. Run Artifacts

| File | Description |
|------|-------------|
| `run_config.json` | Full configuration |
| `geometry_metrics.json` | M1-M3 structural geometry metrics |
| `metrics_by_condition.json` | M4-M6 per condition |
| `decision.json` | Outcome determination |
| `top70_B1_P7.json` | B1_P7 selected candidates |
| `top70_B2_P7.json` | B2_P7 selected candidates |
| `top70_T3_P7.json` | T3_P7 selected candidates |
| `evidence_cache.json` | Extended evidence cache (1242 entries) |
| `pubmed_cache.json` | Extended validation cache |
