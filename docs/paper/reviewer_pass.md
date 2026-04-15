# Skeptical Reviewer Pass — draft_v1.md
*Generated: 2026-04-15 | Reviewer: Claude (adversarial mode)*

---

## Overview

The manuscript argues that the "novelty ceiling" in long-path biomedical KG discovery is a
selection artifact rather than a structural property of path length. This is a coherent and
interesting claim, supported by a well-designed experiment series. However, several issues
require attention before submission: two factual errors, a potential circularity in the
primary evaluation, and several overclaims that a strong reviewer will attack. The issues
are enumerated below in order of severity.

---

## Issue A — HIGH | Circularity / Information Leakage

**Section**: 3.2 (T3+pf pre-filter), 6 (Limitations)

**Issue type**: Circularity / evaluation contamination

**Why a reviewer would care**: The pre-filter's primary signal (`recent_validation_density`,
weight 0.50) is derived from a pubmed_cache containing 2024–2025 PubMed counts for endpoint
pairs validated in prior runs. The investigability evaluation ALSO checks whether selected
endpoint pairs appear in 2024–2025 PubMed. These are not the same instances (the cache was
built in run_042, not during run_043 selection), but they draw from the **same data source
and date window**. The run_043 memo explicitly confirms: "All 20 NT endpoint pairs validated
in run_042 are `investigated=1`" — and any path whose endpoint pair is in that cache receives
a high `recent_validation_density` score, rises to the top of its bucket, and then trivially
passes the investigability check.

In effect, the pre-filter rank-orders candidates by how many 2024–2025 papers their endpoint
pair has, and investigability checks whether those endpoint pairs appear in 2024–2025 papers.
The 1.000 investigability result for T3+pf is therefore not a test of whether the *system*
surfaces investigable paths — it is a test of whether the *pre-filter correctly propagates
a signal that is nearly identical to the evaluation criterion*. A reviewer will characterize
this as "the pre-filter is optimising for the evaluation metric."

The paper's defence in Section 6 ("no target leakage in path ranking") is technically
accurate but insufficient: path-level leakage is absent, but the data-source overlap between
ranking signal and evaluation signal is the same fundamental concern.

**Severity**: HIGH

**Concrete revision suggestion**:
1. Add a dedicated paragraph in Section 3.2 (not only in Limitations) explaining the overlap
   and why it is not fully circular: the cache covers endpoint pairs generically, while
   the evaluation window is path-specific. Quantify what fraction of T3+pf selections had
   endpoint pairs in the run_042 cache vs. proxy-scored.
2. Reframe the 1.000 result: distinguish between (a) the pre-filter correctly selecting
   known-investigable paths (a positive finding) and (b) the pre-filter discovering
   previously-unknown investigable paths (a stronger, untested claim). The current draft
   implies (b) but only demonstrates (a).
