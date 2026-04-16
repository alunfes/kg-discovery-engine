"""H2: Contradiction-driven rerouting.

Maps contradiction type + location → reroute candidate branch:
  - beta_reversion terminal contradiction  → continuation or unwind candidate
  - unwind contradiction with no accumulation → baseline or reversion candidate

Rerouted candidates are derivative records attached to the original hypothesis.
The original is NOT removed; reroutes are additive and fully traceable.

Each reroute record includes:
  original_card_id            — source card's card_id
  original_branch             — branch of the source card
  reroute_candidate_branch    — proposed alternative branch
  reroute_confidence          — [0, 1] confidence in the reroute
  original_score              — composite_score of the source card
  rerouted_score              — estimated score if rerouted (scaled from original)
  original_vs_rerouted_delta  — rerouted_score - original_score
  reroute_reason              — why this reroute was triggered
"""

import re

# ---------------------------------------------------------------------------
# Reroute rules
# ---------------------------------------------------------------------------

_PAIR_RE = re.compile(r"\(([A-Z]+)[,/]([A-Z]+)\)")

_REROUTE_RULES: list[dict] = [
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> claude/crazy-vaughan
    # J1: High-confidence reroute when BOTH funding extreme AND OI accumulation
    # suppress E1 Chain 2 (transient_aggression).  This fires only when the J1
    # discriminative gate in chain_grammar.py did not prevent the card from being
    # generated (defense-in-depth: in practice the chain_grammar fix prevents E1
    # from firing, so this rule rarely triggers post-fix, but remains as a safety net).
    {
        "source_branch": "beta_reversion",
        "trigger_chain": "beta_reversion_transient_aggr",
        "trigger_detail_keyword": "funding extreme + OI accumulation both present",
        "reroute_to": "positioning_unwind",
        "confidence": 0.85,
        "score_scale": 1.10,
        "reason": "beta_reversion transient_aggr overridden by J1 gate (funding extreme + OI confirmed) → high-confidence unwind",
    },
<<<<<<< HEAD
=======
>>>>>>> claude/optimistic-swanson
=======
>>>>>>> claude/sleepy-mestorf
=======
>>>>>>> claude/crazy-vaughan
    {
        "source_branch": "beta_reversion",
        "trigger_chain": "beta_reversion_no_funding_oi",
        "trigger_detail_keyword": "funding extreme present",
        "reroute_to": "positioning_unwind",
        "confidence": 0.70,
        "score_scale": 1.05,
        "reason": "beta_reversion blocked by funding extreme → unwind candidate",
    },
    {
        "source_branch": "beta_reversion",
        "trigger_chain": "beta_reversion_no_funding_oi",
        "trigger_detail_keyword": "OI accumulation detected",
        "reroute_to": "positioning_unwind",
        "confidence": 0.65,
        "score_scale": 1.03,
        "reason": "beta_reversion blocked by OI accumulation → unwind candidate",
    },
    {
        "source_branch": "beta_reversion",
        "trigger_chain": "beta_reversion_weak_premium",
        "trigger_detail_keyword": "premium not weak",
        "reroute_to": "flow_continuation",
        "confidence": 0.60,
        "score_scale": 0.97,
        "reason": "beta_reversion blocked by strong premium → continuation candidate",
    },
    {
        "source_branch": "positioning_unwind",
        "trigger_chain": "positioning_unwind_oi_crowding",
        "trigger_detail_keyword": "no OI accumulation",
        "reroute_to": "beta_reversion",
        "confidence": 0.55,
        "score_scale": 0.90,
        "reason": "unwind blocked by missing OI → reversion candidate",
    },
    {
        "source_branch": "positioning_unwind",
        "trigger_chain": "positioning_unwind_funding_pressure",
        "trigger_detail_keyword": "no funding extreme",
        "reroute_to": "mean_reversion",
        "confidence": 0.50,
        "score_scale": 0.88,
        "reason": "unwind blocked by absent funding pressure → mean_reversion",
    },
]


def _card_pair(card) -> str:
    """Extract 'A/B' pair string from card title."""
    m = _PAIR_RE.search(card.title)
    return f"{m.group(1)}/{m.group(2)}" if m else ""


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


def _matching_suppressions(
    pair: str, rule: dict, suppression_log: list[dict]
) -> list[dict]:
    """Find suppression entries that match the reroute rule for the given pair."""
    return [
        e for e in suppression_log
        if e.get("pair") == pair
        and e.get("chain") == rule["trigger_chain"]
        and rule["trigger_detail_keyword"] in e.get("detail", "")
    ]


def _build_reroute(card, rule: dict, contradiction_penalty: float) -> dict:
    """Build one reroute candidate record from a card and a rule."""
    orig_score = card.composite_score
    rerouted = round(
        min(1.0, (orig_score - contradiction_penalty) * rule["score_scale"]),
        4,
    )
    return {
        "original_card_id": card.card_id,
        "original_title": card.title[:70],
        "original_branch": rule["source_branch"],
        "reroute_candidate_branch": rule["reroute_to"],
        "reroute_confidence": rule["confidence"],
        "original_score": orig_score,
        "rerouted_score": rerouted,
        "original_branch_vs_rerouted_score": round(rerouted - orig_score, 4),
        "reroute_reason": rule["reason"],
    }


def compute_reroute_candidates(
    cards: list,
    contradiction_metrics: dict[str, dict],
    suppression_log: list[dict],
    top_k: int,
) -> list[dict]:
    """H2: Generate reroute candidates from contradiction analysis.

    For each card with at least one matched suppression entry that satisfies a
    reroute rule, generate a derivative reroute record.  Cards are not removed;
    reroutes are additive.

    Args:
        cards: HypothesisCard list from the pipeline.
        contradiction_metrics: Per-card G1 contradiction metrics.
        suppression_log: Chain grammar suppression log.
        top_k: For context in summary stats.

    Returns:
        List of reroute-candidate dicts (one per triggered rule per card).
    """
    reroutes: list[dict] = []
    for card in cards:
        pair = _card_pair(card)
        branch = _card_branch(card.tags)
        cm = contradiction_metrics.get(card.card_id, {})
        penalty = cm.get("conflict_penalty", 0.0)
        for rule in _REROUTE_RULES:
            if rule["source_branch"] != branch:
                continue
            matching = _matching_suppressions(pair, rule, suppression_log)
            if matching:
                reroutes.append(_build_reroute(card, rule, penalty))
    return reroutes


def reroute_summary(reroutes: list[dict], top_k: int) -> dict:
    """Aggregate statistics for the reroute candidates.

    Args:
        reroutes: Output of compute_reroute_candidates().
        top_k: Reference k for coverage stats.

    Returns:
        Dict with n_rerouted, branch_distribution, mean_delta, top_reroutes.
    """
    if not reroutes:
        return {"n_rerouted": 0, "branch_distribution": {}, "mean_delta": 0.0,
                "top_reroutes": []}
    branch_dist: dict[str, int] = {}
    for r in reroutes:
        b = r["reroute_candidate_branch"]
        branch_dist[b] = branch_dist.get(b, 0) + 1
    deltas = [r["original_branch_vs_rerouted_score"] for r in reroutes]
    mean_delta = round(sum(deltas) / len(deltas), 4)
    top = sorted(reroutes, key=lambda r: r["rerouted_score"], reverse=True)[:5]
    return {
        "n_rerouted": len(reroutes),
        "branch_distribution": branch_dist,
        "mean_delta": mean_delta,
        "top_reroutes": top,
    }
