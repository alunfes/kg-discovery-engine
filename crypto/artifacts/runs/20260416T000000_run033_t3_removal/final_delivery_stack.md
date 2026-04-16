# Final Delivery Stack — Run 033

*Complete specification of the push delivery system after T3 removal.*

---

## Layer 1: Card Lifecycle (delivery_state.py)

Cards progress through six states based on `age_min / half_life_min` ratio:

| State | Ratio range | Operator sees |
|-------|-------------|---------------|
| fresh | < 0.5 | Full priority |
| active | 0.5 – 1.0 | Normal |
| aging | 1.0 – 1.75 | Fading |
| digest_only | 1.75 – 2.5 | Summary only |
| expired | ≥ 2.5 | Hidden |
| archived | age ≥ 5× HL | Queryable only |

Half-lives by tier:

| Tier | HL (min) |
|------|----------|
| actionable_watch | 40 |
| research_priority | 50 |
| monitor_borderline | 60 |
| baseline_like | 90 |
| reject_conflicted | 20 |

---

## Layer 2: Family Collapse (delivery_state.py)

Cards sharing `(branch, grammar_family)` across ≥ 2 assets are collapsed
into a single `DigestCard`.  Lead card (highest score) shown in full;
co-assets listed in one line.  Reduces operator surface by ~76% in hot
batches (20 cards → ~4.8 items per review, from Run 027).

---

## Layer 3: Archive Policy (delivery_state.py)

| Transition | Condition | Effect |
|------------|-----------|--------|
| expired → archived | age ≥ 5× HL | Hidden; queryable |
| archived → fresh (re-surface) | Same family arrives within 120 min | Clone injected as fresh |
| archived → deleted | archived for > 480 min (8 h) | Hard removal |

---

## Layer 4: Push Surfacing Engine (push_surfacing.py)

### Trigger conditions (incoming batch)

| Trigger | Condition | Scope |
|---------|-----------|-------|
| T1 | tier ∈ {actionable_watch, research_priority} AND score ≥ 0.74 | Incoming only |
| T2 | count(high-priority incoming cards) ≥ 3 | Incoming only |

### Suppression conditions

| Suppressor | Condition |
|-----------|-----------|
| S1 | No fresh/active/aging cards in full deck |
| S2 | All fresh cards are low-priority or digest-collapsed |
| S3 | Last push < 15 min ago (rate limit) |

### Removed (Run 033)

~~T3 — aging last-chance~~ *(removed; was dead code, never fired)*

---

## Layer 5: Validated Performance (seeds 42–61, 8 h session, hot_batch_prob=0.30)

| Config | Reviews/day | Missed critical | T1 events | T2 events |
|--------|-------------|-----------------|-----------|-----------|
| default | 18.45 | 0 | 123 | 107 |
| sensitive | 19.05 | 0 | 127 | 109 |
| conservative | 16.95 | 0 | 107 | 106 |

**Recommended: default config.**

Operator burden (default): 18.45 reviews/day × 5.73 collapsed items = 105.7
vs. poll_45min benchmark: 32 reviews/day × 4.85 items = 155.2
→ **Push reduces burden by 32% while achieving zero missed critical.**

---

## Production Configuration (JSON)

```json
{
  "delivery_mode": "push",
  "push_triggers": {
    "T1_high_conviction_threshold": 0.74,
    "T1_high_priority_tiers": ["actionable_watch", "research_priority"],
    "T2_fresh_count_threshold": 3,
    "rate_limit_gap_min": 15.0
  },
  "archive_policy": {
    "archive_ratio_hl": 5.0,
    "resurface_window_min": 120,
    "archive_max_age_min": 480
  },
  "family_collapse": {
    "enabled": true,
    "min_family_size": 2
  },
  "baseline_fallback_cadence_min": 45
}
```

---

*Generated: Run 033 (2026-04-16). Supersedes Run 028 delivery stack.*
