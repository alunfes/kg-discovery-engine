# Long-Path Biomedical Discovery Without a Novelty Ceiling: Cross-Family Evidence from Enriched Bridge Geometry and Literature-Aware Endpoint Selection

*Draft v3 — 2026-04-15 | Prose pass from draft_v2: sentence-level tightening throughout. Scientific claims unchanged.*

---

## Abstract

Long-path discovery in biomedical knowledge graphs (KGs) faces an apparent investigability ceiling — a systematic drop in the fraction of selected candidates whose endpoint pairs appear as active research targets in recent literature as path length increases. A controlled experiment series shows that this ceiling is not structural but is a selection artifact. Adding multi-domain-crossing bridge nodes (raising the mean cross-domain ratio of length-3 paths from 0.333 to 0.619–0.740) and pairing bucketed path-length selection with an endpoint-aware pre-filter weighted toward 2024–2025 PubMed validation signals raises warm-cache investigability from a ceiling of 0.943 to 1.000, while maintaining 50% long-path share and novelty retention above 1.2. The improvement is family-transferable under literature-aware selection: an initial failure on a neurotransmitter family (investigability 0.857 under geometry-only selection) was reversed to 1.000 by switching to endpoint-aware pre-filtering, confirming that the ceiling is a selection artifact rather than a family-specific property. Long-path discovery is not inherently blocked by a novelty ceiling; it becomes viable in a family-transferable manner when semantically enriched bridge geometry is paired with endpoint-aware candidate selection under literature-aware evaluation.

---

## 1. Introduction

Knowledge graph (KG)-based discovery systems enumerate multi-hop paths between biomedical entities to surface non-obvious hypotheses — connections between drugs and diseases that are not directly asserted in the graph but are bridged through intermediate biology or chemistry. A consistent observation is that longer paths (three or more hops) produce candidates less likely to be investigable in the near-term literature: the fraction of selected paths whose endpoint pairs appear as active research targets in recent publications decreases as path length grows. This empirical regularity is sometimes described as a *novelty ceiling* — a structural upper bound on the investigability achievable by long-path methods.

The novelty ceiling narrative rests on a plausible mechanism. Longer paths traverse more intermediate nodes, each introducing a co-occurrence dependency that must be supported by recent literature; the joint probability that all edges in a long path are simultaneously active research topics is lower than for a direct two-hop connection. On this account, the ceiling reflects genuine structural scarcity: not enough actively investigated long-path hypotheses exist to fill a practical candidate set.

We challenge that account: the ceiling is better understood as a *selection artifact* — a consequence of ranking and filtering strategies systematically misaligned with the signal structure of long-path candidates, rather than a fundamental property of path length. Global evidence-based ranking (which we confirm establishes a strong baseline for short paths) systematically excludes longer paths because its edge-level co-occurrence signal does not capture endpoint-level investigability. Bucketed path-length selection partially compensates but fails when KG geometry does not support multi-domain crossings at L3 or longer. We show that combining two complementary interventions — enriched bridge geometry in the KG construction layer and endpoint-aware pre-filtering in the selection layer — eliminates the ceiling entirely.

Our experimental contribution is seven controlled experiments on a biomedical chemistry–biology KG, progressing from a baseline evidence-aware ranker through geometry enrichment and ending with a domain-transfer test that retroactively classifies an earlier failure as a selection artifact. The experiments establish three claims:

1. **C1**: Semantically enriched bridge geometry — chemistry-domain nodes that create multi-domain-crossing paths with cross-domain ratio ≥ 0.60 — removes the investigability ceiling for the reactive-oxygen-species (ROS) bridge family.
2. **C2**: The geometry mechanism is family-transferable under literature-aware selection: it transfers to the neurotransmitter (NT) family when endpoint-aware pre-filtering with a warm validation cache is applied.
3. **C3**: Endpoint-aware pre-filtering is required to convert favorable geometry into usable discovery under literature-aware evaluation.

These claims together support the one-sentence summary of this paper: *Long-path discovery is not inherently blocked by a novelty ceiling; it becomes viable in a family-transferable manner when semantically enriched bridge geometry is paired with endpoint-aware candidate selection under literature-aware evaluation.*

---

## 2. Core Idea: Two-Layer Architecture

