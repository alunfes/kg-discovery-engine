"""I4: Watchlist semantics — map branch + tier to actionable watch labels.

Watch labels communicate *what kind of market event to monitor* rather than
*what trade to execute*.  This preserves auditability (the system never gives
direct trade instructions) while making each hypothesis card operationally
meaningful.

Semantic grid:
  branch               | tier                  | watch_label
  ---------------------|----------------------|---------------------------
  flow_continuation    | actionable_watch      | trend_continuation_watch
  flow_continuation    | research_priority     | trend_continuation_watch
  flow_continuation    | monitor_borderline    | trend_continuation_watch
  positioning_unwind   | actionable_watch      | positioning_unwind_watch
  positioning_unwind   | research_priority     | positioning_unwind_watch
  positioning_unwind   | monitor_borderline    | positioning_unwind_watch
  beta_reversion       | actionable_watch      | beta_reversion_watch
  beta_reversion       | research_priority     | beta_reversion_watch
  beta_reversion       | monitor_borderline    | beta_reversion_watch
  any                  | baseline_like         | monitor_no_action
  any                  | reject_conflicted     | discard_or_low_priority
  other/unknown        | any active            | monitor_no_action

Design note: watch_label is branch-driven, with tier controlling urgency.
Tier information is preserved in `watch_urgency` (high/medium/low/none)
so consumers can further filter without re-deriving tier.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Branch → base watch label
# ---------------------------------------------------------------------------

_BRANCH_WATCH: dict[str, str] = {
    "flow_continuation": "trend_continuation_watch",
    "continuation_candidate": "trend_continuation_watch",
    "positioning_unwind": "positioning_unwind_watch",
    "beta_reversion": "beta_reversion_watch",
    "mean_reversion": "beta_reversion_watch",     # structural cousin; same watch
}

_TIER_URGENCY: dict[str, str] = {
    "actionable_watch": "high",
    "research_priority": "medium",
    "monitor_borderline": "low",
    "baseline_like": "none",
    "reject_conflicted": "none",
}

# Tiers that override branch label with non-actionable semantics
_NON_ACTIONABLE_TIERS: frozenset[str] = frozenset({
    "baseline_like",
    "reject_conflicted",
})

_LABEL_BASELINE: str = "monitor_no_action"
_LABEL_DISCARD: str = "discard_or_low_priority"


def _card_branch(tags: list[str]) -> str:
    """Canonical branch from card tags."""
    tag_set = set(tags)
    if "E1" in tag_set or "beta_reversion" in tag_set:
        return "beta_reversion"
    if "E2" in tag_set or "positioning_unwind" in tag_set:
        return "positioning_unwind"
    if "continuation_candidate" in tag_set or "flow_continuation" in tag_set:
        return "flow_continuation"
    if "mean_reversion_candidate" in tag_set:
        return "mean_reversion"
    if "E4" in tag_set or "null_baseline" in tag_set:
        return "null_baseline"
    return "other"


def assign_watch_label(branch: str, tier: str) -> str:
    """Map (branch, tier) to a watch label string.

    Args:
        branch: Canonical branch label.
        tier: I1 decision tier string.

    Returns:
        Watch label string.
    """
    if tier == "reject_conflicted":
        return _LABEL_DISCARD
    if tier == "baseline_like":
        return _LABEL_BASELINE
    # Active tier: use branch-driven label
    label = _BRANCH_WATCH.get(branch)
    if label:
        return label
    # Fallback for 'other', 'null_baseline', unknown branches
    return _LABEL_BASELINE


def assign_watch_urgency(tier: str) -> str:
    """Urgency level derived from tier."""
    return _TIER_URGENCY.get(tier, "none")


def compute_watchlist_semantics(
    tier_assignments: list[dict],
    cards: list,
) -> dict[str, Any]:
    """I4: Annotate each hypothesis with watch label and urgency.

    Args:
        tier_assignments: I1 output list (card_id, decision_tier, branch, ...).
        cards: HypothesisCard list (used for tag resolution).

    Returns:
        Dict with:
          watchlist_cards     — [{card_id, title, branch, tier, watch_label, watch_urgency}]
          label_counts        — {watch_label: count}
          urgency_counts      — {urgency: count}
          high_urgency_labels — top actionable_watch cards with their labels
    """
    # Build card → tags index for branch resolution
    card_tags: dict[str, list[str]] = {
        c.card_id: getattr(c, "tags", []) for c in cards
    }

    watchlist: list[dict] = []
    for a in tier_assignments:
        cid = a["card_id"]
        tags = card_tags.get(cid, [])
        # Prefer branch from tier_assignment dict; re-derive from tags as fallback
        branch = a.get("branch") or _card_branch(tags)
        tier = a["decision_tier"]
        label = assign_watch_label(branch, tier)
        urgency = assign_watch_urgency(tier)
        watchlist.append({
            "card_id": cid,
            "title": a.get("title", ""),
            "branch": branch,
            "decision_tier": tier,
            "watch_label": label,
            "watch_urgency": urgency,
            "composite_score": a.get("composite_score", 0.0),
        })

    # Counts
    label_counts: dict[str, int] = {}
    urgency_counts: dict[str, int] = {}
    for w in watchlist:
        label_counts[w["watch_label"]] = label_counts.get(w["watch_label"], 0) + 1
        urgency_counts[w["watch_urgency"]] = urgency_counts.get(w["watch_urgency"], 0) + 1

    # Top high-urgency entries
    high_urgency = sorted(
        [w for w in watchlist if w["watch_urgency"] == "high"],
        key=lambda w: w["composite_score"],
        reverse=True,
    )

    return {
        "watchlist_cards": watchlist,
        "label_counts": label_counts,
        "urgency_counts": urgency_counts,
        "high_urgency_labels": high_urgency[:5],
    }
