# MVP Results v2 — Scientific Hypothesis Generation (Phase 3 Re-test)

**Date**: 2026-04-14
**Status**: NO-GO

## Background

Phase 2 returned NO-GO due to C_rand v1 baseline bias.
C_rand v2 redesign excludes trivially-known pairs; N increased to 50 per method.
Primary endpoint changed to novel_supported_rate (SC-1r).

## Methods

| Step | v1 | v2 |
|------|----|----|
| N per method | 20 | 50 |
| C_rand design | KG path traversal | Random entity-pool sampling |
| Known-pair exclusion | None | KG 1-hop + trivially-known blacklist |
| Primary endpoint | precision_positive | novel_supported_rate |
| Labeling | Layer 1 only | Layer 1 + Layer 2 (novelty) |

## Results

| Method | N | Investigated | Precision(L1) | Novel_Sup | Known_Fact | Novel_Sup_Rate |
|--------|---|-------------|---------------|-----------|------------|----------------|
| C2 (multi-op) | 50 | 46 | 0.891 | 6 | 37 | 0.130 |
| C1 (single-op) | 50 | 49 | 0.980 | 4 | 46 | 0.082 |
| C_rand_v2 | 50 | 32 | 0.844 | 7 | 21 | 0.219 |

## Success Criteria

| SC | Description | C2 | C_rand_v2 | p-value | Result |
|----|-------------|----|-----------|---------|----|
| SC-1r (primary) | novel_supported_rate | 0.130 | 0.219 | 0.9088 | FAIL |
| SC-2r | plausible_novelty_rate | 0.260 | 0.580 | 0.9997 | FAIL |
| SC-3r | investigability | 0.920 | 0.640 | 0.0007 | PASS |
| SC-4r (exploratory) | known_fact_rate C2 < C_rand | 0.740 | 0.420 | 0.9997 | FAIL |

## Go / No-Go

**NO-GO**

NO-GO | SC-1r(primary)=FAIL | SC-2r=FAIL | SC-3r=PASS | SC-4r=FAIL