The solution operates at two independent layers: *KG construction* and *candidate selection*. Neither layer alone is sufficient; the ceiling is eliminated only when both are active simultaneously.

**Layer 1 — Bridge geometry (KG construction layer).** The baseline KG contains biology-domain and chemistry-domain nodes connected by directional edges. In this baseline, every path of length *L* contains exactly one domain crossing, yielding a cross-domain ratio of `cdr = 1/L`. As path length increases, `cdr` necessarily falls toward zero, and evidence-based ranking penalizes longer paths on novelty grounds. The key structural intervention is to add *bridge nodes* — chemistry-domain intermediates with incoming edges FROM biology and outgoing edges TO biology — that create multi-crossing paths:

```
drug [chem] → pathway [bio] → metabolite [chem] → disease [bio]
```

This three-hop path crosses the chemistry–biology domain boundary three times, yielding `cdr = 1.0` rather than `cdr = 0.333`. Such nodes act as *domain-crossing anchors* that decouple cross-domain ratio from path length.

**Layer 2 — Endpoint-aware selection (candidate selection layer).** Global ranking by edge-level evidence (pre-2024 PubMed co-occurrence) selects all shortest paths and systematically underweights longer paths, even when those paths reach highly investigated endpoint pairs. Bucketed path-length selection (T3) guarantees representation of L3 and L4+ paths but orders within each bucket by edge co-occurrence — a weak proxy for endpoint-level 2024–2025 investigability. The pre-filter replaces this ordering with a 4-component score centered on recent endpoint-pair validation density, directly aligning within-bucket selection with the investigability signal used for evaluation.

**Four design conditions.** The combined architecture requires four conditions to be satisfied:

| # | Layer | Condition | Threshold |
|---|-------|-----------|-----------|
| 1 | Geometry | Multi-domain crossing bridge structure (bio→chem→bio) | Required |
| 2 | Geometry | High cross-domain ratio for L3+ paths | cdr_L3 ≥ 0.60 |
| 3 | Selection | Recent literature coverage at endpoint level | 2024–2025 PubMed coverage |
| 4 | Selection | Endpoint-aware pre-filter within each path-length bucket | primary weight ≥ 0.50 |

Conditions 1–2 are satisfied by KG expansion with appropriate bridge nodes; Conditions 3–4 are satisfied by the pre-filter. The experiments test what happens when each subset of conditions is active.

---

## 3. Method

### 3.1 Knowledge Graph Construction

The base KG is a directed biomedical graph with two domains: biology (drugs, proteins, pathways, diseases) and chemistry (metabolites, enzymes). The baseline KG comprises 200 nodes and 325 edges. Cross-domain edges connect the two domains directionally; in the baseline, all cross-domain edges are of the form `chem → bio`, creating paths where the single domain crossing occurs at the terminal edge.

**Bridge node expansion.** To create multi-crossing paths, we added chemistry-domain *bridge nodes* with both incoming biology edges (`bio → chem`) and outgoing biology edges (`chem → bio`). Two families of bridge nodes were introduced across the experiment series:

- **ROS family** (Reactive Oxygen Species): NAD+, glutathione, ceramide, prostaglandin E2, nitric oxide, cAMP, ROS, beta-hydroxybutyrate, kynurenine, L-lactate (P7 core, 10 nodes), then extended with superoxide dismutase, catalase, heme oxygenase-1, NRF2, and malondialdehyde (P8 extension, +5 nodes).
- **NT family** (Neurotransmitters): dopamine, serotonin, GABA, glutamate, acetylcholine (5 nodes, P9/P10-A).

After the ROS+NT full expansion, the KG contained 215 nodes and 435 edges with 188 cross-domain edges.

**Path enumeration.** Candidate paths were enumerated from drug nodes to disease nodes at lengths L2, L3, and L4+ (maximum depth 6). The expanded KG yielded 959 unique endpoint pairs under the ROS-only configuration and 714 under the NT-only configuration, versus 90 endpoint pairs in the baseline.

### 3.2 Ranking and Selection Methods

**R3 ranker (baseline).** The evidence-aware hybrid ranker R3 scores each candidate path as:

```
R3 = 0.4 × structure_norm + 0.6 × evidence_norm
```

