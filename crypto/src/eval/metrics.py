"""Branch diversity metrics — Sprint E (E3).

Metrics:
  branch_entropy          — Shannon entropy of the branch distribution.
  top_k_branch_share      — fraction of top-k belonging to the dominant branch.
  mean_score_by_branch    — dict: branch → mean composite score.
  survival_across_runs    — placeholder (single run: N/A).
  branch_activation_rate  — fraction of corr-break pairs that produced ≥1 card
                            per branch (requires n_corr_break_pairs).
  branch_suppression_reason — dict: suppression reason → count from suppression_log.

Branch labels are derived from HypothesisCard.tags.
"""

import math
from collections import Counter


# Tag-to-branch mapping (priority order: first match wins)
_BRANCH_TAGS: list[tuple[str, str]] = [
    ("E1", "beta_reversion"),
    ("beta_reversion", "beta_reversion"),
    ("E2", "positioning_unwind"),
    ("positioning_unwind", "positioning_unwind"),
    ("E4", "null_baseline"),
    ("null_baseline", "null_baseline"),
    ("continuation_candidate", "flow_continuation"),
    ("microstructure_artifact", "microstructure_artifact"),
    ("mean_reversion_candidate", "mean_reversion"),
]


def _card_branch(tags: list[str]) -> str:
    """Map a card's tags to a canonical branch label."""
    tag_set = set(tags)
    for tag, branch in _BRANCH_TAGS:
        if tag in tag_set:
            return branch
    return "other"


def _branch_counts(cards: list) -> Counter:
    """Count cards per branch."""
    return Counter(_card_branch(c.tags) for c in cards)


def _entropy(counts: Counter) -> float:
    """Shannon entropy of a count distribution (nats → bits via log2)."""
    total = sum(counts.values())
    if total == 0:
        return 0.0
    return round(
        -sum((v / total) * math.log2(v / total) for v in counts.values() if v > 0),
        4,
    )


def _top_k_branch_share(cards: list, top_k: int) -> dict[str, float]:
    """Fraction of the top-k cards belonging to each branch.

    top-k is defined by descending composite_score order.
    Returns dict: branch → share in [0, 1].
    """
    top = sorted(cards, key=lambda c: c.composite_score, reverse=True)[:top_k]
    if not top:
        return {}
    counts = _branch_counts(top)
    total = len(top)
    return {branch: round(cnt / total, 4) for branch, cnt in counts.items()}


def _mean_score_by_branch(cards: list) -> dict[str, float]:
    """Mean composite score per branch."""
    branch_scores: dict[str, list[float]] = {}
    for c in cards:
        branch = _card_branch(c.tags)
        branch_scores.setdefault(branch, []).append(c.composite_score)
    return {
        branch: round(sum(scores) / len(scores), 4)
        for branch, scores in branch_scores.items()
    }


def _branch_activation_rate(
    cards: list, suppression_log: list[dict], n_pairs: int
) -> dict[str, float]:
    """Fraction of corr-break pairs that produced ≥1 card per branch.

    Activated pairs are inferred from existing cards (activated) + suppression
    log (attempted but suppressed).  n_pairs is the total number of corr-break
    pairs detected in the cross-asset KG.
    """
    if n_pairs == 0:
        return {}
    activated = _branch_counts(cards)
    # Count unique pairs per branch that attempted but were suppressed
    suppressed_pairs: dict[str, set[str]] = {}
    for entry in suppression_log:
        chain = entry.get("chain", "")
        pair = entry.get("pair", "unknown")
        branch = "beta_reversion" if "beta_reversion" in chain else (
            "positioning_unwind" if "positioning_unwind" in chain else "other"
        )
        suppressed_pairs.setdefault(branch, set()).add(pair)

    all_branches = set(activated.keys()) | set(suppressed_pairs.keys())
    rates: dict[str, float] = {}
    for branch in all_branches:
        n_active = min(activated.get(branch, 0), n_pairs)
        rates[branch] = round(n_active / n_pairs, 4)
    return rates


def _suppression_reason_counts(suppression_log: list[dict]) -> dict[str, int]:
    """Count suppression reasons from the suppression log."""
    counts: Counter = Counter(entry.get("reason", "unknown") for entry in suppression_log)
    return dict(counts)


def compute_branch_metrics(
    cards: list,
    suppression_log: list[dict],
    n_corr_break_pairs: int = 0,
    top_k: int = 10,
) -> dict:
    """Compute all E3 branch diversity metrics.

    Args:
        cards: List of HypothesisCard objects from the pipeline run.
        suppression_log: List of dicts from build_chain_grammar_kg().
        n_corr_break_pairs: Count of CorrelationNode(is_break=True) in cross KG.
        top_k: K for top_k_branch_share calculation.

    Returns:
        dict with keys: branch_entropy, top_k_branch_share, mean_score_by_branch,
        survival_across_runs, branch_activation_rate, branch_suppression_reason.
    """
    counts = _branch_counts(cards)
    return {
        "branch_distribution": dict(counts),
        "branch_entropy": _entropy(counts),
        "top_k_branch_share": _top_k_branch_share(cards, top_k),
        "mean_score_by_branch": _mean_score_by_branch(cards),
        "survival_across_runs": "N/A (single run)",
        "branch_activation_rate": _branch_activation_rate(cards, suppression_log, n_corr_break_pairs),
        "branch_suppression_reason": _suppression_reason_counts(suppression_log),
        "total_cards": len(cards),
        "n_corr_break_pairs": n_corr_break_pairs,
    }
