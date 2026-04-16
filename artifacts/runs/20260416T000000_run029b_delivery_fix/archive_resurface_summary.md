# Archive Re-surface Summary — Run 029B

## Bug (BUG-003)

**File**: `delivery_state.py:simulate_batch_refresh_with_archive()`

### Root Cause

```python
# BEFORE (buggy): resurfaced cards added only to the transient deck snapshot
resurfaced = archive_mgr.check_resurface(new_batch_cards, float(t))
deck.extend(resurfaced)                    # ← deck is rebuilt from all_cards each cycle
# all_cards never updated → resurfaced cards vanish in the next loop iteration
```

`deck` is a fresh list rebuilt from `all_cards` at the start of every cycle.
Cards appended only to `deck` do not survive past the current review snapshot.

### Fix

```python
# AFTER (correct): resurfaced cards added to both all_cards and deck
resurfaced = archive_mgr.check_resurface(new_batch_cards, float(t))
for card in resurfaced:
    all_cards.append((float(t), card))    # ← persistent; survives into next cycle
deck.extend(resurfaced)
```

## Re-surface Metrics (Corrected Run 029B)

| Cadence | Archived (avg/review) | Total resurfaced | Re-surface rate |
|---------|-----------------------|-----------------|-----------------|
| poll_30min+archive | 45.4 | 959 | high |
| poll_45min+archive | 37.4 | 313 | moderate |
| poll_60min+archive | 48.7 | 492 | moderate |

### Interpretation

The high re-surface count (959 for 30min cadence across 20 seeds × 8h) reflects
the short HL tiers (actionable_watch=40 min) generating frequent expired→archived
transitions, with recurring hypothesis signals triggering re-surface within the
120-min window.

With BUG-003 fixed, re-surfaced cards now persist into subsequent review snapshots
and age normally.  Before the fix, `total_resurfaced` counted only the first-cycle
injection — the cards disappeared immediately, understating operator-visible signal.

## Archive Policy (Standard Config — Confirmed)

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `_ARCHIVE_RATIO` | 5.0 × HL | 2.5× buffer beyond expiry (2.5× HL) |
| `resurface_window_min` | 120 min | Covers 2–3 detection cycles for HL=40 tier |
| `archive_max_age_min` | 480 min (8 h) | One full trading session horizon |

The standard config is unchanged; BUG-003 only affected persistence — the
archive semantics and window parameters were correct in the original design.

## Invariant Tests

`crypto/tests/test_run029b_delivery_fixes.py::TestResurfacedCardPersistence`

- `test_resurfaced_card_persists_with_manual_archive` — clone is fresh (age=0), not archived
- `test_resurfaced_card_not_present_without_fix` — regression guard: old path loses card
- `test_resurfaced_card_appears_in_next_review` — end-to-end via simulate_batch_refresh_with_archive