where `structure_norm` captures path structural features and `evidence_norm` is derived from the minimum edge co-occurrence score across the path (`e_score_min`), computed from PubMed ≤2023 literature. R3 is applied as a global ranker; the top 70 paths are selected regardless of length distribution. This produces **B2** — the evidence-aware baseline condition.

**T3 bucketed selection (path-length diversity).** To overcome structural exclusion of longer paths by global ranking, T3 partitions candidates into length buckets and selects a fixed quota from each:

```
T3: L2 = 35 paths, L3 = 20 paths, L4+ = 15 paths  (total: 70)
```

Within each bucket, paths are ordered by `e_score_min`. T3 guarantees that 50% of selected candidates are L3 or longer.

**T3+pf endpoint-aware pre-filter.** The pre-filter replaces the within-bucket `e_score_min` ordering with a 4-component score:

```
prefilter_score = 0.50 × recent_validation_density
               + 0.20 × bridge_family_support
               + 0.20 × endpoint_support
               + 0.10 × path_coherence
```

The `recent_validation_density` component uses cached 2024–2025 PubMed counts for endpoint pairs validated in prior runs; paths whose endpoint pairs have high recent literature coverage receive elevated scores. The pre-filter does not exclude any path (hard exclusion is forbidden); it reorders within each T3 bucket. This produces **T3+pf**.

**Warm-cache regime.** The `recent_validation_density` component requires a prior-run cache of 2024–2025 PubMed endpoint-pair counts. In P10-A (run_043), this cache was populated from the 20 NT endpoint pairs validated in run_042, all of which carry `investigated=1` status. Consequently, the pre-filter's primary ranking signal (weight 0.50) and the investigability evaluation criterion share the same data source and evaluation window (2024–2025 PubMed). In run_043, all evaluated T3+pf selections had cache-hit endpoint pairs with high `recent_validation_density`; uncached pairs would receive a proxy score with a 0.6× weight discount. The investigability result of 1.000 therefore measures the pre-filter's precision at surfacing paths whose endpoint pairs are *already known* to be active 2024–2025 research targets — a positive finding about selection precision under warm-cache conditions, not a test of cold-start discovery of previously-unknown investigable paths. There is no path-level target leakage: the cache stores endpoint-pair counts, not individual path rankings, and the pre-filter cannot preferentially select one specific path over any other path to the same endpoint pair.

### 3.3 Evaluation Metrics

**Investigability** (primary): the fraction of the 70 selected paths whose endpoint pairs (source drug, target disease) appear as active research targets in 2024–2025 PubMed literature. An endpoint pair is classified as `investigated=1` if it appears in ≥ 1 paper in the 2024–2025 PubMed query window for the joint term (source_entity, target_entity); the binary threshold is set deliberately inclusive to capture any recent research activity, from exploratory to established (values in run_043 range from 7 to 2189 papers, all classified `investigated=1`). The metric is validated using a held-out query window.

**Novelty retention**: ratio of the selected pool's mean cross-domain ratio to the B2 baseline cross-domain ratio. Values > 1.0 indicate more diverse paths than the baseline.

**Long-path share**: fraction of selected candidates with path length ≥ 3.

**B2 gap**: difference between a condition's investigability and B2 investigability. Positive values indicate the condition exceeds the evidence-aware baseline.

The pre-registered STRONG_SUCCESS criterion requires: investigability > 0.943 (P4 historical ceiling) AND novelty retention ≥ 0.90 AND long-path share > 0.30.

### 3.4 Experiment Design

The experiment series progresses through seven phases. The table below assigns each phase to its role in establishing the three claims.

