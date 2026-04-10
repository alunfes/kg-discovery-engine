# Evaluation Summary — Run 009 Phase 4

## Pipeline Candidate Counts

| Cond | P1(single/2) | P2(multi/2) | P3(multi/3) | P4(multi/4-5) | Aligned | UniqueViaAlign | DeepCross |
|------|-------------|------------|------------|--------------|---------|----------------|-----------|
| A | 251 | 251 | 451 | 706 | 293 | 0 | 0 |
| B | 161 | 161 | 200 | 208 | 243 | 0 | 0 |
| C | 454 | 419 | 665 | 939 | 7 | 168 | 20 |
| D | 542 | 419 | 665 | 939 | 7 | 168 | 20 |

## Hypothesis Verdicts

| Condition | H1'' | H3'' | H4 |
|-----------|------|------|-----|
| A | FAIL — 0 unique pairs from alignment | FAIL — 0 deep cross-domain candidates (s | FAIL |
| B | FAIL — 0 unique pairs from alignment | FAIL — 0 deep cross-domain candidates (s | INCONCLUSIVE |
| C | PASS — 168 unique pairs via alignment | PASS — 20 deep cross-domain candidates f | FAIL |
| D | PASS — 168 unique pairs via alignment | PASS — 20 deep cross-domain candidates f | FAIL |

## Key Finding
H3'' testable: YES — deep cross-domain candidates found in at least one condition
