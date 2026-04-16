# Delivery Policy (Simplified) — Run 033

*Supersedes any prior description that included T3 as a trigger condition.*

## Push Delivery Policy

The push engine fires a "review now" signal when ANY of the following trigger
conditions are met on an incoming batch AND no suppression condition applies.

---

## Trigger Conditions

### T1 — High-conviction fresh card
- **Scope**: incoming batch only
- **Condition**: any arriving card satisfies both:
  - `tier` ∈ {`actionable_watch`, `research_priority`}
  - `composite_score` ≥ 0.74
- **Rationale**: a new card with strong score and high-priority tier warrants
  immediate operator attention, regardless of deck accumulation.

### T2 — Fresh-card count threshold
- **Scope**: incoming batch only
- **Condition**: count of high-priority (`actionable_watch` or
  `research_priority`) cards in the arriving batch ≥ 3
- **Rationale**: a batch with multiple high-priority signals collectively
  warrants review even if no single card clears the T1 score threshold.

---

## Suppression Conditions

### S1 — No actionable cards
- **Condition**: no card in the full deck is in state `fresh`, `active`, or `aging`
- **Effect**: suppress push even if T1/T2 triggered on incoming cards

### S2 — All fresh cards are digest-collapsed duplicates
- **Condition**: every fresh/active card is either low-priority OR part of a
  family with ≥ 2 members (would collapse into a digest)
- **Effect**: suppress — no unique information available outside the digest

### S3 — Rate limit
- **Condition**: a push event fired < 15 min ago
- **Effect**: suppress to avoid burst notifications on a single large batch

---

## What Is NOT a Trigger

- **Aging / last-chance**: there is no "T3" trigger. A card aging toward
  `digest_only` does not independently fire a push. The operator relies on T1
  and T2 during the card's fresh/active window. If T1/T2 covered the card
  while fresh, no further notification is needed.

---

## Delivery Parameters

| Parameter | Value |
|-----------|-------|
| T1 score threshold | 0.74 |
| T1 priority tiers | actionable_watch, research_priority |
| T2 count threshold | 3 high-priority incoming cards |
| Rate limit gap | 15 min |
| seeds (validation) | 42–61 (20 seeds) |

---

## Validated Metrics (Run 033, default config)

| Metric | Value |
|--------|-------|
| Reviews/day | 18.45 |
| Missed critical | 0 |
| T1 events | 123 |
| T2 events | 107 |

Zero missed critical is the hard safety constraint. Policy is unchanged from
Run 028 because T3 never fired in any simulation.