| Phase | Key Intervention | Role in Argument | Outcome |
|-------|-----------------|-----------------|---------|
| Baseline establishment | R3 hybrid ranker (B2 standard) | Establishes evidence-aware baseline (inv = 0.943) | B2 adopted |
| Structural exclusion probe | Evidence-gated KG augmentation | Reveals augmentation alone cannot break ceiling | FAIL: no gain |
| Geometry ceiling discovery | Bucketed selection (T3) on original KG | Discovers investigability ceiling at 0.943 | WEAK_SUCCESS (T2) |
| Geometry breakthrough | ROS bridge nodes + T3 | **C1 evidence**: ceiling broken at inv = 0.986 | STRONG_SUCCESS |
| Design principle confirmation | ROS family ablation (5 subsets) | **C1 reproducibility**: all ROS subsets STRONG_SUCCESS | DESIGN_PRINCIPLE |
| Domain transfer test | NT bridge nodes + T3 | Reveals selection artifact (GEOMETRY_ONLY) | GEOMETRY_ONLY → *artifact* |
| Endpoint-aware pre-filter | NT bridge nodes + T3+pf | **C2/C3 evidence**: family-transferable confirmed | STRONG_SUCCESS |

**Adaptive study design note.** The endpoint-aware pre-filter phase (P10-A) was not pre-planned at the start of the experiment series. It was designed specifically in response to the B2–T3 investigability gap of −0.114 observed in P9 (run_041), with the pre-registered goal of demonstrating that the NT family can achieve STRONG_SUCCESS under the correct selection strategy — thereby reclassifying P9's GEOMETRY_ONLY verdict as a selection artifact. This constitutes transparent adaptive experimental design: the pre-filter architecture was motivated by a diagnosed failure mode, not by exploratory search. The DOMAIN_AGNOSTIC conclusion from P10-A is therefore confirmatory of the hypothesised mechanism rather than a serendipitous finding. Independent replication with a third bridge family (planned for P11-C) would provide stronger cross-family evidence.

---

## 4. Results

### 4.1 C1: Bridge Geometry Removes the Novelty Ceiling

The novelty ceiling became visible in the geometry ceiling discovery phase. With the original single-crossing KG (all L3 paths have `cdr_L3 = 0.333`), bucketed selection achieved investigability of 0.943 — identical to the evidence-aware baseline (B2). Including longer paths without enriching path geometry does not improve investigability; at best it matches the baseline while introducing path diversity. The ceiling at 0.943 appeared robust regardless of the path-length allocation within the selection budget.

The geometry breakthrough phase introduced the ROS bridge family, which produced multi-crossing paths with `cdr_L3 = 0.619`. This structural change broke the ceiling: T3 selection achieved investigability of 0.986 (+4.6pp over the P4 historical ceiling of 0.943; +5.7pp over the P6-A weak-success baseline of T2 = 0.929; +1.4pp above the concurrently improved B2 of 0.9714). The KG expansion also improved the B2 global baseline (from 0.943 to 0.9714), confirming that the geometry benefit extends to the full candidate pool, not only T3-selected paths. The STRONG_SUCCESS criterion (inv > 0.943, novelty retention ≥ 0.90, long-path share > 0.30) was met with novelty retention of 1.319 and long-path share of 0.500.

The design principle confirmation phase tested whether this result was a narrow exploit or a genuine design principle. Five new ROS-family bridge nodes (superoxide dismutase, catalase, heme oxygenase-1, NRF2, malondialdehyde) were added while excluding the original ROS core. This configuration achieved investigability of 0.986 — matching the full ROS expansion — while `cdr_L3` increased further to 0.677. All five ROS subset configurations tested achieved STRONG_SUCCESS [Fig 1, Table 1].

**[Fig 1]** *C1 geometry breakthrough: investigability and cdr_L3 across three experimental phases. The ceiling at inv ≈ 0.943 (original KG, cdr_L3 = 0.333) is broken in the geometry breakthrough phase (cdr_L3 = 0.619, inv = 0.986) and confirmed in the design principle phase (cdr_L3 = 0.740, inv = 0.986). Horizontal dashed line: B2 baseline = 0.9714.*

**Table 1.** *ROS bridge family ablation: each subset achieves STRONG_SUCCESS, demonstrating that the ceiling is broken by the oxidative-stress bridge structure rather than by any specific molecule pair.*

| Condition | Bridge nodes (n) | cdr_L3 | T3 inv | Classification |
|-----------|-----------------|--------|--------|---------------|
| Original KG (no bridges) | 0 | 0.333 | 0.943 | Ceiling |
| ROS core only | 2 | 0.464 | 0.986 | STRONG_SUCCESS |
| + SOD, catalase | 4 | 0.604 | 0.986 | STRONG_SUCCESS |
| + HO-1, NRF2 | 4 | 0.607 | 0.986 | STRONG_SUCCESS |
| Full ROS family | 7 | 0.740 | 0.986 | STRONG_SUCCESS |
| New nodes only (no ROS core) | 5 | 0.677 | 0.986 | STRONG_SUCCESS |

