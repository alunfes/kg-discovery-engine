# Revision Targets — Ranked by Severity
*Companion to `reviewer_pass.md` | 2026-04-15*

Ordered HIGH → MEDIUM → LOW within each tier. Fix HIGH items before submission.
Item IDs reference the corresponding issue in `reviewer_pass.md`.

---

## HIGH — Must Fix Before Submission

### R1 · §4.1 · Numerical error: "+5.7pp over P4 historical ceiling"
- **Issue ID**: B
- **Sections affected**: §4.1 (first paragraph of 4.1)
- **Issue summary**: 0.986 − 0.943 = 4.3pp (or 4.6pp per source data), not 5.7pp; 5.7pp is vs T2 weak-success baseline (0.929), not the P4 ceiling
- **Severity**: HIGH
- **Suggested fix**: Change to "+4.6 percentage-point gain over the P4 historical ceiling of 0.943 (0.986 vs. 0.943)." If the T2 comparison is also desired, add it as a separate parenthetical: "(+5.7pp vs. the P6-A bucketed weak-success baseline of 0.929)."
- **Dependencies**: None — isolated textual correction

---

### R2 · §5.3 · Numerical error: "63.6% of the ROS family-transfer score"
- **Issue ID**: C
- **Sections affected**: §5.3 (second paragraph)
- **Issue summary**: The H_P9_TRANSFER metric (run_041) was 0.8695 (C_NT_ONLY / C_P7_FULL = 0.8571/0.9857 = 86.95%). The 63.6% figure does not correspond to any metric in the source data.
- **Severity**: HIGH
- **Suggested fix**: Replace "NT achieving only 63.6% of the ROS family-transfer score" with "NT achieving a family-transfer score of 0.8695 — below the pre-registered threshold of 0.95." Verify the intended formula and confirm the number against `runs/run_041_p9_nt_family/domain_agnostic_analysis.json`.
- **Dependencies**: None

---

### R3 · Abstract, §4.2, §5.4, Conclusion · "Domain-agnostic" overclaim
- **Issue ID**: D
- **Sections affected**: Abstract (final sentence), Introduction C2 claim, §4.2 heading and body, §5.4, Conclusion
- **Issue summary**: Only two bridge families tested, both well-studied chemistry families with rich 2024–2025 PubMed coverage; the run_041 memo itself concluded "literature-frontier-specific"; the pre-filter requires a warm validation cache to achieve domain-agnostic investigability
- **Severity**: HIGH
- **Suggested fix**: Qualify "domain-agnostic" in every occurrence: add "for bridge families with established 2024–2025 PubMed endpoint coverage." In §5.4 (scope), add: "Domain-agnosticism is demonstrated for two well-characterised chemistry families; extension to frontier families with sparse coverage requires P11-A cold-start validation." Adjust the one-sentence summary accordingly.
- **Dependencies**: R4 (circularity fix should be resolved first, as it changes the framing of what the 1.000 result means)

---

### R4 · §3.2, §6 · Pre-filter circularity: same data source used for ranking and evaluation
- **Issue ID**: A
- **Sections affected**: §3.2 (T3+pf description), §6 Limitations
- **Issue summary**: `recent_validation_density` (weight 0.50) uses 2024–2025 PubMed counts from prior-run cache; investigability evaluation also uses 2024–2025 PubMed; the T3+pf result of 1.000 is partly a confirmation that the pre-filter correctly propagates a near-identical signal to the evaluation criterion
- **Severity**: HIGH
- **Suggested fix**:
  1. Add to §3.2: quantify what share of T3+pf selections had endpoint pairs with cache hits vs. proxy scores. State that the 1.000 result applies to the warm-cache regime.
  2. In §6, elevate to a prominent named limitation: "Evaluation signal overlap — the pre-filter's primary signal and the investigability criterion share the same data source (2024–2025 PubMed). Warm-cache investigability of 1.000 measures the pre-filter's ability to surface paths whose endpoint pairs are already known to be active research targets; it does not measure discovery of previously-unknown investigable paths. Cold-start performance (P11-A) provides the independent test."
  3. Soften the 1.000 result in the abstract/conclusion to "warm-cache investigability of 1.000" or add an asterisk-style qualifier.
- **Dependencies**: Must be resolved before R3 (the domain-agnostic framing depends on how strongly the 1.000 result is claimed)

---

## MEDIUM — Should Fix Before Submission

