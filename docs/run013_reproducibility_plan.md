# Run 013 — Reproducibility Plan

**Date**: 2026-04-10  
**Purpose**: Cross-subset reproducibility / robustness test for Run 012 pipeline  
**Status**: Planned → Executing

---

## Objective

Determine whether the Run 012 pipeline findings (drift-filtered deep cross-domain discovery)
are reproducible across different bio-chem domain pairs, or are artifacts of Subset A's
specific entity structure.

**Question**: When the same pipeline is applied to different bio/chem subsets (without
retuning), does it produce the same structural phenomena?

---

## Subsets

| Subset | Bio domain | Chem domain | Bridge type |
|--------|-----------|-------------|-------------|
| A (reference) | Cancer signaling (bio:) | Metabolic chemistry (chem:) | Metabolite identity (NAD, ATP, ...) |
| B (new) | Immunology (imm:) | Natural products (nat:) | Eicosanoid identity + compound→enzyme |
| C (new) | Neuroscience (neu:) | Neuro-pharmacology (phar:) | Neurotransmitter identity + drug→receptor |

### Subset B: Immunology + Natural Products
- **Bio focus**: TLR signaling, NLRP3 inflammasome, JAK-STAT, eicosanoid synthesis, T/B cell activation
- **Chem focus**: Flavonoids (Kaempferol, Luteolin), terpenoids (Artemisinin, Tanshinone), alkaloids (Berberine), isothiocyanates (Sulforaphane)
- **Bridge metabolites**: Arachidonic acid (imm:m_AA ↔ nat:ArachidonicAcid), PGE2, LTB4
- **Expected cross-domain paths**: g_ALOX5→encodes→ALOX5→catalyzes→m_AA→[bridge]→ArachidonicAcid→undergoes→r_OxidationNat

### Subset C: Neuroscience + Neuro-pharmacology
- **Bio focus**: Dopamine/serotonin synthesis, receptors, synaptic proteins, BDNF signaling, neurodegeneration
- **Chem focus**: SSRIs, antipsychotics, anticonvulsants, anti-Parkinson drugs, neurotransmitter chemistry
- **Bridge metabolites**: Dopamine (neu:m_Dopamine ↔ phar:Dopamine), Serotonin, GABA, Norepinephrine
- **Expected cross-domain paths**: g_TH→encodes→TH→produces→m_Dopamine→[bridge]→Dopamine→undergoes→r_Hydroxylation→produces→fg_Catechol

---

## Pipeline Spec (identical to Run 012)

```python
filter_relations = {"contains", "is_product_of", "is_reverse_of", "is_isomer_of"}
guard_consecutive_repeat = True
min_strong_ratio = 0.40   # depth≥3 requires ≥40% strong relations
filter_generic_intermediates = True
max_depth = 9             # up to 5-hop
max_per_source = 50
```

**Critical constraint**: No per-subset retuning. If results differ, it's because the
domains differ — not because we cherry-picked parameters.

---

## Metrics Collected per Subset

1. **Candidate counts**: baseline (no filter) and filtered
2. **Deep cross-domain**: candidates with ≥3-hop cross-domain path (baseline and filtered)
3. **Label distribution**: promising / weak_speculative / drift_heavy among filtered deep CD
4. **Alignment-dependent reachability**: unique_to_multi count (candidates only reachable via alignment)
5. **Drift rate by depth bucket**: mean drift rate for shallow/medium/deep
6. **Top-20 composition**: depth distribution, cross-domain count, mean score

---

## Success / Failure Criteria

**SUCCESS**: ≥2 out of 3 subsets reproduce all three phenomena:
1. `unique_to_multi > 0` (alignment creates genuinely new reachable pairs)
2. Filtered deep CD count ≥ 1 (pipeline generates deep cross-domain candidates)
3. Promising label count ≥ 1 after filter (at least 1 high-quality deep CD survives)

**FAILURE**: Only Subset A passes all criteria → Run 012 findings are Subset A-specific.

---

## Implementation

- `src/data/wikidata_phase4_subset_b.py` — Subset B curated data
- `src/data/wikidata_phase4_subset_c.py` — Subset C curated data
- `src/pipeline/run_013.py` — Pipeline runner (3 subsets)
- `tests/test_run_013.py` — 59 tests

---

## Expected Outcomes

Given the structural design:
- **Subset A**: Known to produce 3 promising deep CD (VHL/HIF1A/LDHA cascade)
- **Subset B**: Arachidonic acid bridge should enable gene→enzyme→metabolite→chem-reaction chains
- **Subset C**: Neurotransmitter bridges should enable TH→Dopamine→drug-reaction chains

Hypothesis: All 3 subsets will show alignment-dependent reachability and deep CD candidates,
but Subset B/C may show different numbers due to different graph density and relation structure.