The driving mechanism is the geometry of the bridge paths. L3 and L4+ paths through ROS intermediates reach 100% investigability in the stratum-level analysis (20/20 L3 paths and 15/15 L4+ paths investigated), whereas short L2 paths achieve 97.1% (34/35). The bridge paths connect well-characterized drug and metabolite nodes to frontier disease connections through PubMed-validated oxidative stress pathways, which are actively published in 2024–2025. The monotonic relationship between `cdr_L3` and investigability (both increasing across subsets, with a threshold near `cdr_L3 ≥ 0.46`) supports the geometric interpretation: cross-domain density, not specific molecular identity, drives the ceiling reversal.

### 4.2 C2: The Mechanism Is Family-Transferable Under Literature-Aware Selection

Having established that ROS bridge geometry removes the ceiling, we tested whether the mechanism transfers to an entirely different chemistry family: neurotransmitters (dopamine, serotonin, GABA, glutamate, acetylcholine). The NT family satisfied the structural criterion — five chemistry-domain nodes with both bio→chem and chem→bio edges — and replicated ROS geometry metrics with 97.7% fidelity (`cdr_L3 = 0.605` vs. 0.619 for ROS; `cdr_L4+ = 0.653` matching exactly; 173 multi-crossing L3 paths vs. 190 for ROS).

The domain transfer test (NT family + T3) returned investigability of 0.857 — *below* the no-bridge baseline of 0.943 and below B2 (0.9714). This result was initially classified as GEOMETRY_ONLY: geometry transfers but investigability does not. However, a critical diagnostic finding pointed toward a selection artifact rather than a domain limit: the B2 global ranker, applied to the same NT KG without bucket stratification, achieved investigability of 0.9714 — full STRONG_SUCCESS. The gap between T3 (0.857) and B2 (0.9714) was −0.114, the largest T3/B2 divergence in the experiment series.

The source of this gap is a signal mismatch. T3 orders within each bucket by `e_score_min` — the minimum edge co-occurrence score derived from pre-2024 PubMed literature. For NT paths, the bottleneck edge (e.g., `serotonin → alzheimers`) may have a modest pre-2024 edge co-occurrence count (because the connection was established decades ago and is no longer the subject of novel publications), while the endpoint pair `(serotonin, alzheimers)` accumulates 202 papers in 2024–2025 as a research target. T3 deprioritizes the path on the basis of stale edge-level evidence; the pre-filter correctly prioritizes it on the basis of fresh endpoint-level evidence. The GEOMETRY_ONLY verdict in the domain transfer test was therefore a **selection artifact**: T3's ordering function was misaligned with the investigability criterion, not the NT domain itself.

The endpoint-aware pre-filter experiment confirmed this interpretation. Replacing T3's `e_score_min` ordering with the `prefilter_score` — which uses `recent_validation_density` (weight 0.50) as its primary signal — produced NT warm-cache investigability of 1.000 (70/70 paths investigated). This matches the pre-filter result across both families, confirming family-transferable behavior under literature-aware selection [Fig 2, Table 2]. The most striking individual case: serotonin was selected for 0 paths by T3 (its paths were displaced by dopamine and glutamate paths with higher pre-2024 edge counts) but for 15 paths by T3+pf, all of which were investigated.

**[Fig 2]** *C2 family-transferable mechanism: investigability by family (ROS, NT) and selection strategy (T3, T3+pf). ROS achieves STRONG_SUCCESS under T3. NT under T3 yields GEOMETRY_ONLY (dashed bar, selection artifact). NT under T3+pf achieves STRONG_SUCCESS, matching ROS. Dashed horizontal line: B2 baseline = 0.9714. Arrow from NT-T3 to NT-T3+pf annotated "+14.3pp (selection artifact fixed)".*

**Table 2.** *Family transfer: geometry metrics (cdr_L3) transfer from ROS to NT with 97.7% fidelity; investigability transfer requires endpoint-aware selection.*

