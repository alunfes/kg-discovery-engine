# Selection Policy Redesign — run_032 WS2

## Motivation

run_031 proved that `compose_cross_domain` with shortest-path top-70 selection produces C=A (augmented KG = original KG). WS1 confirmed the mechanism: all 70 top-k slots are filled by length-2 paths; all 86 augmented-edge paths rank ≥74.

WS2 redesigns the selection layer to test whether augmented paths can be made reachable.

## 5 Policies

### Policy A: Baseline (current)
```
sort(path_length ASC, path_weight DESC) → top-70
```
- Augmented quota: 0
- Expected augmented inclusion: ~0

### Policy B: Augmentation Quota
```
top-15 augmented (shortest-path rank) + top-55 non-augmented
```
- Hard reserves 15 of 70 slots for augmented-edge paths
- Falls back to non-augmented if fewer than 15 augmented paths exist
- Augmented quota: 15/70 = 21.4%

### Policy C: Novelty Boost
```
score = (1 - path_len/max_len) + 0.5 * novelty(path)
novelty = +0.3 (uses_aug_edge) + 0.1 (path_len≥4) + 0.1 (cross_domain)
```
- Soft augmentation preference via composite score
- α=0.5 means novelty can overcome 1 length unit of disadvantage

### Policy D: Multi-bucket
```
bucket1 (35): shortest-path stable
bucket2 (15): augmented-edge paths
bucket3 (10): high-novelty (top novelty score)
bucket4 (10): exploratory (len≥3, mid-range weight)
```
- No duplicate (subject, object) pairs across buckets
- Bucket fill order: b1 → b2 → b3 → b4 → overflow from baseline

### Policy E: Reranking Layer
```
Stage 1: baseline top-200 candidate pool
Stage 2: greedy reranker
  score = 0.4*path_quality + 0.2*density_proxy + 0.2*diversity_penalty + 0.2*aug_bonus
```
- path_quality = 0.6*(1-len/max_len) + 0.4*(weight/max_weight)
- density_proxy = path_weight / max_weight (proxy for literture density)
- diversity_penalty = -(0.5*subj_seen + 0.5*obj_seen)
- aug_bonus = 1.0 if uses_augmented_edge else 0.0

## Implementation

`src/scientific_hypothesis/selection_policies_v2.py`

All policies implement `SelectionPolicy.select(candidates, k, aug_edge_set, seed)`.

## Key Design Constraint

Policies operate on the **full candidate pool** (no pre-filter). This ensures that augmented paths are available for selection; the policy determines which are chosen.
