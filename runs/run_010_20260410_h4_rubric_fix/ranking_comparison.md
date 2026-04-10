# Ranking Comparison — Run 010 (3-way: naive / old aware / revised aware)

## Overview (top-20)

| Metric | Value |
|--------|-------|
| Total candidates | 939 |
| Deep candidates (≥3-hop) | 520 |
| Cross-domain candidates | 42 |
| Deep cross-domain | 20 |

## Jaccard Similarity (top-k overlap)

| Pair | Jaccard |
|------|---------|
| naive vs old_aware | 1.0 |
| naive vs revised | 0.4286 |
| old_aware vs revised | 0.4286 |

## Deep Candidate Movement (revised vs naive)

| Movement | Count |
|----------|-------|
| Deep promoted | 309 |
| Deep demoted | 209 |
| Deep unchanged | 2 |

## Deep Cross-Domain Movement (revised vs naive)

| Movement | Count |
|----------|-------|
| Promoted | 14 |
| Demoted | 6 |
| Unchanged | 0 |

## New entries in revised top-20: 8

## H4 Verdicts

| Scheme | Verdict |
|--------|---------|
| old provenance-aware | FAIL |
| revised aware | PASS |

## Depth Distribution in Top-k

| Bucket | Naive | Revised |
|--------|-------|---------|
| 2-hop | 20 | 20 |

| Cross-domain in top-k | 0 | 0 |