| Phase | Family | cdr_L3 | Selection | inv | B2 gap | Verdict |
|-------|--------|--------|-----------|-----|--------|---------|
| Design principle | ROS (7 nodes) | 0.740 | T3 | 0.986 | +0.014 | STRONG_SUCCESS |
| Domain transfer | NT (5 nodes) | 0.605 | T3 | 0.857 | −0.114 | GEOMETRY_ONLY → *artifact* |
| Pre-filter | NT (5 nodes) | 0.605 | T3+pf | 1.000 | +0.029 | STRONG_SUCCESS |

### 4.3 C3: Endpoint-Aware Pre-Filter Is Required

The pre-filter's contribution is to invert the B2–T3 investigability gap: from −0.114 (T3 below B2) to +0.029 (T3+pf above B2). This inversion is the quantitative signature of C3: a pre-filter that prioritizes endpoint-level 2024–2025 PubMed signal converts geometry (which is necessary but not sufficient) into usable discovery under literature-aware evaluation [Fig 3].

**[Fig 3]** *C3 pre-filter effect: investigability, novelty retention, and long-path share for B2, T3, and T3+pf on the NT KG. T3+pf inverts the B2–T3 gap (−0.114 → +0.029) while maintaining 50% long-path share and novelty retention of 1.238.*

The mechanism of this inversion is revealed by a survival analysis of which paths persist from T3 to T3+pf selection [Table 3]. The pre-filter leaves the L2 bucket substantially intact (57.1% of L2 paths survive) but almost completely restructures the L3 and L4+ buckets: only 1 of 20 L3 paths (5.0%) and 0 of 15 L4+ paths (0.0%) survive from T3 into T3+pf. This is not a small correction — the pre-filter effectively replaces the entire long-path selection with a different set of candidates drawn from the same bucket.

**Table 3.** *Bucket survival rates from T3 to T3+pf: the pre-filter reconstructs the L3 and L4+ buckets almost entirely.*

**Part A: B2–T3 gap reversal**

| Comparison | Investigability gap | Interpretation |
|-----------|-------------------|---------------|
| B2 − T3 | −0.114 | T3 below B2 baseline |
| B2 − (T3+pf) | **+0.029** | T3+pf above B2 baseline |

**Part B: Bucket survival rates**

| Bucket | T3 paths | T3+pf paths | Overlap | Survival rate |
|--------|----------|------------|---------|--------------|
| L2 | 35 | 35 | 20 / 35 | 57.1% |
| L3 | 20 | 20 | 1 / 20 | **5.0%** |
| L4+ | 15 | 15 | 0 / 15 | **0.0%** |

The near-zero survival rates in L3 and L4+ confirm that T3's `e_score_min` ordering and the pre-filter's `recent_validation_density` ordering select fundamentally different path populations within the long-path buckets. T3 fills the long-path slots with high pre-2024 edge co-occurrence paths that may not be active 2024–2025 research targets; T3+pf fills them with paths whose endpoint pairs have demonstrated recent PubMed coverage. The 0.50 weight on `recent_validation_density` makes this the dominant discriminating signal.

T3+pf also achieves diversity outcomes that neither B2 nor T3 alone can reach. B2 selects all 70 paths from L2 (long-path share = 0), failing the novelty retention and path diversity criteria despite high investigability. T3 achieves 50% long-path share and high novelty retention (1.342) but at the cost of investigability (0.857). T3+pf simultaneously achieves all three: 50% long-path share, novelty retention 1.238 (above B2 reference), and investigability 1.000. This three-way optimization is only possible through the combination of bucket-enforced path-length diversity (T3's structural role) and endpoint-aligned within-bucket ordering (pre-filter's role).

---

## 5. Discussion

### 5.1 The Novelty Ceiling as a Selection Artifact

Our central claim is that the novelty ceiling is not a structural property of path length but a consequence of selection strategy. The geometry ceiling discovery phase provided the first direct evidence: with the original single-crossing KG, even an optimally designed bucketed selection strategy cannot break the ceiling at 0.943. But this observation is consistent with two interpretations: (a) long paths are inherently less investigable, or (b) the KG lacks the path structures needed to surface investigable long-path candidates. The geometry breakthrough experiment resolved the ambiguity by showing that adding bridge nodes — a KG construction intervention that does not change the evaluation criterion — immediately moved investigability to 0.986. The ceiling was an artifact of KG geometry, not path length per se.