3. In the limitations, elevate this from a brief remark to a named concern ("evaluation
   signal overlap") and state explicitly that cold-start results (P11-A) are required before
   the claim that T3+pf achieves 1.000 on an independent evaluation window can be made.

---

## Issue B — HIGH | Factual Error: "+5.7pp over P4 ceiling"

**Section**: 4.1, first paragraph

**Issue type**: Numerical error

**Why a reviewer would care**: The manuscript states: "T3 selection achieved investigability
of 0.986 — a +5.7 percentage-point gain over the P4 historical ceiling of 0.943." But
0.986 − 0.943 = **4.3pp**, not 5.7pp. The +5.7pp figure is correct for a different
comparison: T3 P7 (0.9857) vs T2 P6-A (0.9286), i.e., +5.71pp over the previous
*bucketed* weak-success result. The run_038 review memo confirms this: "T3_P7 vs P4 ceiling
= +0.0457 (+4.6pp)."

This mixes up two distinct reference points. The ceiling the paper defines throughout is
B2 = 0.943 (P4 historical ceiling); the 5.7pp figure compares against T2 = 0.929, which is
a different baseline. A reviewer fact-checking the arithmetic will flag this immediately.

**Severity**: HIGH

**Concrete revision suggestion**: Change "+5.7 percentage-point gain over the P4 historical
ceiling of 0.943" to "+4.6 percentage-point gain over the P4 historical ceiling of 0.943
(0.986 vs. 0.943)." If you also want to report the 5.7pp figure, add: "and +5.7pp over the
P6-A bucketed weak-success result (T2 = 0.929)," making the two comparisons explicit.

---

## Issue C — HIGH | Factual Error: "63.6% of the ROS family-transfer score"

**Section**: 5.3, second paragraph

**Issue type**: Numerical error

**Why a reviewer would care**: The manuscript states that "NT achieving only 63.6% of the
ROS family-transfer score." The H_P9_TRANSFER metric in run_041 is defined as
C_NT_ONLY T3 inv / C_P7_FULL T3 inv = 0.8571 / 0.9857 = **0.8695 (86.95%)**. There is
no derivation in the source data that produces 63.6%. This number does not match any
metric recorded in the run_041 review memo. A reviewer who reads the source data will find
a discrepancy of ~23 percentage points.

**Severity**: HIGH

**Concrete revision suggestion**: Replace "only 63.6% of the ROS family-transfer score"
with "only 86.95% of the ROS family-transfer threshold (family_transfer = 0.8695, vs.
pre-registered threshold ≥ 0.95)." If 63.6% derives from a different calculation, document
the formula explicitly and verify it against the source data.

---

## Issue D — HIGH | "Domain-Agnostic" Is Overclaimed

**Section**: Abstract, C2 claim, Section 4.2, Section 5.4, Conclusion

**Issue type**: Overclaim / generality

