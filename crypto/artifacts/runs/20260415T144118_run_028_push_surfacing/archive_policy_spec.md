# Archive Policy Specification — Run 028

## States

| State | Condition | Operator sees? |
|-------|-----------|---------------|
| fresh | age/HL < 0.5 | Yes (priority) |
| active | 0.5 ≤ age/HL < 1.0 | Yes |
| aging | 1.0 ≤ age/HL < 1.75 | Yes (last-chance) |
| digest_only | 1.75 ≤ age/HL < 2.5 | Summary only |
| expired | age/HL ≥ 2.5 | No |
| **archived** | age_min ≥ 5.0× half_life_min | No (queryable) |

## Transition Rules

### expired → archived
- **When**: `age_min >= 5.0 × half_life_min`
- **Effect**: Card moved to archive pool; excluded from stale_count denominator
- **Why 5.0×**: gives 2.5× buffer beyond expiry threshold (2.5×), covering
  a full 200-min trading session window for HL=40 actionable_watch tier

### archived → fresh (re-surface)
- **When**: New card arrives with same `(branch, grammar_family)` within
  `resurface_window_min` (default: 120 min) of archival
- **Effect**: Clone of archived card injected as fresh (age_min=0), resurface_count+1
- **Why clone**: preserves original card_id integrity; re-surface is a new signal event
- **Why 120 min**: covers 2–3 detection cycles for HL=40 tier,
  treating pattern recurrence as confirmation rather than noise

### archived → deleted (hard prune)
- **When**: `current_time - archived_at >= archive_max_age_min`
  (default: 480 min / 8 h)
- **Effect**: Removed from pool; no further re-surface possible
- **Why 8h**: one trading session horizon; cards older
  than this cannot meaningfully influence current positioning decisions

## Archive Configuration Comparison

| Config | resurface_window | archive_max_age | Re-surface risk |
|--------|-----------------|-----------------|-----------------|
| tight | 60 min | 4 h | Low (narrower window) |
| **standard** | **120 min** | **8 h** | **Balanced** |
| loose | 180 min | 12 h | Higher (broader window) |

**Recommendation**: standard config — 120 min re-surface window, 8 h retention.

## Information Loss from Archiving

Archiving removes expired cards from the operator view.  Information loss is bounded:
- Cards enter archive only after expiry (already suppressed from full reviews)
- Re-surface captures recurrent signals within the trading session
- Hard deletion occurs only after 8 h (full session horizon)
- Archived cards remain queryable for audit/analytics

## Integration with Push Surfacing

T3 trigger (aging last-chance) fires before a card crosses into digest_only,
giving the operator one final notification.  This means no actionable card
should ever reach the archive without the operator having had at least one
push notification during its active lifecycle.
