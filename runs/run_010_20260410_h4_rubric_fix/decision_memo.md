# Decision Memo — Run 010 H4 Rubric Revision

## What Changed
- Old traceability: `1.0 / hop_count` → longer paths always score lower
- Revised traceability: quality-based penalty (low-spec relations, repeated
  consecutive relations, generic intermediate nodes) → length-neutral

## Key Results
- Old provenance-aware H4 verdict: **FAIL**
- Revised provenance-aware H4 verdict: **PASS**
- Deep candidates promoted by revised vs naive: 309
- Deep candidates demoted by revised vs naive: 209
- Deep cross-domain promoted by revised vs naive: 14
- New deep entries in top-20: 8

## Verdict
PASS — revised traceability promotes more deep candidates than it demotes.

## Interpretation
The revised rubric successfully re-ranks deep candidates by chain quality rather than length, enabling high-quality deep paths to rise above shallow-but-generic ones.

## Next Step
Adopt revised_traceability=True as default for H4 evaluation going forward.