**Why a reviewer would care**: C2 claims the mechanism is "domain-agnostic." The evidence
is two chemistry families: ROS (oxidative stress metabolites) and NT (neurotransmitters).
Both are:
- Well-characterised biomedical chemistry families with decades of research
- Connected to mainstream 2024–2025 research targets (neurodegeneration, Alzheimer's,
  Parkinson's)
- Heavily covered in the evaluation window (NT endpoint pairs: 202–2189 PubMed papers)

The run_041 review memo (§7) explicitly concluded: "**The design principle is
geometry-agnostic but literature-frontier-specific.**" This is a more precise
characterisation than "domain-agnostic." After P10-A, the paper reinterprets P9's failure
as a "selection artifact," which is valid, but the revised conclusion — "domain-agnostic" —
requires the pre-filter to generalise to families that are NOT well-covered in the
evaluation-window PubMed cache. That has not been tested. Two families, both drawn from
mainstream biomedical chemistry, both with rich 2024–2025 PubMed coverage, do not establish
domain generality.

A reviewer will ask: does "domain-agnostic" hold for a frontier chemistry family with
sparse 2024–2025 coverage? The cold-start limitation in Section 6 acknowledges the pre-filter
needs a warm cache — which means it specifically CANNOT be domain-agnostic for families
without existing PubMed coverage.

**Severity**: HIGH

**Concrete revision suggestion**:
- In abstract and conclusion, replace "domain-agnostic" with "geometry-transferable across
  bridge families with established PubMed endpoint coverage" or equivalent.
- In Section 5.4, add explicit statement: "Domain-agnosticism in the present study is
  demonstrated for families with high 2024–2025 PubMed endpoint coverage; the behaviour
  for frontier families (sparse coverage) is untested and constitutes the cold-start case
  addressed in planned P11-A."
- In the C2 claim statement (Section 1, Introduction): add the qualifier "when endpoint-aware
  selection has access to a warm validation cache."

---

## Issue E — MEDIUM | Investigability Metric Conflates "Investigated" with "Novel"

**Section**: Introduction, 3.3, 5.1

**Issue type**: Metric concern / conceptual ambiguity

**Why a reviewer would care**: The paper opens with the goal of surfacing "non-obvious
hypotheses — connections between drugs and diseases that are not directly asserted in the
graph." But investigability is defined as: fraction of selected paths whose endpoint pairs
**appear in 2024–2025 PubMed**. Endpoint pairs with 202–2189 papers in the validation window
(as with NT connections) are not "non-obvious" — they are mainstream, heavily-studied
connections. Maximising investigability may select paths connecting well-known drug-disease
pairs through multi-hop intermediates, not genuinely novel hypotheses.

A reviewer will observe: (serotonin, Alzheimer's) with 202 papers is not a discovery system
output — it is textbook knowledge. The metric rewards selecting paths whose endpoints are
actively published, but this is orthogonal to whether the *paths themselves* are novel
hypotheses. The paper conflates the investigability of the endpoint pair (a proxy for
"worth investigating") with the novelty of the hypothesised path (the actual discovery claim).

**Severity**: MEDIUM

**Concrete revision suggestion**: Add a paragraph to Section 3.3 (Evaluation Metrics)
explicitly distinguishing investigability (endpoint-pair coverage in 2024–2025 PubMed)
from path-level novelty (whether the intermediate-mediated connection is previously
documented). Acknowledge that investigability is a necessary but not sufficient condition
for novelty. Either add a path-level novelty check as a secondary metric, or explicitly
scope the claim to "investigability-maximisation" rather than "discovery."

---

## Issue F — MEDIUM | Investigability Binary Threshold Not Specified

**Section**: 3.3 (Evaluation Metrics)

**Issue type**: Ambiguity / reproducibility

**Why a reviewer would care**: Investigability is described as "a binary label, validated
using a held-out query window." But the threshold for "appearing as active research targets
in 2024–2025 PubMed literature" is never specified. Is it 1 paper? 5 papers? 10 papers?
The run_043 memo shows endpoint pairs ranging from 7 papers (glutamate, Huntington's) to
2189 papers (dopamine, Parkinson's) — both labelled `investigated=1`. Without the threshold,
the metric definition is incomplete, and the 100% investigability result cannot be verified.

**Severity**: MEDIUM

**Concrete revision suggestion**: In Section 3.3, specify the binary threshold: "endpoint
pair is classified as `investigated=1` if it appears in ≥ N papers in the 2024–2025 PubMed
query window." Provide the value of N and justify it. This is also needed for reproducibility.

---

## Issue G — MEDIUM | Figure Filename / Number Mismatch

**Section**: Section 7 (Figure and Table Reference)

**Issue type**: Factual inconsistency / reproducibility

**Why a reviewer would care**: The Figure and Table Reference table maps:
- Fig 1 → `docs/figures/fig2_c1_geometry_breakthrough.png`
- Fig 2 → `docs/figures/fig3_c2_domain_agnostic.png`
- Fig 3 → `docs/figures/fig1_p10a_comparison.png`

The file named `fig1_*` corresponds to the paper's Fig 3; `fig2_*` to Fig 1; `fig3_*` to
Fig 2. Any reader following the file path reference will find the wrong figure. This creates
confusion for both reviewers inspecting the files and anyone attempting to reproduce the
figures. The figures themselves may be correct; only the filename-to-paper-number mapping
is inconsistent.

**Severity**: MEDIUM

**Concrete revision suggestion**: Either rename the figure files to match paper numbering
(`fig1_c1_geometry_breakthrough.png`, `fig2_c2_domain_agnostic.png`,
`fig3_c3_prefilter.png`) and update all references accordingly, OR note in the reference
table which file corresponds to which figure caption to prevent confusion.

---

## Issue H — MEDIUM | Statistical Significance vs. Causal Claims

**Section**: 3.3, 6 (Limitations), throughout

**Issue type**: Overclaim / statistical concern

**Why a reviewer would care**: The manuscript makes strong causal statements throughout:
"the ceiling is not structural but is instead an artifact," "the mechanism generalizes,"
"endpoint-aware pre-filtering is a necessary selection layer component." Yet Section 6
explicitly states that "none of the pairwise comparisons reach conventional significance
thresholds (all p > 0.05)" with N=70. This creates a gap: the language of strong causal
determination appears in the abstract and introduction, while the statistical basis for
those claims is described as underpowered in Limitations.

Additionally, the claim that the 70/70 vs. 66/70 comparison (T3+pf investigability 1.000
vs. baseline ceiling 0.943) has p > 0.05 is worth verifying explicitly — with a one-sided
Fisher exact test this comparison may in fact reach significance, and if so, the "all
p > 0.05" statement is wrong.

**Severity**: MEDIUM

**Concrete revision suggestion**: Report the actual p-values for each key pairwise
comparison in Table 1 or in a supplementary statistical table, including the test type
(one-sided vs. two-sided Fisher exact) and justification. Modulate the causal language in
the abstract and introduction to match the statistical evidence: replace "eliminates the
ceiling" with "consistently reduces" or "reverses" until N=200 results (P11-D) confirm
significance. The conclusion can still be affirmative but should be calibrated.

---

## Issue I — MEDIUM | Cold-Start Limitation Understated Given Evaluation Architecture

**Section**: 6 (Limitations)

**Issue type**: Missing evidence / scope concern

**Why a reviewer would care**: The pre-filter's 50% primary weight on `recent_validation_density`
means the entire T3+pf result depends on the pubmed_cache quality. The run_043 memo
confirms: "The pre-filter's effectiveness here relies on the pubmed_cache from run_042
containing 2024–2025 PubMed counts for all key NT endpoint pairs." Without that cache
(cold-start), performance falls back to a 0.6× proxy discount. Whether cold-start
performance maintains STRONG_SUCCESS is explicitly untested.

Given that Issue A (circularity) means the warm-cache result may overestimate real-world
performance, the cold-start case is not just a limitation — it is the relevant measure for
any genuine assessment of the method's value. The current limitations section lists it as
one of four items with equal weight. A reviewer will notice this understatement.

**Severity**: MEDIUM

**Concrete revision suggestion**: Elevate the cold-start limitation to the first item
in Section 6 and reframe it as: "The reported T3+pf investigability of 1.000 is a
**warm-cache result**. The pre-filter's primary signal requires prior-run endpoint-pair
validation data from the same evaluation window. Cold-start performance (no prior cache)
is untested. Whether the method achieves STRONG_SUCCESS without a warm cache is the
critical open question addressed by planned P11-A." Do not present warm-cache investigability
as the primary performance number without qualification.

---

## Issue J — MEDIUM | Adaptive Study Design Not Acknowledged

**Section**: 3.4, Discussion

**Issue type**: Transparency / study design concern

**Why a reviewer would care**: P10-A was designed specifically to address P9's failure —
the run_041 memo explicitly says P10-A "could retroactively demonstrate that NT family CAN
achieve STRONG_SUCCESS with the right selection strategy — changing the conclusion from
GEOMETRY_ONLY to DOMAIN_AGNOSTIC." The pre-filter's design (use endpoint-level 2024–2025
signal as primary discriminator) is a direct response to the observed B2–T3 gap. This is
valid adaptive experimental design but creates a circularity in the argument: P9 revealed
the failure mode → P10-A was designed to fix exactly that failure mode → P10-A fixes it →
conclusion is that P9's failure was an artifact. A reviewer who reads the P9 memo will
observe this chain.

The paper does not acknowledge that the DOMAIN_AGNOSTIC conclusion was the *pre-specified
goal* of P10-A, not a serendipitous discovery.

**Severity**: MEDIUM

**Concrete revision suggestion**: Add a sentence in Section 3.4 or 5.3: "The endpoint-aware
pre-filter (P10-A) was designed specifically in response to the B2–T3 gap observed in P9,
making the retroactive DOMAIN_AGNOSTIC verdict interpretable as confirmation of the
hypothesised selection mechanism rather than an independent replication. Independent
confirmation from a new bridge family (P11-C or beyond) would strengthen the domain-agnostic
claim."

---

## Issue K — LOW | "Novelty Ceiling" Terminology Ambiguous

**Section**: Title, Abstract, throughout

**Issue type**: Ambiguity / terminology

**Why a reviewer would care**: The paper uses "novelty ceiling" to mean "investigability
ceiling" (the 0.943 upper bound on the fraction of paths that are investigated). But the
paper also uses "novelty" in a different sense: "novelty retention" (the cross-domain ratio
preservation metric). The title and abstract use "novelty" to mean the former; Section 2
and the four-condition table reference the latter. A reader focusing on the title expects
the paper to be about generating *novel* (previously unknown) drug-disease hypotheses, but
the metric being maximised is investigability (whether the endpoint pair is in 2024–2025
PubMed), which rewards well-studied connections.

**Severity**: LOW

**Concrete revision suggestion**: Either (a) rename the ceiling "investigability ceiling"
throughout to align with the metric's definition, reserving "novelty" for cross-domain
ratio retention, or (b) explicitly define "novelty ceiling" in the introduction as "the
empirical ceiling on investigability" and explain why this is a proxy for novelty.

---

## Issue L — LOW | Table 1 Missing P7 Full-Expansion Row

**Section**: 4.1, Table 1

**Issue type**: Missing evidence / presentation gap

**Why a reviewer would care**: Table 1 ("ROS bridge family ablation") shows six conditions
from P8 but omits the P7 full KG expansion (10 nodes, cdr_L3=0.619, inv=0.9857), which is
the primary evidence for C1's geometry breakthrough claim. The table jumps from "Original KG
(no bridges) | 0 | 0.333 | 0.943" directly to "ROS core only | 2 | 0.464 | 0.986." A reader
trying to follow the C1 argument from Table 1 will not see the P7 breakthrough condition.

**Severity**: LOW

**Concrete revision suggestion**: Add a row for "P7 full expansion (metabolite bridge) | 10 | 0.619 | 0.986 | STRONG_SUCCESS" between the "Original KG" row and the "ROS core only" row.
This makes the C1 claim trajectory visible in the table itself.

---

## Issue M — LOW | C_P7_FULL / C_ROS_ALL Labelling Confusion in Table 1

**Section**: 4.1, Table 1

**Issue type**: Ambiguity

**Why a reviewer would care**: Table 1's row "Full ROS family | 7 | 0.740" corresponds to
P8's C_ROS_ALL (7 of the combined nodes), not to C_P7_FULL (10 nodes, which was the P7
full expansion). A reader who identifies "Full ROS family" with "the full P7 KG expansion"
will read cdr_L3=0.740 (P8) as the P7 breakthrough value, when the P7 breakthrough actually
achieved cdr_L3=0.619. This could overstate what the P7 intervention alone achieved.

**Severity**: LOW

**Concrete revision suggestion**: Rename the "Full ROS family | 7" row to "ROS-only family
(no metabolite core) | 7 | 0.740" or add a footnote: "C_ROS_ALL (P8) excludes the 3
non-ROS metabolites from P7's 10-node expansion; the P7 breakthrough used 10 nodes and
achieved cdr_L3=0.619."

---

## Summary: Issues by Severity

| ID | Severity | Location | Issue |
|----|----------|----------|-------|
| A | HIGH | §3.2, §6 | Pre-filter uses same data source as evaluation metric (near-circular) |
| B | HIGH | §4.1 | +5.7pp vs P4 ceiling is wrong; correct is +4.6pp |
| C | HIGH | §5.3 | 63.6% family-transfer figure not derivable from source data; actual is 86.95% |
| D | HIGH | Abstract, §4.2, §5.4 | "Domain-agnostic" overclaimed; only 2 well-studied families tested |
| E | MEDIUM | §1, §3.3, §5.1 | Investigability ≠ novelty; metric rewards well-studied connections |
| F | MEDIUM | §3.3 | Investigability binary threshold never specified |
| G | MEDIUM | §7 | Figure filenames mismatched to paper figure numbers |
| H | MEDIUM | §3.3, §6 | Statistical significance not reached; causal language too strong |
| I | MEDIUM | §6 | Cold-start limitation understated given evaluation architecture |
| J | MEDIUM | §3.4, §5.3 | Adaptive design (P10-A designed to fix P9) not disclosed |
| K | LOW | Title, throughout | "Novelty ceiling" ambiguously overloads "novelty" terminology |
| L | LOW | §4.1 Table 1 | P7 full-expansion row missing from Table 1 |
| M | LOW | §4.1 Table 1 | "Full ROS family" label implies P7 full expansion but shows P8 subset |
