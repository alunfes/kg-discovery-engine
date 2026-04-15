"""I2: Temporal persistence and promotion tracking.

Tracks hypothesis families across runs to identify signals that consistently
appear in the top-k (persistence) and cases where a branch promotion occurs
(soft_gated → active, or primary → rerouted).

Why run_007 as baseline:
  The first meaningful multi-signal run. Earlier runs lacked H1/H2/H3/I1
  outputs, making apples-to-apples comparison impossible.

ID design — {branch}:{pair}:{rule_tag}:
  branch   — canonical branch label (beta_reversion, positioning_unwind, other)
  pair     — canonical pair string "A/B" from card title
  rule_tag — first E-tag or D-tag from card tags (e.g. E1, E2, D1)

  This ID is stable across runs given same synthetic seed because:
  - The generator is deterministic (seed=42)
  - Branch + pair + rule_tag uniquely identify a hypothesis family
  - card_id (UUID) changes each run but the family ID does not

Persistence fields tracked:
  consecutive_top_k_count    — how many consecutive runs the family appeared in top-k
  persistence_score          — EMA-like: 0.6 * prev + 0.4 * appeared
  soft_gated_to_active_promotion — True if any run promoted this from soft_gated
  primary_to_rerouted_transition — True if originally primary, later rerouted
  uplift_persistence         — average uplift_over_matched_baseline across tracked runs
"""

from __future__ import annotations

import re
from typing import Any

_PAIR_RE = re.compile(r"\(([A-Z]+)[,/]([A-Z]+)\)")

# EMA decay factor for persistence score
_EMA_ALPHA: float = 0.40

# A family is considered "top-k" if its tier is one of the active tiers
_ACTIVE_TIERS: frozenset[str] = frozenset({
    "actionable_watch",
    "research_priority",
    "monitor_borderline",
})


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


def _card_pair(title: str) -> str:
    """Extract 'A/B' pair string from card title."""
    m = _PAIR_RE.search(title)
    return f"{m.group(1)}/{m.group(2)}" if m else "unknown"


def _rule_tag(tags: list[str]) -> str:
    """First E-tag or D-tag from tags, or 'generic' if none."""
    for tag in tags:
        if tag.startswith("E") or tag.startswith("D"):
            return tag
    return "generic"


def make_family_id(card) -> str:
    """Stable cross-run ID for a hypothesis family.

    Format: {branch}:{pair}:{rule_tag}

    Why not use card_id: UUIDs change every run. This ID is reproducible
    from the card's semantic content alone.
    """
    branch = _card_branch(card.tags)
    pair = _card_pair(card.title)
    tag = _rule_tag(card.tags)
    return f"{branch}:{pair}:{tag}"


def _build_reroute_index(reroute_candidates: list[dict]) -> dict[str, str]:
    """Map original_card_id → reroute_candidate_branch."""
    return {
        r["original_card_id"]: r["reroute_candidate_branch"]
        for r in reroute_candidates
    }