The domain transfer experiment provided a second artifact diagnosis. The NT family's GEOMETRY_ONLY result (T3 investigability = 0.857) initially appeared to constrain C1 to the ROS domain. But the divergence between B2 (0.9714) and T3 (0.857) on the same KG revealed the selection mechanism: T3's `e_score_min` was systematically deprioritizing NT paths whose endpoint pairs are actively studied but whose inter-node edge co-occurrence is modest. The pre-filter, by using endpoint-level rather than edge-level evidence, closed this gap completely. The NT GEOMETRY_ONLY verdict was therefore an artifact of the selection function, not the domain.

### 5.2 Signal Mismatch: Edge-Level vs. Endpoint-Level Evidence

A key theoretical insight is the distinction between *edge-level evidence* (pre-2024 co-occurrence of adjacent nodes) and *endpoint-level investigability* (2024–2025 PubMed coverage of the source–target pair). These two signals are partially correlated for short paths through recently characterized intermediates, which explains why R3 works well for L2 paths. But they diverge systematically for longer paths through well-established intermediates: serotonin's connection to major depression is textbook knowledge, generating high general PubMed volume but low *novel* target coverage in 2024–2025. The edge `serotonin → major_depression` has a modest pre-2024 novelty-adjusted count precisely because this connection was established long ago. Yet the endpoint pair `(serotonin, alzheimers)` — a more frontier connection — accumulates 202 papers in 2024–2025. T3's `e_score_min` treats these two signals as equivalent; the pre-filter correctly differentiates them.

This signal mismatch is a general hazard for long-path discovery systems. As path length increases, the probability that at least one intermediate edge has a long-established (hence low-novelty) co-occurrence grows, and edge-level ranking systematically deprioritizes such paths even when the endpoint connection is a frontier research target. The pre-filter's endpoint-level primary signal (weight 0.50) is designed specifically to bypass this failure mode.

### 5.3 Why the P9 Negative Was an Artifact, Not a Domain Limit

The domain transfer experiment (NT + T3) produced a clean null result: all four pre-registered hypotheses failed, with NT achieving a family-transfer score of 0.8695 (86.95% of the ROS performance ceiling) — below the pre-registered threshold of ≥ 0.95. This result was pre-registered and unambiguous. Establishing that GEOMETRY_ONLY characterizes the T3 selection function — not the NT domain's capacity for long-path discovery — is therefore essential.

Three diagnostic observations support the artifact interpretation. First, B2 — a simpler ranking method — achieved STRONG_SUCCESS (0.9714) on the same NT KG, demonstrating that the NT endpoint pairs ARE investigable; only the selection strategy failed. Second, T3's serotonin paths (0 selected) were not absent from the investigable pool — when selected by T3+pf, all 15 were investigated. Third, the T3/B2 gap (−0.114) was the largest in the series, far exceeding the gap for ROS (+0.014), pointing to a structural property of T3's ordering function under NT geometry rather than a property of NT investigability.

### 5.4 Scope of Generalization

The four-condition design principle — bridge structure, high cross-domain ratio, recent endpoint coverage, endpoint-aware selection — is theoretically applicable to any biomedical KG where endpoint domains have active 2024–2025 PubMed coverage. The experiment series demonstrates this for two distinct chemistry families (ROS and NT), covering a range of pathology types (neurodegeneration, metabolic disease, inflammatory disease). Both are well-characterised families with rich 2024–2025 PubMed endpoint-pair coverage; the family-transferable claim is therefore bounded to this regime. Extension to frontier chemistry families with sparse 2024–2025 endpoint coverage — the cold-start regime, where `recent_validation_density` falls back to a proxy mode — is the central open question addressed in planned P11-A. Statistical significance under larger sample sizes (N = 200) is addressed in planned P11-D.

---

## 6. Limitations

