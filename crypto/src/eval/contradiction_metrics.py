"""G1: Conflict-aware ranking — per-hypothesis contradiction metrics.

Attaches five new metrics to each hypothesis card based on the suppression log:
  contradiction_count               — number of contradictory_evidence entries for the pair+branch
  contradiction_severity            — strength-weighted sum (chain-type and detail)
  contradiction_confidence_weighted_score — severity scaled by corr_break_score of the pair
  contradiction_proximity_to_terminal — how close to the terminal claim the contradiction hits
  net_support_minus_contradiction   — composite_score minus the scaled penalty

Three ranking modes are returned by compute_conflict_adjusted_ranking():
  raw_score              — card.composite_score (unchanged)
  normalized_meta_score  — F2 meta_score (within-branch percentile + z-score)
  conflict_adjusted_score — composite_score minus contradiction penalty
"""

import math
import re

# ---------------------------------------------------------------------------
# Chain-level weights
# ---------------------------------------------------------------------------

# Proximity of contradiction to the terminal claim per chain.
# Higher = contradiction blocks more of the supporting path → harder penalty.
_CHAIN_PROXIMITY: dict[str, float] = {
    "beta_reversion_no_funding_oi": 0.85,   # blocks 2 of 3 E1-chain-1 hops
    "beta_reversion_weak_premium": 0.70,    # blocks premium-gated path
    "beta_reversion_transient_aggr": 0.50,  # partial transient check fails
    "positioning_unwind_funding_pressure": 0.75,
    "positioning_unwind_oi_crowding": 0.65,
    "positioning_unwind_premium_compress": 0.60,
}

# Severity multiplier by contradiction detail keyword.
_DETAIL_SEVERITY: dict[str, float] = {
    "funding extreme present": 1.5,
    "OI accumulation detected": 1.2,
    "premium not weak": 1.4,
}

_PAIR_RE = re.compile(r"\(([A-Z]+)[,/]([A-Z]+)\)")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _card_pair(card) -> str:
    """Extract 'A/B' pair string from card title."""
    m = _PAIR_RE.search(card.title)
    return f"{m.group(1)}/{m.group(2)}" if m else ""


def _card_branch(tags: list[str]) -> str:
    """Map card tags to canonical branch label."""
    tag_set = set(tags)
    if "E1" in tag_set or "beta_reversion" in tag_set:
        return "beta_reversion"
    if "E2" in tag_set or "positioning_unwind" in tag_set:
        return "positioning_unwind"
    if "E4" in tag_set or "null_baseline" in tag_set:
        return "null_baseline"
    return "other"


def _chain_branch(chain_name: str) -> str:
    """Map suppression log chain name to branch."""
    if "beta_reversion" in chain_name:
        return "beta_reversion"
    if "positioning_unwind" in chain_name:
        return "positioning_unwind"
    return "other"


def _detail_severity(detail: str) -> float:
    """Severity multiplier from contradiction detail string."""
    for key, val in _DETAIL_SEVERITY.items():
        if key in detail:
            return val
    return 1.0


# ---------------------------------------------------------------------------
# G1 core computation
# ---------------------------------------------------------------------------

def compute_contradiction_metrics(
    cards: list,
    suppression_log: list[dict],
    cross_kg,
) -> dict[str, dict]:
    """Compute per-card G1 contradiction metrics.

    Args:
        cards: HypothesisCard objects from the pipeline run.
        suppression_log: chain_grammar suppression log (list of dicts).
        cross_kg: Cross-asset KGraph, used to look up corr_break_score.

    Returns:
        Dict keyed by card_id → {contradiction_count, contradiction_severity,
        contradiction_confidence_weighted_score,
        contradiction_proximity_to_terminal,
        net_support_minus_contradiction, conflict_penalty}.

    Why break_score for confidence weighting:
        A CorrelationNode with high break_score is a more confident structural
        break; a contradiction against it is thus more meaningful (and penalises
        harder than a contradiction against a weak, noisy break).
    """
    pair_break_score = _index_break_scores(cross_kg)
    pair_contradictions = _index_contradictions(suppression_log)

    result: dict[str, dict] = {}
    for card in cards:
        pair = _card_pair(card)
        branch = _card_branch(card.tags)
        relevant = _relevant_contradictions(pair, branch, pair_contradictions)

        count = len(relevant)
        severity, prox_weights = _severity_and_proximity(relevant)
        break_score = pair_break_score.get(pair, 0.5)
        conf_weighted = round(severity * break_score, 4)
        prox = (
            round(sum(prox_weights) / len(prox_weights), 4)
            if prox_weights else 0.0
        )
        # Penalty: capped at 0.30 so a card can't go deeply negative
        penalty = round(min(0.30, severity * prox * 0.05), 4)
        net = round(card.composite_score - penalty, 4)

        result[card.card_id] = {
            "pair": pair,
            "branch": branch,
            "contradiction_count": count,
            "contradiction_severity": round(severity, 4),
            "contradiction_confidence_weighted_score": conf_weighted,
            "contradiction_proximity_to_terminal": prox,
            "net_support_minus_contradiction": net,
            "conflict_penalty": penalty,
        }
    return result


def _index_break_scores(cross_kg) -> dict[str, float]:
    """Build pair → max corr_break_score index from cross-asset KG."""
    scores: dict[str, float] = {}
    for node in cross_kg.nodes.values():
        if node.node_type != "CorrelationNode":
            continue
        if not node.attributes.get("is_break"):
            continue
        a1 = node.attributes.get("asset_a", "")
        a2 = node.attributes.get("asset_b", "")
        key = f"{a1}/{a2}"
        bs = float(node.attributes.get("corr_break_score", 0.0))
        scores[key] = max(scores.get(key, 0.0), bs)
    return scores