def compute_persistence_snapshot(
    run_id: str,
    cards: list,
    tier_assignments: list[dict],
    reroute_candidates: list[dict],
    baseline_pool: dict,
    prior_state: dict[str, dict] | None = None,
) -> dict[str, Any]:
    """I2: Build or update persistence state for this run.

    Args:
        run_id: Current run identifier (e.g. 'run_008_sprint_i').
        cards: HypothesisCard objects.
        tier_assignments: I1 tier assignment list (card_id, decision_tier, ...).
        reroute_candidates: H2 reroute candidate list.
        baseline_pool: G3 matched_baseline_pool dict.
        prior_state: Persistence state dict from the prior run (or None for first run).

    Returns:
        Dict with:
          run_id         — current run identifier
          families       — {family_id: persistence_record}
          promotions     — list of promotion events this run
          summary        — aggregate counts
    """
    # Build lookup structures
    tier_by_cid = {a["card_id"]: a["decision_tier"] for a in tier_assignments}
    reroute_by_cid = _build_reroute_index(reroute_candidates)
    g3_uplift_by_cid: dict[str, float] = {
        d["card_id"]: d.get("complexity_adjusted_uplift", 0.0)
        for d in baseline_pool.get("matched_baseline_cards", [])
    }

    prev = prior_state or {}
    families: dict[str, dict] = {}
    promotions: list[dict] = []

    for card in cards:
        fid = make_family_id(card)
        cid = card.card_id
        tier = tier_by_cid.get(cid, "baseline_like")
        uplift = g3_uplift_by_cid.get(cid, 0.0)
        is_soft_gated = "soft_gated" in getattr(card, "tags", [])
        is_rerouted = cid in reroute_by_cid
        in_active = tier in _ACTIVE_TIERS

        # Load prior state for this family if exists
        prior = prev.get(fid, {})
        prev_consec = prior.get("consecutive_top_k_count", 0)
        prev_ema = prior.get("persistence_score", 0.0)
        prev_sg_promoted = prior.get("soft_gated_to_active_promotion", False)
        prev_rerouted = prior.get("primary_to_rerouted_transition", False)
        prev_uplift_sum = prior.get("_uplift_sum", 0.0)
        prev_uplift_n = prior.get("_uplift_n", 0)

        # Update consecutive count
        if in_active:
            consecutive = prev_consec + 1
        else:
            consecutive = 0

        # EMA persistence score
        ema = round(_EMA_ALPHA * (1.0 if in_active else 0.0) + (1 - _EMA_ALPHA) * prev_ema, 4)

        # Promotion tracking
        sg_promoted = prev_sg_promoted
        if not prev_sg_promoted and is_soft_gated and in_active:
            sg_promoted = True
            promotions.append({
                "run_id": run_id,
                "family_id": fid,
                "event": "soft_gated_to_active",
                "tier": tier,
            })

        rerouted = prev_rerouted
        if not prev_rerouted and is_rerouted:
            rerouted = True
            promotions.append({
                "run_id": run_id,
                "family_id": fid,
                "event": "primary_to_rerouted",
                "rerouted_branch": reroute_by_cid[cid],
            })

        # Running uplift average
        new_uplift_sum = prev_uplift_sum + uplift
        new_uplift_n = prev_uplift_n + 1
        uplift_persistence = round(new_uplift_sum / new_uplift_n, 4)

        families[fid] = {
            "family_id": fid,
            "last_run_id": run_id,
            "consecutive_top_k_count": consecutive,
            "persistence_score": ema,
            "last_tier": tier,
            "soft_gated_to_active_promotion": sg_promoted,
            "primary_to_rerouted_transition": rerouted,
            "uplift_persistence": uplift_persistence,
            # Internal accumulators (not surfaced in output JSON)
            "_uplift_sum": new_uplift_sum,
            "_uplift_n": new_uplift_n,
        }

    # Summary
    n_persistent = sum(1 for f in families.values() if f["consecutive_top_k_count"] >= 2)
    n_promoted_sg = sum(1 for f in families.values() if f["soft_gated_to_active_promotion"])
    n_rerouted = sum(1 for f in families.values() if f["primary_to_rerouted_transition"])
    top_persistent = sorted(
        families.values(),
        key=lambda f: (f["consecutive_top_k_count"], f["persistence_score"]),
        reverse=True,
    )[:5]

    return {
        "run_id": run_id,
        "families": families,
        "promotions": promotions,
        "summary": {
            "n_families": len(families),
            "n_persistent_ge2_runs": n_persistent,
            "n_soft_gated_to_active": n_promoted_sg,
            "n_primary_to_rerouted": n_rerouted,
        },
        "top_persistent_families": [
            {k: v for k, v in f.items() if not k.startswith("_")}
            for f in top_persistent
        ],
    }
