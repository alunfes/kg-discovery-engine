"""Branch diversity and calibration metrics — Sprint E (E3) + Sprint F (F1–F5).

Sprint E metrics:
  branch_entropy          — Shannon entropy of the branch distribution.
  top_k_branch_share      — fraction of top-k belonging to each branch.
  mean_score_by_branch    — dict: branch → mean composite score.
  branch_activation_rate  — fraction of corr-break pairs producing ≥1 card per branch.
  branch_suppression_reason — dict: suppression reason → count.

Sprint F additions:
  F1  branch_calibration  — per-branch: count, mean, median, p90, top_k_share,
                            count_normalized_top_k_share, evidence_slope,
                            low_coverage_score_persistence.
  F2  normalized_ranking  — within-branch z-score + percentile, cross-branch
                            meta-score, raw-vs-normalized rank diff per card.
  F4  regime_stratified   — branch activation / top-k share / mean score per
                            regime bucket (vol, oi_growth, funding, lead, coverage).
  F5  baseline_uplift     — per-hypothesis uplift over matched E4 null baseline.
"""

import math
import re
from collections import Counter


# ---------------------------------------------------------------------------
# Branch label mapping
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Sprint E helpers (unchanged)
# ---------------------------------------------------------------------------

def _top_k_branch_share(cards: list, top_k: int) -> dict[str, float]:
    """Fraction of the top-k cards belonging to each branch."""
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
    """Fraction of corr-break pairs that produced ≥1 card per branch."""
    if n_pairs == 0:
        return {}
    activated = _branch_counts(cards)
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


# ---------------------------------------------------------------------------
# F1: branch-wise calibration helpers
# ---------------------------------------------------------------------------

def _median(values: list[float]) -> float:
    """Median of a sorted list."""
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return round(s[mid] if n % 2 == 1 else (s[mid - 1] + s[mid]) / 2.0, 4)


def _percentile(values: list[float], p: float) -> float:
    """p-th percentile (0–100) of a list using linear interpolation."""
    if not values:
        return 0.0
    s = sorted(values)
    idx = (p / 100.0) * (len(s) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(s) - 1)
    frac = idx - lo
    return round(s[lo] + frac * (s[hi] - s[lo]), 4)


def _linear_slope(xs: list[float], ys: list[float]) -> float:
    """OLS slope of y~x.  Returns 0.0 if fewer than 2 points or zero variance."""
    if len(xs) < 2:
        return 0.0
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    var = sum((x - mx) ** 2 for x in xs)
    if var < 1e-12:
        return 0.0
    return round(cov / var, 4)


def _compute_branch_calibration(
    cards: list, top_k: int
) -> dict[str, dict]:
    """F1: per-branch calibration stats.

    Returns dict: branch → {count, mean_score, median_score, p90_score,
    top_k_share, count_normalized_top_k_share, evidence_count_vs_score_slope,
    low_coverage_score_persistence, score_architecture_advantage}.
    """
    # Group cards by branch
    branch_cards: dict[str, list] = {}
    for c in cards:
        branch = _card_branch(c.tags)
        branch_cards.setdefault(branch, []).append(c)

    total = len(cards)
    top_k_counts = _branch_counts(
        sorted(cards, key=lambda c: c.composite_score, reverse=True)[:top_k]
    )
    top_k_total = min(top_k, total)

    result: dict[str, dict] = {}
    for branch, bcards in branch_cards.items():
        scores = [c.composite_score for c in bcards]
        ev_counts = [len(c.evidence_nodes) for c in bcards]
        mean_s = round(sum(scores) / len(scores), 4)
        med_s = _median(scores)
        p90_s = _percentile(scores, 90)
        tk_share = round(top_k_counts.get(branch, 0) / max(top_k_total, 1), 4)
        fraction_total = len(bcards) / max(total, 1)
        # count_normalized_top_k_share: ratio of tk_share to expected if uniform
        count_norm_share = round(tk_share / max(fraction_total, 1e-6), 4)
        # evidence slope: regression of evidence_count on composite_score
        ev_slope = _linear_slope(ev_counts, scores)
        # low_coverage_persistence: mean score where evidence_count <= 2
        low_cov = [c.composite_score for c in bcards if len(c.evidence_nodes) <= 2]
        low_cov_persist = round(sum(low_cov) / len(low_cov), 4) if low_cov else None
        # Architecture advantage flag: count_norm_share > 1.1 means over-represented
        arch_advantage = count_norm_share > 1.1
        result[branch] = {
            "count": len(bcards),
            "mean_score": mean_s,
            "median_score": med_s,
            "p90_score": p90_s,
            "top_k_share": tk_share,
            "count_normalized_top_k_share": count_norm_share,
            "evidence_count_vs_score_slope": ev_slope,
            "low_coverage_score_persistence": low_cov_persist,
            "score_architecture_advantage": arch_advantage,
        }
    return result