### R5 · §3.3, §1 · Investigability metric conflates "investigated" with "novel"
- **Issue ID**: E
- **Sections affected**: §1 (Introduction, motivation framing), §3.3 (metric definition), §5.1
- **Issue summary**: The paper claims to surface "non-obvious hypotheses" but the investigability metric rewards endpoint pairs actively published in 2024–2025, which includes well-known connections (dopamine/Parkinson's with 2189 papers). High investigability does not imply novel discovery.
- **Severity**: MEDIUM
- **Suggested fix**: Add a sentence to §3.3 separating the two concepts: "Investigability is a proxy for near-term research relevance, not for prior-knowledge novelty. An endpoint pair may be investigable because it is an established connection (high prior literature) or because it is an emerging connection (low prior, high recent literature). The present evaluation does not distinguish these cases." Consider adding a "prior-knowledge score" secondary metric, or at minimum scope the claim: "investigability-maximising discovery" rather than "novel hypothesis discovery."
- **Dependencies**: None — can be done independently; may also partially address R3 framing

---

### R6 · §3.3 · Investigability binary threshold not defined
- **Issue ID**: F
- **Sections affected**: §3.3 (third paragraph, Evaluation Metrics)
- **Issue summary**: The paper never states what PubMed count threshold converts a continuous endpoint-pair literature count into the binary `investigated=1` label. Values in source data range from 7 to 2189 papers, both `investigated=1`.
- **Severity**: MEDIUM
- **Suggested fix**: Add: "An endpoint pair is labelled `investigated=1` if ≥ N papers appear in the 2024–2025 PubMed query window for the joint term (source_entity, target_entity); N=X [specify value from validation code]." Verify the threshold against `runs/run_043_p10a_prefilter/preregistration.md` or the scoring function in `src/scientific_hypothesis/run_043_p10a_prefilter.py`.
- **Dependencies**: None

---

### R7 · §7 Figure Reference Table · Figure filename / number mismatch
- **Issue ID**: G
- **Sections affected**: §7 (Figure and Table Reference table); figure captions in §4.1–4.3
- **Issue summary**: In the reference table, Fig 1 maps to `fig2_*`, Fig 2 to `fig3_*`, Fig 3 to `fig1_*` — file names and paper figure numbers are in inverted order
- **Severity**: MEDIUM
- **Suggested fix**: Rename figure files to match paper order:
  - `fig1_c1_geometry_breakthrough.png` (currently `fig2_*`)
  - `fig2_c2_domain_agnostic.png` (currently `fig3_*`)
  - `fig3_c3_prefilter_comparison.png` (currently `fig1_*`)
  Update all in-text references and the reference table. Confirm with the figures commit that `fig1_p10a_comparison.png` content is indeed the C3 figure.
- **Dependencies**: None — purely mechanical rename; do before finalising PDF

---

### R8 · §6 · Statistical significance: verify "all p > 0.05" claim and recalibrate causal language
- **Issue ID**: H
- **Sections affected**: §6 Limitations, Abstract, Introduction (causal language throughout)
- **Issue summary**: "None of the pairwise comparisons reach conventional significance thresholds (all p > 0.05)" — for the most extreme comparison (70/70 vs 66/70, T3+pf vs ceiling), a one-sided Fisher exact test may in fact reach p < 0.05; if so, the claim is wrong. Even if correct (two-tailed), causal language in the abstract ("ceiling is not structural," "mechanism generalizes") is unsupported at N=70.
- **Severity**: MEDIUM
- **Suggested fix**:
  1. Report actual p-values for all key comparisons in a supplementary statistical table (or in Table 1 as a column), specifying test type and directionality.
  2. If any comparison reaches p < 0.05 one-sided, correct the "all p > 0.05" statement.
  3. In the abstract and conclusion, replace absolute causal language with appropriately calibrated language: "strongly suggests the ceiling is an artifact" rather than "the ceiling is an artifact." Reserve definitive language for post-P11-D (N=200) results.
- **Dependencies**: None, but should be done before submission

---

### R9 · §6 · Cold-start limitation understated
- **Issue ID**: I
- **Sections affected**: §6 Limitations (first and second bullets)
- **Issue summary**: The cold-start case is the primary test of the method's real-world applicability given the evaluation signal overlap (R4); currently listed as a minor limitation alongside three others of equal weight
- **Severity**: MEDIUM
- **Suggested fix**: Reorder §6 to lead with cold-start, and expand it: "The T3+pf investigability of 1.000 is a warm-cache result. In cold-start mode (no prior validation cache), the pre-filter's primary signal is unavailable and performance falls back to a proxy-scored mode (0.6× weight discount). Whether STRONG_SUCCESS is maintained in cold-start is the single most important open empirical question. Until P11-A results are available, the warm-cache result should be interpreted as an upper bound."
- **Dependencies**: R4 (best addressed together)

---

### R10 · §3.4, §5.3 · Acknowledge adaptive study design
- **Issue ID**: J
- **Sections affected**: §3.4 Experiment Design table (Phase roles), §5.3 Discussion
- **Issue summary**: P10-A was explicitly designed to change the P9 GEOMETRY_ONLY verdict to DOMAIN_AGNOSTIC; this is not disclosed in the paper. A reviewer reading the run_041 memo will notice the pre-registered goal of P10-A was to "retroactively demonstrate" DOMAIN_AGNOSTIC.
- **Severity**: MEDIUM
- **Suggested fix**: Add to §3.4: "The pre-filter design (P10-A) was motivated by the B2–T3 investigability gap observed in P9 (−0.114). P10-A constitutes a theory-driven response experiment, not an independent replication. Independent confirmation with a third bridge family (P11-C) would provide stronger domain-agnostic evidence." This is transparent without being self-undermining — adaptive design is legitimate; it just needs disclosure.
- **Dependencies**: None; recommended to address alongside R3

---

## LOW — Improve If Time Permits

### R11 · Title/throughout · "Novelty ceiling" terminology
- **Issue ID**: K
- **Sections affected**: Title, Abstract, Introduction, Section headers
- **Issue summary**: "Novelty" is overloaded: "novelty ceiling" refers to the investigability upper bound, while "novelty retention" is a separate metric about cross-domain ratio. The title implies the paper is about generating novel (previously unknown) connections, but the ceiling/metric is about investigability.
- **Severity**: LOW
- **Suggested fix**: Consider renaming to "Investigability Ceiling" throughout, reserving "novelty" exclusively for the novelty retention metric. If "novelty ceiling" is retained in the title for rhetorical reasons, define it explicitly in the abstract's first paragraph.
- **Dependencies**: None

---

### R12 · §4.1 Table 1 · Add P7 full-expansion row
- **Issue ID**: L
- **Sections affected**: §4.1, Table 1
- **Issue summary**: The C1 breakthrough experiment (P7, 10 nodes, cdr_L3=0.619, inv=0.986) is the primary evidence for C1 but is absent from Table 1, which only shows P8 ablation conditions
- **Severity**: LOW
- **Suggested fix**: Add a row "P7 metabolite expansion | 10 | 0.619 | 0.986 | STRONG_SUCCESS (breakthrough)" between the "Original KG" row and "ROS core only." This makes the C1 claim visible within the table.
- **Dependencies**: None

---

### R13 · §4.1 Table 1 · "Full ROS family | 7" label implies P7 full expansion
- **Issue ID**: M
- **Sections affected**: §4.1, Table 1 caption and row label
- **Issue summary**: "Full ROS family | 7 | 0.740" refers to P8's C_ROS_ALL (7 ROS-specific nodes), not to the P7 10-node full expansion (cdr_L3=0.619). Mislabelling could mislead readers about the cdr_L3 value at which the P7 breakthrough occurred.
- **Severity**: LOW
- **Suggested fix**: Rename row to "Full ROS-family subset (P8 C_ROS_ALL) | 7 | 0.740" and add footnote: "Excludes the 3 non-ROS metabolites from P7's 10-node expansion. The P7 breakthrough used 10 nodes (cdr_L3=0.619)."
- **Dependencies**: R12 (if P7 row is added, this label ambiguity becomes less likely to mislead)

---

## Dependency Graph

```
R4 (circularity)
  └─ must precede ─→ R3 (domain-agnostic framing)
  └─ should align with ─→ R9 (cold-start prominence)

R3 (domain-agnostic)
  └─ should align with ─→ R10 (adaptive design disclosure)

R1 (5.7pp error) — independent
R2 (63.6% error) — independent
R5 (investigability≠novelty) — independent; benefits R3 framing
R6 (threshold) — independent
R7 (figure filenames) — independent; do last before PDF generation
R8 (statistics) — independent; verify p-values first before editing text
R12 ─→ R13 (add P7 row first, then fix "full ROS" label)
```

---

## Revision Priority Order

1. **R1** — single sentence fix, high-visibility factual error
2. **R2** — single sentence fix, high-visibility factual error
3. **R4** — adds a paragraph to §3.2 and rewrites §6 lead bullet; foundational for framing
4. **R3** — qualifier additions to 5–6 locations; depends on R4
5. **R8** — run Fisher exact tests, report p-values, recalibrate language
6. **R6** — specify the investigability threshold (look up from code)
7. **R9** — reorder and expand §6; best done together with R4
8. **R10** — one sentence addition to §3.4 and §5.3
9. **R5** — one paragraph addition to §3.3
10. **R7** — rename figure files; do immediately before generating final PDF
11. **R11** — terminology; lower priority, higher effort
12. **R12 + R13** — table additions
