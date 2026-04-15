"""I1: Decision tiering — convert hypothesis-arbitration signals into a
five-tier decision framework.

Tiers (ordered from most to least actionable):
  actionable_watch      — high confidence, positive uplift, manageable conflict
  research_priority     — good signal, needs further confirmation
  monitor_borderline    — soft-gated OR moderate conflict, rescued by uplift
  baseline_like         — undifferentiated from baseline; no action
  reject_conflicted     — contradiction strong enough to discard even high raw score

Why five tiers (not a binary keep/drop):
  Binary thresholding loses information at the margins. A card with composite=0.80
  but severity=6.0 contradictions should not be treated the same as composite=0.80
  with no contradictions. Similarly, a soft-gated card with strong uplift over its
  baseline is actionable context even if its raw score is moderate.

Inputs per card (all extracted from upstream pipeline outputs):
  normalized_meta_score         — F2 within-branch percentile + z-score blend
  conflict_adjusted_score       — G1 composite minus contradiction penalty
  uplift_over_matched_baseline  — G3 complexity-adjusted uplift
  reroute_candidate_branch      — H2 target branch if rerouted (or None)
  reroute_confidence            — H2 confidence in reroute [0,1]
  is_soft_gated                 — H1 soft-gate flag (border-case activation)
  contradiction_severity        — G1 weighted severity sum
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Tier constants
# ---------------------------------------------------------------------------

TIER_ACTIONABLE_WATCH: str = "actionable_watch"
TIER_RESEARCH_PRIORITY: str = "research_priority"
TIER_MONITOR_BORDERLINE: str = "monitor_borderline"
TIER_BASELINE_LIKE: str = "baseline_like"
TIER_REJECT_CONFLICTED: str = "reject_conflicted"

# ---------------------------------------------------------------------------
# Thresholds — calibrated on run_007 distribution
# ---------------------------------------------------------------------------

# Contradiction severity at or above this always forces reject_conflicted,
# regardless of raw score.  (run_007 beta_reversion worst case = 6.0)
_HIGH_SEVERITY_THRESHOLD: float = 5.0

# If conflict_adjusted_score < this AND severity >= _MEDIUM_SEVERITY, reject.
_LOW_CONFLICT_ADJ: float = 0.55
_MEDIUM_SEVERITY_THRESHOLD: float = 2.5

# Soft-gated + uplift above this → monitor_borderline (rescued from baseline_like)
_BORDERLINE_UPLIFT_RESCUE: float = 0.05

# Top-tier thresholds
_ACTIONABLE_SCORE_MIN: float = 0.74
_ACTIONABLE_UPLIFT_MIN: float = 0.04

# Research-priority thresholds
_RESEARCH_SCORE_MIN: float = 0.65

# Minimum score to qualify for monitor_borderline without uplift rescue
_MONITOR_SCORE_MIN: float = 0.60


def assign_decision_tier(
    composite_score: float,
    normalized_meta_score: float,
    conflict_adjusted_score: float,
    uplift_over_matched_baseline: float,
    contradiction_severity: float,
    is_soft_gated: bool,
    reroute_candidate_branch: str | None = None,
    reroute_confidence: float = 0.0,
) -> str:
    """Assign a decision tier to one hypothesis card.

    Evaluation order:
      1. Hard reject: severe contradiction → reject_conflicted
      2. Conditional reject: low conflict-adj + medium severity → reject_conflicted
      3. Soft-gated uplift rescue → monitor_borderline
      4. High score + positive uplift → actionable_watch
      5. Good score → research_priority
      6. Minimum threshold → monitor_borderline
      7. Fall-through → baseline_like

    Args:
        composite_score: Card composite_score from scorer.
        normalized_meta_score: F2 meta_score (within-branch z+percentile blend).
        conflict_adjusted_score: G1 net_support_minus_contradiction.
        uplift_over_matched_baseline: G3 complexity_adjusted_uplift vs comparator pool.
        contradiction_severity: G1 contradiction_severity (severity-weighted sum).
        is_soft_gated: True if card was activated via border-case gate (H1).
        reroute_candidate_branch: H2 reroute target branch, or None.
        reroute_confidence: H2 confidence in the reroute.

    Returns:
        One of the five tier string constants.
    """
    # 1. Hard reject: high severity → reject regardless of raw score
    if contradiction_severity >= _HIGH_SEVERITY_THRESHOLD:
        return TIER_REJECT_CONFLICTED

    # 2. Conditional reject: moderate severity + low conflict-adjusted score
    if (contradiction_severity >= _MEDIUM_SEVERITY_THRESHOLD
            and conflict_adjusted_score < _LOW_CONFLICT_ADJ):
        return TIER_REJECT_CONFLICTED

    # 3. Soft-gated rescue: border-case activation with meaningful uplift
    # Why: soft-gated cards that beat their baseline deserve monitoring even
    # if raw score is modest. Without this, border cases are silently dropped.
    if is_soft_gated and uplift_over_matched_baseline >= _BORDERLINE_UPLIFT_RESCUE:
        return TIER_MONITOR_BORDERLINE

    # 4. Actionable watch: high score + positive uplift + low conflict
    if (composite_score >= _ACTIONABLE_SCORE_MIN
            and uplift_over_matched_baseline >= _ACTIONABLE_UPLIFT_MIN
            and contradiction_severity < _MEDIUM_SEVERITY_THRESHOLD):
        return TIER_ACTIONABLE_WATCH

    # 5. Research priority: solid score, not conflict-killed
    if composite_score >= _RESEARCH_SCORE_MIN:
        return TIER_RESEARCH_PRIORITY

    # 6. Monitor borderline: passed minimum threshold
    if composite_score >= _MONITOR_SCORE_MIN:
        return TIER_MONITOR_BORDERLINE

    # 7. Below all thresholds: undifferentiated from baseline
    return TIER_BASELINE_LIKE


def compute_decision_tiers(
    cards: list,
    contradiction_metrics: dict[str, dict],
    meta_scores: dict[str, float],
    baseline_pool: dict,
    reroute_candidates: list[dict],
) -> dict[str, Any]:
    """I1: Compute decision tiers for all hypothesis cards.

    Args:
        cards: HypothesisCard list from pipeline.
        contradiction_metrics: G1 per-card contradiction metrics.
        meta_scores: F2 card_id → meta_score.
        baseline_pool: G3 matched_baseline_pool dict.
        reroute_candidates: H2 reroute candidate list.

    Returns:
        Dict with tier_assignments (list), tier_counts (dict),
        tier_distribution_pct (dict), reject_conflicted_examples (list).
    """
    # Index G3 uplift per card
    g3_uplift: dict[str, float] = {
        d["card_id"]: d.get("complexity_adjusted_uplift", 0.0)
        for d in baseline_pool.get("matched_baseline_cards", [])
    }
    global_baseline = baseline_pool.get("global_baseline_score", 0.62)

    # Index H2 reroutes per original_card_id (take highest-confidence reroute)
    reroute_index: dict[str, dict] = {}
    for r in reroute_candidates:
        cid = r["original_card_id"]
        if cid not in reroute_index or r["reroute_confidence"] > reroute_index[cid]["reroute_confidence"]:
            reroute_index[cid] = r

    assignments: list[dict] = []
    for card in cards:
        cid = card.card_id
        cm = contradiction_metrics.get(cid, {})
        meta = meta_scores.get(cid, card.composite_score)
        uplift = g3_uplift.get(cid, card.composite_score - global_baseline)
        severity = float(cm.get("contradiction_severity", 0.0))
        conflict_adj = float(cm.get("net_support_minus_contradiction", card.composite_score))
        is_soft_gated = "soft_gated" in getattr(card, "tags", [])
        reroute = reroute_index.get(cid, {})

        tier = assign_decision_tier(
            composite_score=card.composite_score,
            normalized_meta_score=meta,
            conflict_adjusted_score=conflict_adj,
            uplift_over_matched_baseline=uplift,
            contradiction_severity=severity,
            is_soft_gated=is_soft_gated,
            reroute_candidate_branch=reroute.get("reroute_candidate_branch"),
            reroute_confidence=reroute.get("reroute_confidence", 0.0),
        )

        assignments.append({
            "card_id": cid,
            "title": card.title[:70],
            "branch": _card_branch(card.tags),
            "composite_score": card.composite_score,
            "normalized_meta_score": round(meta, 4),
            "conflict_adjusted_score": round(conflict_adj, 4),
            "uplift_over_matched_baseline": round(uplift, 4),
            "contradiction_severity": round(severity, 4),
            "is_soft_gated": is_soft_gated,
            "reroute_candidate_branch": reroute.get("reroute_candidate_branch"),
            "reroute_confidence": reroute.get("reroute_confidence", 0.0),
            "decision_tier": tier,
        })

    # Aggregate tier counts
    tier_counts: dict[str, int] = {}
    for a in assignments:
        t = a["decision_tier"]
        tier_counts[t] = tier_counts.get(t, 0) + 1
    total = max(len(assignments), 1)
    tier_pct = {t: round(c / total, 4) for t, c in tier_counts.items()}

    # Highlight reject_conflicted examples
    rejected = [
        a for a in assignments
        if a["decision_tier"] == TIER_REJECT_CONFLICTED
    ]
    rejected.sort(key=lambda a: a["contradiction_severity"], reverse=True)

    return {
        "tier_assignments": assignments,
        "tier_counts": tier_counts,
        "tier_distribution_pct": tier_pct,
        "reject_conflicted_examples": rejected[:5],
        "actionable_watch_top": sorted(
            [a for a in assignments if a["decision_tier"] == TIER_ACTIONABLE_WATCH],
            key=lambda a: a["composite_score"],
            reverse=True,
        )[:5],
        "monitor_borderline_cases": [
            a for a in assignments
            if a["decision_tier"] == TIER_MONITOR_BORDERLINE
        ][:5],
    }


def _card_branch(tags: list[str]) -> str:
    """Canonical branch label from tags."""
    tag_set = set(tags)
    if "E1" in tag_set or "beta_reversion" in tag_set:
        return "beta_reversion"
    if "E2" in tag_set or "positioning_unwind" in tag_set:
        return "positioning_unwind"
    if "E4" in tag_set or "null_baseline" in tag_set:
        return "null_baseline"
    return "other"