# ---------------------------------------------------------------------------
# F2: cross-branch normalization helpers
# ---------------------------------------------------------------------------

def _branch_stats(cards: list) -> dict[str, dict]:
    """Compute mean and std per branch for within-branch z-score."""
    branch_scores: dict[str, list[float]] = {}
    for c in cards:
        branch_scores.setdefault(_card_branch(c.tags), []).append(c.composite_score)
    stats: dict[str, dict] = {}
    for branch, scores in branch_scores.items():
        n = len(scores)
        mean = sum(scores) / n
        var = sum((s - mean) ** 2 for s in scores) / max(n - 1, 1)
        stats[branch] = {"mean": mean, "std": max(math.sqrt(var), 1e-4), "count": n}
    return stats


def compute_normalized_ranking(cards: list, top_k: int) -> dict:
    """F2: cross-branch normalized ranking.

    Returns:
        {
          normalized_cards: [
            {card_id, title, branch, raw_rank, raw_score,
             branch_zscore, branch_percentile, meta_score, norm_rank,
             rank_diff}
          ],
          ranking_diff_summary: {mean_abs_diff, max_diff, n_cards_changed_top_k}
        }
    """
    if not cards:
        return {"normalized_cards": [], "ranking_diff_summary": {}}

    stats = _branch_stats(cards)
    # Build per-branch sorted positions for percentile
    branch_sorted: dict[str, list[float]] = {}
    for c in cards:
        branch_sorted.setdefault(_card_branch(c.tags), []).append(c.composite_score)
    for b in branch_sorted:
        branch_sorted[b].sort()

    raw_ranked = sorted(cards, key=lambda c: c.composite_score, reverse=True)
    raw_rank_map = {c.card_id: i + 1 for i, c in enumerate(raw_ranked)}

    enriched = []
    for c in cards:
        branch = _card_branch(c.tags)
        s = stats[branch]
        score = c.composite_score
        # Within-branch z-score
        bz = round((score - s["mean"]) / s["std"], 4)
        # Within-branch percentile (rank / count)
        sorted_branch = branch_sorted[branch]
        rank_in_branch = sorted(sorted_branch).index(score) + 1
        bp = round(rank_in_branch / len(sorted_branch), 4)
        # Meta-score: percentile * 0.6 + z-score scaled to [0,1] * 0.4
        # z-score scaled: clamp to [-3, 3], map to [0, 1]
        bz_scaled = round(min(1.0, max(0.0, (bz + 3) / 6.0)), 4)
        meta = round(bp * 0.6 + bz_scaled * 0.4, 4)
        enriched.append({
            "card_id": c.card_id,
            "title": c.title,
            "branch": branch,
            "raw_rank": raw_rank_map[c.card_id],
            "raw_score": score,
            "branch_zscore": bz,
            "branch_percentile": bp,
            "meta_score": meta,
        })

    # Normalized rank by meta_score descending
    norm_ranked = sorted(enriched, key=lambda d: d["meta_score"], reverse=True)
    for i, d in enumerate(norm_ranked):
        d["norm_rank"] = i + 1
        d["rank_diff"] = d["raw_rank"] - d["norm_rank"]

    # Summary stats
    diffs = [abs(d["rank_diff"]) for d in enriched]
    raw_top_k_ids = {d["card_id"] for d in enriched if d["raw_rank"] <= top_k}
    norm_top_k_ids = {d["card_id"] for d in enriched if d["norm_rank"] <= top_k}
    n_changed = len(raw_top_k_ids.symmetric_difference(norm_top_k_ids)) // 2

    return {
        "normalized_cards": sorted(norm_ranked, key=lambda d: d["norm_rank"]),
        "ranking_diff_summary": {
            "mean_abs_diff": round(sum(diffs) / max(len(diffs), 1), 2),
            "max_diff": max(diffs) if diffs else 0,
            "n_cards_changed_top_k": n_changed,
        },
    }


