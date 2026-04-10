# Run 013 Decision Memo

**Date**: 20260410
**Verdict**: SUCCESS

## Summary

3/3 subsets passed all three reproducibility criteria.

## Per-Subset Observations

### Subset A: PASS

- Deep CD candidates: baseline=20, filtered=3
- Label distribution: promising=3, weak_spec=0, drift_heavy=0
- Alignment-dependent reachability: unique_to_multi=5

Top deep CD candidates (filtered, promising):
  - [promising] bio:VHL → ... → chem_run013::chem:r_Oxidation (depth=4, strong_ratio=0.5)
  - [promising] bio:g_HIF1A → ... → chem_run013::chem:r_Oxidation (depth=4, strong_ratio=0.5)
  - [promising] bio:g_VHL → ... → chem_run013::chem:r_Oxidation (depth=5, strong_ratio=0.6)

### Subset B: PASS

- Deep CD candidates: baseline=45, filtered=39
- Label distribution: promising=39, weak_spec=0, drift_heavy=0
- Alignment-dependent reachability: unique_to_multi=40

Top deep CD candidates (filtered, promising):
  - [promising] imm:PTGS1 → ... → chem_run013::nat:fg_Catechol_nat (depth=3, strong_ratio=0.6667)
  - [promising] imm:PTGS1 → ... → chem_run013::nat:fg_Lactone (depth=3, strong_ratio=0.6667)
  - [promising] imm:PTGS1 → ... → chem_run013::nat:fg_Phenolic (depth=4, strong_ratio=0.5)

### Subset C: PASS

- Deep CD candidates: baseline=86, filtered=33
- Label distribution: promising=33, weak_spec=0, drift_heavy=0
- Alignment-dependent reachability: unique_to_multi=55

Top deep CD candidates (filtered, promising):
  - [promising] neu:TH → ... → chem_run013::phar:fg_Piperidine (depth=3, strong_ratio=0.6667)
  - [promising] neu:TH → ... → chem_run013::phar:r_Deamination (depth=4, strong_ratio=0.5)
  - [promising] neu:DDC → ... → chem_run013::phar:fg_Piperidine (depth=3, strong_ratio=0.6667)

## Next Steps

Run 013 PASSED. The pipeline shows robustness across different domain pairs.

Recommended next actions:
1. Quantitative analysis of which structural properties drive reproducibility
2. H1''/H3'' re-verification with filter-cleaned candidates
3. Investigation of why certain subsets produce fewer promising candidates