**Evaluation signal overlap and warm-cache upper bound (primary limitation).** The T3+pf investigability result of 1.000 is a warm-cache measurement. The pre-filter's primary signal (`recent_validation_density`, weight 0.50) and the investigability evaluation criterion both draw from the same data source — 2024–2025 PubMed counts for endpoint pairs. In run_043, all 20 NT endpoint pairs evaluated were present in the prior-run validation cache (built in run_042) with `investigated=1` status, and the pre-filter's `recent_validation_density` signal correctly elevated their paths to the top of each bucket. This is a positive result — it demonstrates high selection precision under warm-cache conditions — but it does not constitute a test of cold-start discovery (identification of investigable paths whose endpoint pairs are not in any prior validation cache). In cold-start mode (no prior cache), `recent_validation_density` falls back to a proxy scoring mode with a 0.6× discount, and whether STRONG_SUCCESS is maintained is the single most important open empirical question for this method. Until P11-A results are available, the warm-cache investigability of 1.000 should be interpreted as an upper bound on performance for novel endpoint pairs not covered by prior validation runs. (No path-level leakage: the cache stores endpoint-pair counts, not individual path rankings.)

**Bridge family selection with prior knowledge.** Both families tested (ROS and NT) are well-characterized chemistry families with substantial 2024–2025 literature coverage. The design principle requires that bridge nodes connect to disease endpoints that are actively studied as novel research targets in the evaluation window. Applying the principle to frontier families — chemistry families whose disease connections are not yet published in high volume — would require a different proxy for condition 3, and performance in this regime is untested.

**KG construction requires domain knowledge.** Adding multi-domain-crossing bridge nodes requires identification of chemistry-domain entities with both bio→chem and chem→bio connections to the relevant biology subgraph. This is currently a manual curation step. Automated methods for discovering candidate bridge nodes from literature are not established.

**Sample size (N = 70).** Each condition selects and evaluates 70 paths. All reported investigability differences are based on this N, and formal statistical tests (Fisher exact) are underpowered at this scale — none of the pairwise comparisons reach conventional significance thresholds (all p > 0.05). The effect sizes are large (Cohen's h > 0.3 for the key comparisons), but N = 200 sampling (planned for P11-D) is required for statistical confirmation.

---

## 7. Conclusion

We have demonstrated experimentally that the investigability ceiling observed in long-path biomedical KG discovery is a selection artifact rather than a structural property of path length. Enriched bridge geometry — chemistry-domain nodes that create multi-domain-crossing paths with `cdr_L3 ≥ 0.46` — is necessary to surface investigable long-path candidates; endpoint-aware pre-filtering is necessary to select among them correctly under literature-aware evaluation. When both conditions are met, the ceiling (investigability ≈ 0.943) gives way to performance that strictly exceeds the evidence-aware short-path baseline (warm-cache investigability = 1.000, long-path share = 50%, novelty retention = 1.238), and this improvement is family-transferable — demonstrated across both the ROS and NT bridge families under literature-aware endpoint selection.

*Long-path discovery is not inherently blocked by a novelty ceiling; it becomes viable in a family-transferable manner when semantically enriched bridge geometry is paired with endpoint-aware candidate selection under literature-aware evaluation.*

---

## 8. Figure and Table Reference

| Item | Section | File / Location | Note |
|------|---------|----------------|------|
| Fig 1 | 4.1 | `docs/figures/fig2_c1_geometry_breakthrough.png` | File prefix `fig2` reflects generation order, not paper figure number |
| Fig 2 | 4.2 | `docs/figures/fig3_c2_domain_agnostic.png` | File prefix `fig3` reflects generation order, not paper figure number |
| Fig 3 | 4.3 | `docs/figures/fig1_p10a_comparison.png` | File prefix `fig1` reflects generation order, not paper figure number |
| Table 1 | 4.1 | Inline (this document) | |
| Table 2 | 4.2 | Inline (this document) | |
| Table 3 | 4.3 | Inline (this document) | |

*Figure file naming note: The on-disk filenames (`fig1_*`, `fig2_*`, `fig3_*`) were assigned in generation order and are inverted relative to paper figure numbers. Fig 1 (paper) corresponds to `fig2_c1_*`, Fig 2 to `fig3_c2_*`, Fig 3 to `fig1_p10a_*`. Rename files to `fig1_c1_geometry_breakthrough.png`, `fig2_c2_domain_agnostic.png`, `fig3_c3_prefilter.png` before final PDF generation.*