# ---------------------------------------------------------------------------
# F4: regime-stratified evaluation helpers
# ---------------------------------------------------------------------------

_PAIR_RE = re.compile(r"\(([A-Z]+)[,/]([A-Z]+)\)")


def _extract_pair(title: str) -> tuple[str, str] | None:
    """Extract (asset_a, asset_b) pair from card title."""
    m = _PAIR_RE.search(title)
    if m:
        return m.group(1), m.group(2)
    return None


def _card_regime_buckets(card) -> list[str]:
    """Return list of regime bucket labels for a card (can belong to multiple).

    Buckets:
      high_vol:       microstructure_artifact tag OR continuation_candidate tag
      low_vol:        mean_reversion_candidate OR null_baseline (calm market)
      high_oi_growth: oi_crowding or one_sided_oi in tags
      flat_oi:        no OI growth signal
      funding_shifted: funding_pressure or positioning_unwind tags
      funding_quiet:  beta_reversion or null_baseline tags
      btc_led:        BTC appears in pair
      alt_led:        BTC NOT in pair
      high_coverage:  traceability >= 0.75
      low_coverage:   traceability < 0.75
    """
    tags = set(card.tags)
    buckets = []
    # vol
    if "microstructure_artifact" in tags or "continuation_candidate" in tags:
        buckets.append("high_vol")
    elif "mean_reversion_candidate" in tags or "null_baseline" in tags or "beta_reversion" in tags:
        buckets.append("low_vol")
    # oi
    if "oi_crowding" in tags or "one_sided_oi" in tags:
        buckets.append("high_oi_growth")
    else:
        buckets.append("flat_oi")
    # funding
    if "funding_pressure" in tags or "positioning_unwind" in tags or "E2" in tags:
        buckets.append("funding_shifted")
    elif "beta_reversion" in tags or "null_baseline" in tags or "E1" in tags:
        buckets.append("funding_quiet")
    # BTC lead
    pair = _extract_pair(card.title)
    if pair and "BTC" in pair:
        buckets.append("btc_led")
    else:
        buckets.append("alt_led")
    # coverage
    tr = card.scores.traceability if hasattr(card.scores, "traceability") else 0.5
    if tr >= 0.75:
        buckets.append("high_coverage")
    else:
        buckets.append("low_coverage")
    return buckets


def compute_regime_stratified(cards: list, top_k: int) -> dict:
    """F4: aggregate branch metrics per regime bucket.

    Returns dict: bucket → {branch_activation, top_k_share, mean_score,
    dominant_branch, n_cards}.
    """
    # Collect all known buckets
    bucket_cards: dict[str, list] = {}
    for card in cards:
        for bucket in _card_regime_buckets(card):
            bucket_cards.setdefault(bucket, []).append(card)

    top_k_set = {
        c.card_id
        for c in sorted(cards, key=lambda c: c.composite_score, reverse=True)[:top_k]
    }

    result: dict[str, dict] = {}
    for bucket, bcards in bucket_cards.items():
        scores = [c.composite_score for c in bcards]
        mean_s = round(sum(scores) / len(scores), 4) if scores else 0.0
        in_top_k = [c for c in bcards if c.card_id in top_k_set]
        tk_share = round(len(in_top_k) / max(len(bcards), 1), 4)
        branch_cnt = _branch_counts(bcards)
        dominant = branch_cnt.most_common(1)[0][0] if branch_cnt else "none"
        branch_activation = {
            b: round(cnt / max(len(bcards), 1), 4)
            for b, cnt in branch_cnt.items()
        }
        result[bucket] = {
            "n_cards": len(bcards),
            "mean_score": mean_s,
            "top_k_share": tk_share,
            "dominant_branch": dominant,
            "branch_activation": branch_activation,
        }
    return result


# ---------------------------------------------------------------------------
# F5: baseline uplift helpers
# ---------------------------------------------------------------------------