def _index_contradictions(
    suppression_log: list[dict],
) -> dict[str, list[dict]]:
    """Index contradictory_evidence entries by pair."""
    index: dict[str, list[dict]] = {}
    for entry in suppression_log:
        if entry.get("reason") != "contradictory_evidence":
            continue
        pair = entry.get("pair", "")
        if pair:
            index.setdefault(pair, []).append(entry)
    return index


def _relevant_contradictions(
    pair: str,
    branch: str,
    pair_contradictions: dict[str, list[dict]],
) -> list[dict]:
    """Select contradictions that penalise the card's own branch.

    For beta_reversion: E1 chain contradictions (E2 signals blocking E1) hurt.
    For positioning_unwind: the same contradictions SUPPORT the card, so no penalty.
    For other branches: any same-branch chain contradiction applies.
    """
    entries = pair_contradictions.get(pair, [])
    if branch == "beta_reversion":
        # E1 chains contradicted by E2 evidence → genuine contradiction for E1 card
        return [e for e in entries if "beta_reversion" in e.get("chain", "")]
    # positioning_unwind and others: E1 contradictions are supportive; skip
    return [e for e in entries if _chain_branch(e.get("chain", "")) == branch]


def _severity_and_proximity(
    relevant: list[dict],
) -> tuple[float, list[float]]:
    """Compute total severity and per-entry proximity weights."""
    severity = 0.0
    prox_weights: list[float] = []
    for entry in relevant:
        detail = entry.get("detail", "")
        chain = entry.get("chain", "")
        severity += _detail_severity(detail)
        prox_weights.append(_CHAIN_PROXIMITY.get(chain, 0.5))
    return severity, prox_weights


# ---------------------------------------------------------------------------
# G1: three-way ranking comparison
# ---------------------------------------------------------------------------

def compute_conflict_adjusted_ranking(
    cards: list,
    contradiction_metrics: dict[str, dict],
    meta_scores: dict[str, float],
    top_k: int,
) -> dict:
    """G1: Compare raw_score, normalized_meta_score, conflict_adjusted_score.

    Args:
        cards: HypothesisCard list (sorted by composite_score desc).
        contradiction_metrics: Output of compute_contradiction_metrics().
        meta_scores: {card_id: meta_score} from F2 normalized_ranking.
        top_k: K for ranking comparison.

    Returns:
        {ranking_comparison, conflict_shifted_examples, summary}.
    """
    raw_ranked = sorted(cards, key=lambda c: c.composite_score, reverse=True)
    raw_rank_map = {c.card_id: i + 1 for i, c in enumerate(raw_ranked)}

    norm_ranked = sorted(
        cards,
        key=lambda c: meta_scores.get(c.card_id, c.composite_score),
        reverse=True,
    )
    norm_rank_map = {c.card_id: i + 1 for i, c in enumerate(norm_ranked)}

    conflict_scores = {
        c.card_id: contradiction_metrics.get(c.card_id, {}).get(
            "net_support_minus_contradiction", c.composite_score
        )
        for c in cards
    }
    conflict_ranked = sorted(
        cards, key=lambda c: conflict_scores[c.card_id], reverse=True
    )
    conflict_rank_map = {c.card_id: i + 1 for i, c in enumerate(conflict_ranked)}

    comparison = []
    for card in cards:
        cid = card.card_id
        cm = contradiction_metrics.get(cid, {})
        entry = {
            "card_id": cid,
            "title": card.title[:60],
            "branch": _card_branch(card.tags),
            "raw_rank": raw_rank_map[cid],
            "raw_score": card.composite_score,
            "norm_rank": norm_rank_map[cid],
            "meta_score": round(meta_scores.get(cid, card.composite_score), 4),
            "conflict_adjusted_score": round(conflict_scores[cid], 4),
            "conflict_rank": conflict_rank_map[cid],
            "contradiction_count": cm.get("contradiction_count", 0),
            "contradiction_severity": cm.get("contradiction_severity", 0.0),
            "conflict_penalty": cm.get("conflict_penalty", 0.0),
            "rank_diff_norm_vs_raw": raw_rank_map[cid] - norm_rank_map[cid],
            "rank_diff_conflict_vs_raw": raw_rank_map[cid] - conflict_rank_map[cid],
        }
        comparison.append(entry)

    comparison.sort(key=lambda d: d["raw_rank"])

    # Examples where contradiction moved rank significantly (fell > 2 places)
    shifted = [
        d for d in comparison
        if d["rank_diff_conflict_vs_raw"] < -2  # fell in conflict ranking
    ]
    shifted.sort(key=lambda d: d["rank_diff_conflict_vs_raw"])

    diffs = [abs(d["rank_diff_conflict_vs_raw"]) for d in comparison]
    raw_top_k = {d["card_id"] for d in comparison if d["raw_rank"] <= top_k}
    conflict_top_k = {d["card_id"] for d in comparison if d["conflict_rank"] <= top_k}
    n_changed = len(raw_top_k.symmetric_difference(conflict_top_k)) // 2

    return {
        "ranking_comparison": comparison,
        "conflict_shifted_examples": shifted[:5],
        "summary": {
            "mean_abs_conflict_vs_raw_diff": round(
                sum(diffs) / max(len(diffs), 1), 2
            ),
            "max_conflict_vs_raw_diff": max(diffs) if diffs else 0,
            "n_top_k_changed_by_conflict": n_changed,
        },
    }