def compute_baseline_uplift(cards: list) -> dict:
    """F5: compare each non-baseline card to its matched E4 baseline.

    Matches are by pair extracted from title: (A,B) pattern.

    Returns:
        {
          uplift_cards: [{card_id, title, branch, pair,
                          uplift_over_baseline, incremental_evidence_count,
                          complexity_penalty, complexity_penalty_adjusted_uplift}],
          top_uplift: [top-5 by adjusted_uplift],
          mean_uplift_by_branch: dict,
        }
    """
    # Index E4 baseline cards by pair
    baseline_by_pair: dict[str, object] = {}
    for c in cards:
        if "null_baseline" in c.tags or "E4" in c.tags:
            pair = _extract_pair(c.title)
            if pair:
                key = f"{pair[0]}/{pair[1]}"
                # Keep highest-scoring baseline per pair
                if key not in baseline_by_pair or c.composite_score > baseline_by_pair[key].composite_score:
                    baseline_by_pair[key] = c

    uplift_cards = []
    for c in cards:
        if "null_baseline" in c.tags or "E4" in c.tags:
            continue  # Skip baselines themselves
        pair = _extract_pair(c.title)
        if not pair:
            continue
        key = f"{pair[0]}/{pair[1]}"
        baseline = baseline_by_pair.get(key)
        if not baseline:
            continue
        branch = _card_branch(c.tags)
        uplift = round(c.composite_score - baseline.composite_score, 4)
        incr_ev = len(c.evidence_nodes) - len(baseline.evidence_nodes)
        # Complexity penalty: 0.02 per additional evidence node beyond first
        penalty = round(0.02 * max(0, incr_ev - 1), 4)
        adj_uplift = round(uplift - penalty, 4)
        uplift_cards.append({
            "card_id": c.card_id,
            "title": c.title,
            "branch": branch,
            "pair": key,
            "baseline_score": baseline.composite_score,
            "card_score": c.composite_score,
            "uplift_over_baseline": uplift,
            "incremental_evidence_count": incr_ev,
            "complexity_penalty": penalty,
            "complexity_penalty_adjusted_uplift": adj_uplift,
        })

    uplift_cards.sort(key=lambda d: d["complexity_penalty_adjusted_uplift"], reverse=True)
    top5 = [
        {k: v for k, v in d.items() if k in ("card_id", "title", "branch", "pair",
                                               "complexity_penalty_adjusted_uplift")}
        for d in uplift_cards[:5]
    ]

    # Mean uplift by branch
    branch_uplift: dict[str, list[float]] = {}
    for d in uplift_cards:
        branch_uplift.setdefault(d["branch"], []).append(d["complexity_penalty_adjusted_uplift"])
    mean_by_branch = {
        b: round(sum(vals) / len(vals), 4)
        for b, vals in branch_uplift.items()
    }

    return {
        "uplift_cards": uplift_cards,
        "top_uplift": top5,
        "mean_uplift_by_branch": mean_by_branch,
        "n_matched": len(uplift_cards),
    }


# ---------------------------------------------------------------------------
# Public entry point (F1–F5 extended)
# ---------------------------------------------------------------------------

def compute_branch_metrics(
    cards: list,
    suppression_log: list[dict],
    n_corr_break_pairs: int = 0,
    top_k: int = 10,
) -> dict:
    """Compute all branch diversity and calibration metrics (E3 + F1–F5).

    Args:
        cards: List of HypothesisCard objects from the pipeline run.
        suppression_log: List of dicts from build_chain_grammar_kg().
        n_corr_break_pairs: Count of CorrelationNode(is_break=True) in cross KG.
        top_k: K for top_k_branch_share calculation.

    Returns:
        dict with all E3 keys plus F1 branch_calibration, F2 normalized_ranking,
        F4 regime_stratified, F5 baseline_uplift.
    """
    counts = _branch_counts(cards)
    return {
        # E3 (unchanged)
        "branch_distribution": dict(counts),
        "branch_entropy": _entropy(counts),
        "top_k_branch_share": _top_k_branch_share(cards, top_k),
        "mean_score_by_branch": _mean_score_by_branch(cards),
        "survival_across_runs": "N/A (single run)",
        "branch_activation_rate": _branch_activation_rate(
            cards, suppression_log, n_corr_break_pairs
        ),
        "branch_suppression_reason": _suppression_reason_counts(suppression_log),
        "total_cards": len(cards),
        "n_corr_break_pairs": n_corr_break_pairs,
        # F1: per-branch calibration
        "branch_calibration": _compute_branch_calibration(cards, top_k),
        # F2: cross-branch normalization
        "normalized_ranking": compute_normalized_ranking(cards, top_k),
        # F4: regime-stratified
        "regime_stratified": compute_regime_stratified(cards, top_k),
        # F5: baseline uplift
        "baseline_uplift": compute_baseline_uplift(cards),
    }
